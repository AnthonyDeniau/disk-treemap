"""Iterative, metadata-only traversal with bounded embedded subtrees."""

from __future__ import annotations

import fnmatch
import json
import os
import stat
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Node = dict[str, Any]
SYSTEM_ROOTS = frozenset(
    {
        "/dev",
        "/proc",
        "/sys",
        "/run",
        "/Volumes",
        "/Network",
        "/System/Volumes",
        "/Library/Developer/CoreSimulator/Volumes",
    }
)


@dataclass(frozen=True)
class ScanOptions:
    size: str = "allocated"
    excludes: tuple[str, ...] = ()
    one_file_system: bool = False
    count_hard_links: bool = False
    chunk_size: int = 5000


@dataclass
class ScanStats:
    files: int = 0
    directories: int = 0
    unreadable: int = 0
    excluded: int = 0
    hard_links: int = 0
    allocated_fallbacks: int = 0


@dataclass
class _Frame:
    path: Path
    name: str
    parent: _Frame | None
    children: list[Node] = field(default_factory=list)
    nodes: int = 1
    height: int = 1
    partial: bool = False


class Scanner:
    def __init__(
        self,
        root: Path,
        chunk_directory: Path,
        options: ScanOptions,
        ignored_paths: tuple[Path, ...] = (),
        progress: Callable[[ScanStats], None] | None = None,
    ) -> None:
        self.root = root
        self.chunk_directory = chunk_directory
        self.options = options
        self.ignored_paths = set(ignored_paths)
        self.progress = progress
        self.stats = ScanStats()
        self.chunks = 0
        self._last_progress = time.monotonic()
        self._hard_links: set[tuple[int, int]] = set()
        self._root_device = root.stat().st_dev

    def exclusion(self, path: Path) -> str | None:
        if path in self.ignored_paths:
            return "Report output (excluded from its own scan)"
        name = path.name
        lower = name.casefold()
        # Do not enumerate credential stores, even if selected as the root.
        if (lower == "keychains" and path.parent.name == "Library") or lower.endswith(
            (".keychain", ".keychain-db")
        ):
            return "Credential store (not scanned)"
        parts = path.parts
        if len(parts) >= 2 and parts[-2:] in {
            ("Library", "Mobile Documents"),
            ("Library", "CloudStorage"),
        }:
            return "Cloud provider storage (not scanned or downloaded)"
        if path.as_posix() in SYSTEM_ROOTS:
            return "Virtual filesystem or additional mounted volume"
        relative = path.relative_to(self.root).as_posix()
        for pattern in self.options.excludes:
            candidate = relative if "/" in pattern else name
            if fnmatch.fnmatchcase(candidate, pattern.rstrip("/")):
                return "Excluded by pattern: " + pattern
        return None

    def _excluded(self, name: str, reason: str, *, unreadable: bool = False) -> Node:
        if unreadable:
            self.stats.unreadable += 1
        else:
            self.stats.excluded += 1
        return {"name": name, "kind": "excluded", "value": 0, "reason": reason}

    def _chunk(self, children: list[Node]) -> str:
        self.chunks += 1
        chunk_id = f"c{self.chunks:07d}"
        self.chunk_directory.mkdir(exist_ok=True, mode=0o700)
        payload = json.dumps(children, ensure_ascii=True, separators=(",", ":"))
        # External JS allows offline file:// loading without a web server or fetch.
        source = (
            "window.__TREE_CHUNKS__=window.__TREE_CHUNKS__||{};"
            f"window.__TREE_CHUNKS__[{json.dumps(chunk_id)}]={payload};\n"
        )
        target = self.chunk_directory / f"{chunk_id}.js"
        target.write_text(source, encoding="utf-8")
        target.chmod(0o600)
        return chunk_id

    def _finish(self, frame: _Frame) -> tuple[Node, int, int]:
        frame.children.sort(key=lambda n: (-n["value"], n["name"].casefold(), n["name"]))
        node: Node = {
            "name": frame.name,
            "kind": "directory",
            "value": sum(child["value"] for child in frame.children),
        }
        if frame.partial:
            node["partial"] = True
        if frame.children:
            # Bound serialization depth independently of subtree size.
            if frame.nodes > self.options.chunk_size or frame.height >= 48:
                node["chunkId"] = self._chunk(frame.children)
                return node, 1, 1
            node["children"] = frame.children
        return node, frame.nodes, frame.height

    def _file(self, path: Path, info: os.stat_result) -> Node:
        self.stats.files += 1
        size = info.st_size
        if self.options.size == "allocated":
            blocks = getattr(info, "st_blocks", None)
            if blocks is None:
                self.stats.allocated_fallbacks += 1
            else:
                size = blocks * 512
        node: Node = {"name": path.name, "kind": "file", "value": size, "logicalSize": info.st_size}
        if stat.S_ISLNK(info.st_mode):
            node["isSymlink"] = True
        elif info.st_nlink > 1 and not self.options.count_hard_links:
            identity = (info.st_dev, info.st_ino)
            if identity in self._hard_links:
                node["value"] = 0
                node["isHardlink"] = True
                self.stats.hard_links += 1
            self._hard_links.add(identity)
        return node

    def scan(self) -> Node:
        reason = self.exclusion(self.root)
        if reason:
            return self._excluded(self.root.name or str(self.root), reason)
        root_frame = _Frame(self.root, self.root.name or str(self.root), None)
        # A frame is visited twice; no Python recursion or open directory per depth.
        tasks: list[tuple[_Frame, bool]] = [(root_frame, False)]
        result: Node = {}
        while tasks:
            frame, finished = tasks.pop()
            if finished:
                node, count, height = self._finish(frame)
                if frame.parent is None:
                    result = node
                else:
                    frame.parent.children.append(node)
                    frame.parent.nodes += count
                    frame.parent.height = max(frame.parent.height, height + 1)
                    frame.parent.partial |= frame.partial
                continue
            self.stats.directories += 1
            directories: list[Path] = []
            try:
                with os.scandir(frame.path) as entries:
                    for entry in entries:
                        path = frame.path / entry.name
                        reason = self.exclusion(path)
                        if reason:
                            child = self._excluded(entry.name, reason)
                        else:
                            try:
                                info = entry.stat(follow_symlinks=False)
                                if stat.S_ISDIR(info.st_mode):
                                    if (
                                        self.options.one_file_system
                                        and info.st_dev != self._root_device
                                    ):
                                        child = self._excluded(entry.name, "Different filesystem")
                                    else:
                                        directories.append(path)
                                        continue
                                elif stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                                    child = self._file(path, info)
                                else:
                                    child = self._excluded(entry.name, "Special filesystem entry")
                            except OSError as exc:
                                child = self._excluded(
                                    entry.name,
                                    f"Metadata unavailable ({type(exc).__name__})",
                                    unreadable=True,
                                )
                        frame.children.append(child)
                        frame.nodes += 1
                        frame.partial |= child["kind"] == "excluded"
            except OSError as exc:
                self.stats.unreadable += 1
                frame.partial = True
                frame.children.append(
                    {
                        "name": "[scan error]",
                        "kind": "excluded",
                        "value": 0,
                        "reason": f"Directory unavailable ({type(exc).__name__})",
                    }
                )
            tasks.append((frame, True))
            # Reverse lexical order on the stack gives stable hard-link accounting.
            for directory in sorted(directories, reverse=True):
                tasks.append((_Frame(directory, directory.name, frame), False))
            now = time.monotonic()
            if self.progress and now - self._last_progress >= 1:
                self.progress(self.stats)
                self._last_progress = now
        return result
