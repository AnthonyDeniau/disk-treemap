"""Fail if tracked files contain real reports, machine paths or common secret formats."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_HTML = {"web/index.html", "src/disk_treemap/assets/viewer.html"}
FORBIDDEN_PARTS = {"node_modules", ".venv", ".env", ".codex", ".cache", "reports"}
PATTERNS = {
    "absolute macOS home path": re.compile("/" + r"Users/[^\s/\"'<>]+/"),
    "absolute Linux home path": re.compile("/" + r"home/[^\s/\"'<>]+/"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"),
    "API secret": re.compile(
        r"(?<![A-Za-z0-9_-])sk-(?:(?:proj|ant)-[A-Za-z0-9_-]{20,}|[A-Za-z0-9]{32,})"
    ),
    "private key": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
}


def main() -> int:
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).split(b"\0")
    failures = []
    for entry in tracked:
        if not entry:
            continue
        relative = entry.decode("utf-8")
        path = ROOT / relative
        if not path.is_file():
            continue
        parts = set(Path(relative).parts)
        if parts & FORBIDDEN_PARTS or "disk-treemap-data-" in relative:
            failures.append(relative + ": private/generated path")
        if path.suffix == ".html" and relative not in ALLOWED_HTML:
            failures.append(relative + ": unexpected HTML report")
        if path.suffix in {".pem", ".key", ".p8"} or path.name.startswith(".env"):
            failures.append(relative + ": credential-like filename")
        if path.suffix == ".png":
            if relative != "docs/demo.png":
                failures.append(relative + ": undocumented binary artifact")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            failures.append(relative + ": unexpected binary artifact")
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                failures.append(relative + ": " + label)
        if relative == "src/disk_treemap/assets/viewer.html":
            if not re.search(r'window\.__TREE_DATA__\s*=\s*"__TREE_DATA__"', text):
                failures.append(relative + ": data placeholder missing (possible real scan)")
    if failures:
        print("Public-content check FAILED:\n" + "\n".join(failures))
        return 1
    print(f"Public-content check passed for {sum(bool(p) for p in tracked)} tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
