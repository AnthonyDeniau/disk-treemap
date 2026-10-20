"""Publish a report without overwriting an existing path or leaving partial output."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import asdict
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from . import __version__
from .scanner import Scanner, ScanOptions


def inline_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")


def generate_report(
    root: Path,
    output: Path,
    options: ScanOptions,
    *,
    label: str | None = None,
    progress=None,
) -> dict[str, Any]:
    root = root.expanduser().resolve(strict=True)
    output = output.expanduser()
    output = output.parent.resolve(strict=True) / output.name
    if not root.is_dir():
        raise ValueError("The scan root must be a directory")
    if output.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("The output filename must end in .html or .htm")
    if not output.parent.is_dir():
        raise ValueError("The output parent directory does not exist")
    template = files("disk_treemap").joinpath("assets/viewer.html").read_text(encoding="utf-8")
    if '"__TREE_DATA__"' not in template or '"__TREE_META__"' not in template:
        raise ValueError("The packaged viewer is missing its data placeholders")

    # Reserve the filename exclusively, then replace only our own empty reservation.
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    reservation = os.fstat(descriptor)
    os.close(descriptor)
    committed = False
    published_assets: Path | None = None
    rendered_identity: tuple[int, int] | None = None

    def owns_reservation() -> bool:
        try:
            current = output.lstat()
            return (
                current.st_ino == reservation.st_ino
                and current.st_dev == reservation.st_dev
                and current.st_size == 0
            )
        except OSError:
            return False

    try:
        with tempfile.TemporaryDirectory(prefix=".disk-treemap-build-", dir=output.parent) as stage:
            staging = Path(stage)
            scanner = Scanner(root, staging / "data", options, (output, staging), progress)
            tree = scanner.scan()
            tree["name"] = label if label is not None else str(root)
            assets_name = "disk-treemap-data-" + uuid.uuid4().hex[:12]
            try:
                free = shutil.disk_usage(root).free
            except OSError:
                free = None
            meta = {
                "schemaVersion": 1,
                "generator": "disk-treemap",
                "version": __version__,
                "root": tree["name"],
                "pathSeparator": os.sep,
                "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
                **asdict(scanner.stats),
                "chunks": scanner.chunks,
                "chunkDirectory": assets_name if scanner.chunks else "",
                "freeBytes": free,
                "sizeMode": options.size,
                "method": "st_blocks * 512 (logical size if unavailable)"
                if options.size == "allocated"
                else "st_size",
            }
            html = template.replace('"__TREE_DATA__"', inline_json(tree))
            html = html.replace('"__TREE_META__"', inline_json(meta))
            rendered = staging / "report.html"
            rendered.write_text(html, encoding="utf-8")
            rendered.chmod(0o600)
            rendered_info = rendered.stat()
            rendered_identity = (rendered_info.st_dev, rendered_info.st_ino)
            if not owns_reservation():
                raise OSError("The output changed during the scan; refusing to replace it")
            if scanner.chunks:
                assets_target = output.parent / assets_name
                if assets_target.exists() or assets_target.is_symlink():
                    raise OSError("Generated data folder already exists; retry with a new output")
                (staging / "data").rename(assets_target)
                published_assets = assets_target
            os.replace(rendered, output)
            committed = True
            return {"output": str(output), "bytes": tree["value"], **meta}
    finally:
        # A signal immediately after replace must not remove a complete report's data.
        if not committed and rendered_identity is not None:
            try:
                current = output.lstat()
                committed = (current.st_dev, current.st_ino) == rendered_identity
            except OSError:
                pass
        if not committed:
            if owns_reservation():
                output.unlink()
            if published_assets is not None and published_assets.exists():
                shutil.rmtree(published_assets)
