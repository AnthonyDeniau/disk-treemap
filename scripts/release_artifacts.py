"""Normalize distribution headers, check their content, and create SHA256SUMS."""

from __future__ import annotations

import copy
import gzip
import hashlib
import io
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from check_public import PATTERNS


def check_member(name: str, content: bytes | None) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe archive path: " + name)
    if content is None or name.endswith("/docs/demo.png"):
        return
    text = content.decode("utf-8")
    for label, pattern in PATTERNS.items():
        if pattern.search(text):
            raise ValueError(f"{name}: {label}")
    if name.endswith(".html") and not name.endswith(("assets/viewer.html", "web/index.html")):
        raise ValueError("Unexpected HTML in distribution: " + name)
    if name.endswith("assets/viewer.html") and '"__TREE_DATA__"' not in text:
        raise ValueError("Packaged template contains real data or is missing its placeholder")


def normalize_sdist(path: Path) -> None:
    buffer = io.BytesIO()
    with tarfile.open(path, "r:gz") as source:
        with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as target:
                for original in sorted(source.getmembers(), key=lambda member: member.name):
                    if not (original.isfile() or original.isdir()):
                        raise ValueError("Unexpected archive member type: " + original.name)
                    reader = source.extractfile(original) if original.isfile() else None
                    content = reader.read() if reader is not None else None
                    check_member(original.name, content)
                    member = copy.copy(original)
                    member.uid = member.gid = 0
                    member.uname = member.gname = ""
                    member.mtime = 0
                    member.mode = 0o755 if member.isdir() else 0o644
                    member.pax_headers = {}
                    target.addfile(member, io.BytesIO(content) if content is not None else None)
    path.write_bytes(buffer.getvalue())


def normalize_wheel(path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(path) as source:
        with zipfile.ZipFile(
            buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as target:
            for name in sorted(source.namelist()):
                content = source.read(name)
                check_member(name, content)
                member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                member.create_system = 3
                member.external_attr = 0o100644 << 16
                member.compress_type = zipfile.ZIP_DEFLATED
                target.writestr(member, content)
    path.write_bytes(buffer.getvalue())


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "dist"
    archives = sorted([*root.glob("*.whl"), *root.glob("*.tar.gz")])
    if not archives:
        raise SystemExit("No distribution archives; run uv build first")
    for archive in archives:
        if archive.suffix == ".whl":
            normalize_wheel(archive)
        else:
            normalize_sdist(archive)
    checksums = "".join(
        hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n"
        for archive in archives
    )
    (root / "SHA256SUMS").write_text(checksums, encoding="ascii")
    print("Normalized and privacy-checked " + str(len(archives)) + " archives; wrote SHA256SUMS.")


if __name__ == "__main__":
    main()
