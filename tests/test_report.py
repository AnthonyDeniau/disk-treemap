from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from disk_treemap.cli import main
from disk_treemap.report import generate_report, inline_json
from disk_treemap.scanner import ScanOptions


def embedded(path: Path):
    html = path.read_text(encoding="utf-8")
    marker = "window.__TREE_DATA__ = "
    start = html.index(marker) + len(marker)
    end = html.index(";\n", start)
    return json.loads(html[start:end])


def fixture(tmp_path):
    root = tmp_path / "input"
    root.mkdir()
    (root / "hello.txt").write_bytes(b"hello")
    return root


def test_report_runs_with_packaged_viewer_and_no_node(tmp_path):
    root = fixture(tmp_path)
    output = tmp_path / "report.html"
    summary = generate_report(root, output, ScanOptions(size="logical"))
    assert summary["bytes"] == 5
    assert summary["files"] == 1
    assert embedded(output)["children"][0]["name"] == "hello.txt"
    assert '__TREE_DATA__"' not in output.read_text(encoding="utf-8")
    if os.name != "nt":
        assert output.stat().st_mode & 0o777 == 0o600


def test_existing_output_is_preserved(tmp_path):
    root = fixture(tmp_path)
    output = tmp_path / "report.html"
    output.write_bytes(b"do not overwrite")
    with pytest.raises(FileExistsError):
        generate_report(root, output, ScanOptions())
    assert output.read_bytes() == b"do not overwrite"


def test_failed_or_cancelled_scan_cleans_only_its_own_output(tmp_path):
    root = fixture(tmp_path)
    for failure in (OSError("disk full"), KeyboardInterrupt()):
        with patch("disk_treemap.report.Scanner.scan", side_effect=failure):
            with pytest.raises(type(failure)):
                generate_report(root, tmp_path / "report.html", ScanOptions())
        assert not (tmp_path / "report.html").exists()
        assert not list(tmp_path.glob(".disk-treemap-build-*"))
        assert (root / "hello.txt").read_bytes() == b"hello"


def test_atomic_publish_failure_removes_new_assets(tmp_path):
    root = fixture(tmp_path)
    with patch("disk_treemap.report.os.replace", side_effect=OSError("publish failed")):
        with pytest.raises(OSError):
            generate_report(root, tmp_path / "report.html", ScanOptions(chunk_size=1))
    assert not list(tmp_path.glob("disk-treemap-data-*"))
    assert not (tmp_path / "report.html").exists()


def test_existing_assets_are_never_deleted_on_a_name_collision(tmp_path):
    from types import SimpleNamespace

    root = fixture(tmp_path)
    existing = tmp_path / ("disk-treemap-data-" + "a" * 12)
    existing.mkdir()
    (existing / "user-data.txt").write_text("keep me")
    with patch("disk_treemap.report.uuid.uuid4", return_value=SimpleNamespace(hex="a" * 32)):
        with pytest.raises(OSError, match="data folder already exists"):
            generate_report(root, tmp_path / "report.html", ScanOptions(chunk_size=1))
    assert (existing / "user-data.txt").read_text() == "keep me"
    assert not (tmp_path / "report.html").exists()


def test_signal_after_atomic_publish_preserves_the_complete_report(tmp_path):
    root = fixture(tmp_path)
    output = tmp_path / "report.html"
    original_replace = os.replace

    def publish_then_interrupt(source, destination):
        original_replace(source, destination)
        raise KeyboardInterrupt

    with patch("disk_treemap.report.os.replace", side_effect=publish_then_interrupt):
        with pytest.raises(KeyboardInterrupt):
            generate_report(root, output, ScanOptions(chunk_size=1))
    assert output.is_file()
    assert list(tmp_path.glob("disk-treemap-data-*/c0000001.js"))


def test_output_symlink_is_not_followed_or_overwritten(tmp_path):
    root = fixture(tmp_path)
    target = tmp_path / "important.txt"
    target.write_text("keep")
    output = tmp_path / "report.html"
    try:
        output.symlink_to(target)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(FileExistsError):
        generate_report(root, output, ScanOptions())
    assert target.read_text() == "keep"


def test_changed_output_is_never_removed_or_overwritten(tmp_path):
    root = fixture(tmp_path)
    output = tmp_path / "report.html"
    from disk_treemap.scanner import Scanner

    original = Scanner.scan

    def change_output(scanner):
        output.write_text("somebody else's data")
        return original(scanner)

    with patch("disk_treemap.report.Scanner.scan", change_output):
        with pytest.raises(OSError, match="output changed"):
            generate_report(root, output, ScanOptions())
    assert output.read_text() == "somebody else's data"


def test_output_inside_scan_root_does_not_scan_itself(tmp_path):
    root = fixture(tmp_path)
    output = root / "report.html"
    summary = generate_report(root, output, ScanOptions(size="logical", chunk_size=1))
    assert summary["files"] == 1
    assert summary["bytes"] == 5
    assert summary["chunks"] == 1
    assert (root / summary["chunkDirectory"]).is_dir()


def test_alias_output_parent_is_normalized(tmp_path):
    root = fixture(tmp_path)
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(root, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    summary = generate_report(
        root, alias / "report.html", ScanOptions(size="logical", chunk_size=1)
    )
    assert summary["files"] == 1
    assert summary["bytes"] == 5


def test_json_cannot_close_script_tag():
    payload = {"name": '</script><script>alert("x")</script>\u2028&'}
    encoded = inline_json(payload)
    assert "<" not in encoded
    assert "\u2028" not in encoded
    assert json.loads(encoded) == payload


def test_cli_json_summary_and_label(tmp_path, capsys):
    root = fixture(tmp_path)
    output = tmp_path / "report with spaces.html"
    label = "</script><script>window.unwanted=true</script>"
    assert main([str(root), "-o", str(output), "--json", "--label", label]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["root"] == label
    assert embedded(output)["name"] == label
    assert "<script>window.unwanted" not in output.read_text(encoding="utf-8")


def test_cli_errors_do_not_create_files(tmp_path, capsys):
    assert main([str(tmp_path / "missing"), "-o", str(tmp_path / "r.html")]) == 1
    assert not (tmp_path / "r.html").exists()
    assert "disk-treemap:" in capsys.readouterr().err
    with pytest.raises(SystemExit) as error:
        main(["--chunk-size", "0"])
    assert error.value.code == 2


def test_strict_writes_partial_report_but_returns_failure(tmp_path, capsys):
    output = tmp_path / "report.html"
    original_scandir = os.scandir

    def deny_root(path):
        if not isinstance(path, int) and Path(path) == tmp_path:
            raise PermissionError
        return original_scandir(path)

    with patch("disk_treemap.scanner.os.scandir", side_effect=deny_root):
        assert main([str(tmp_path), "-o", str(output), "--strict", "--json"]) == 1
    assert output.is_file()
    assert json.loads(capsys.readouterr().out)["unreadable"] == 1


def test_quiet_and_module_entry_point(tmp_path, capsys):
    root = fixture(tmp_path)
    assert main([str(root), "-o", str(tmp_path / "report.html"), "--quiet"]) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("output", ["report.json", "report", "missing-parent/report.html"])
def test_invalid_output(tmp_path, output):
    root = fixture(tmp_path)
    with pytest.raises((OSError, ValueError)):
        generate_report(root, tmp_path / output, ScanOptions())
