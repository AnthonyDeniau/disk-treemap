from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from disk_treemap.scanner import Scanner, ScanOptions


def scan(root: Path, tmp_path: Path, **options):
    scanner = Scanner(root, tmp_path / "chunks", ScanOptions(**options))
    return scanner, scanner.scan()


def children(node):
    return {child["name"]: child for child in node.get("children", [])}


def test_nested_files_and_empty_entries(tmp_path):
    root = tmp_path / "input"
    (root / "nested").mkdir(parents=True)
    (root / "nested" / "file.txt").write_bytes(b"hello")
    (root / "empty").mkdir()
    (root / "zero.txt").touch()
    scanner, tree = scan(root, tmp_path, size="logical")
    assert tree["value"] == 5
    assert scanner.stats.files == 2
    assert scanner.stats.directories == 3
    assert children(children(tree)["nested"])["file.txt"]["logicalSize"] == 5
    assert children(tree)["zero.txt"]["value"] == 0
    assert children(tree)["empty"]["kind"] == "directory"


def test_unicode_names_and_metadata_only_access(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    name = "résumé & notes 'quoted'.txt"
    (root / name).write_bytes(b"data")
    scanner = Scanner(root, tmp_path / "chunks", ScanOptions(size="logical"))
    with patch("builtins.open", side_effect=AssertionError("must not read file contents")):
        tree = scanner.scan()
    assert tree["children"][0]["name"] == name
    assert tree["value"] == 4


def test_allocated_size_and_sparse_file(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    target = root / "sparse.bin"
    with target.open("wb") as handle:
        handle.seek(16 * 1024**2)
        handle.write(b"x")
    scanner, tree = scan(root, tmp_path)
    info = target.stat()
    expected = info.st_blocks * 512 if hasattr(info, "st_blocks") else info.st_size
    assert tree["value"] == expected
    assert scanner.stats.allocated_fallbacks == (0 if hasattr(info, "st_blocks") else 1)


def test_excludes_prune_subtrees(tmp_path):
    root = tmp_path / "input"
    (root / "node_modules" / "nested").mkdir(parents=True)
    (root / "build").mkdir()
    (root / "node_modules" / "nested" / "big.bin").write_bytes(b"x" * 100)
    (root / "build" / "skip.log").write_text("log")
    (root / "keep.txt").write_text("ok")
    scanner, tree = scan(root, tmp_path, size="logical", excludes=("node_modules", "build/*.log"))
    assert tree["value"] == 2
    assert scanner.stats.files == 1
    assert children(tree)["node_modules"]["kind"] == "excluded"
    assert children(children(tree)["build"])["skip.log"]["kind"] == "excluded"


def test_credential_stores_are_never_enumerated(tmp_path):
    root = tmp_path / "Library" / "Keychains"
    root.mkdir(parents=True)
    scanner = Scanner(root, tmp_path / "chunks", ScanOptions())
    with patch("disk_treemap.scanner.os.scandir", side_effect=AssertionError("must not enumerate")):
        tree = scanner.scan()
    assert tree["kind"] == "excluded"
    assert scanner.stats.directories == 0


def test_keychain_source_code_is_not_a_credential_store(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    (root / "Keychain.swift").write_text("source")
    (root / "login.keychain-db").write_bytes(b"private")
    scanner, tree = scan(root, tmp_path, size="logical")
    assert scanner.stats.files == 1
    assert tree["value"] == 6
    assert children(tree)["login.keychain-db"]["kind"] == "excluded"


def test_cloud_provider_is_not_enumerated(tmp_path):
    root = tmp_path / "Library" / "CloudStorage"
    root.mkdir(parents=True)
    scanner = Scanner(root, tmp_path / "chunks", ScanOptions())
    with patch("disk_treemap.scanner.os.scandir", side_effect=AssertionError("must not enumerate")):
        assert scanner.scan()["kind"] == "excluded"


def test_permission_failure_is_partial_not_fatal(tmp_path):
    scanner = Scanner(tmp_path, tmp_path / "chunks", ScanOptions())
    with patch("disk_treemap.scanner.os.scandir", side_effect=PermissionError):
        tree = scanner.scan()
    assert tree["partial"]
    assert scanner.stats.unreadable == 1


def test_links_are_counted_without_following_targets(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "not-scanned.txt").write_text("private")
    try:
        (root / "loop").symlink_to(root, target_is_directory=True)
        (root / "outside").symlink_to(outside, target_is_directory=True)
        (root / "broken").symlink_to(tmp_path / "missing")
    except OSError:
        pytest.skip("Creating symlinks requires additional privileges on this platform")
    scanner, tree = scan(root, tmp_path)
    assert scanner.stats.files == 3
    assert scanner.stats.directories == 1
    assert all(child["isSymlink"] for child in tree["children"])


def test_hard_links_count_bytes_once(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    first = root / "a.bin"
    first.write_bytes(b"hello")
    try:
        os.link(first, root / "b.bin")
    except OSError:
        pytest.skip("Hard links unavailable")
    scanner, tree = scan(root, tmp_path, size="logical")
    assert scanner.stats.files == 2
    assert scanner.stats.hard_links == 1
    assert tree["value"] == 5
    _, counted = scan(root, tmp_path, size="logical", count_hard_links=True)
    assert counted["value"] == 10


def test_chunks_preserve_all_children(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    for i in range(20):
        (root / f"file-{i}.txt").write_bytes(b"data")
    scanner, tree = scan(root, tmp_path, size="logical", chunk_size=3)
    assert scanner.chunks == 1
    assert tree["value"] == 80
    source = (tmp_path / "chunks" / (tree["chunkId"] + ".js")).read_text()
    payload = source.split(f"[{json.dumps(tree['chunkId'])}]=", 1)[1].removesuffix(";\n")
    assert len(json.loads(payload)) == 20


@pytest.mark.skipif(os.name == "nt", reason="Windows path length limits depend on OS settings")
def test_deep_tree_does_not_depend_on_python_recursion(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    current = root
    for _ in range(160):
        current /= "d"
        current.mkdir()
    (current / "leaf").write_bytes(b"x")
    scanner, tree = scan(root, tmp_path, chunk_size=5000)
    assert scanner.stats.directories == 161
    assert scanner.stats.files == 1
    assert scanner.chunks >= 3  # Bounded JSON depth, even below the node threshold.
    json.dumps(tree)


def test_one_file_system_does_not_descend_foreign_device(tmp_path):
    (tmp_path / "mount").mkdir()
    scanner = Scanner(tmp_path, tmp_path / "chunks", ScanOptions(one_file_system=True))
    scanner._root_device = -1  # No real mount or admin privileges needed.
    tree = scanner.scan()
    assert scanner.stats.directories == 1
    assert children(tree)["mount"]["reason"] == "Different filesystem"
