# disk-treemap

[![CI](https://github.com/AnthonyDeniau/disk-treemap/actions/workflows/ci.yml/badge.svg)](https://github.com/AnthonyDeniau/disk-treemap/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Your filesystem, from the root folder down to individual files, in an offline HTML mosaic.**

```sh
uvx --from 'git+https://github.com/AnthonyDeniau/disk-treemap@v0.1.0' disk-treemap ~/Projects -o projects.html
```

Open `projects.html` in your browser. Click a rectangle for its path and size;
explore a folder to reveal smaller files. No server, account, telemetry or
internet connection is needed to generate or view a report after installation.

![Treemap generated from synthetic example data](docs/demo.png)

## Install

Requires **Python 3.10 or newer**. Node is only needed when developing the viewer.

With [uv](https://docs.astral.sh/uv/):

```sh
uv tool install 'git+https://github.com/AnthonyDeniau/disk-treemap@v0.1.0'
disk-treemap . -o report.html
```

With [pipx](https://pipx.pypa.io/):

```sh
pipx install 'git+https://github.com/AnthonyDeniau/disk-treemap@v0.1.0'
```

Or install a wheel from [Releases](https://github.com/AnthonyDeniau/disk-treemap/releases)
into a virtual environment. There are **no Python runtime dependencies**, and
the wheel already contains the built viewer. This project is not currently
published on PyPI; use the Git URL or release wheel above.

## Examples

```sh
# The current directory, including hidden files
disk-treemap . -o current.html

# Skip generated dependencies and build output (quote globs to avoid shell expansion)
disk-treemap ~/Projects -o code.html --exclude node_modules --exclude .venv --exclude .git

# Measure logical file length instead of allocated disk blocks
disk-treemap /path/to/data -o logical.html --size logical

# Stay on one filesystem and write a machine-readable summary
disk-treemap /path/to/volume -o volume.html --one-file-system --json

# Hide the absolute root path in the report; descendant names are still included
disk-treemap ~/Projects -o labelled.html --label 'Projects'
```

`--help` lists all options. Existing output files are never overwritten: use a new
filename for each snapshot. The output parent directory must already exist.

### Large scans

Small reports are one HTML file. Larger reports also create a neighboring
`disk-treemap-data-<id>/` directory. **Keep the HTML and this directory together**
when moving the report; both contain filesystem metadata. Open the HTML using
`file://` in a modern browser (Chromium, Firefox or Safari); no server is needed.
To delete a report, remove its HTML and its associated data directory.

The viewer loads detailed branches on demand. A tiny folder can initially be
shown as a single gray rectangle; explore it to see its files. Every recorded
entry remains in the data. Zero-size, excluded and unreadable entries have no
proportional area, but can be inspected in **Folder contents**. `--chunk-size`
controls the embedded subtree threshold; a single directory with many direct
children may produce a larger block. This is not a fixed-memory scanner or viewer.

### Navigation and accessibility

- Click a rectangle to inspect it. Use **Explore this folder** or **Zoom to parent folder**.
- Use the small back/root buttons after zooming.
- Press **Escape** to close details, then go up one level; **Backspace** also goes up.
- Keyboard: focus the canvas and press **Enter**, then browse **Folder contents**
  using standard controls. The list includes files too small to click on the canvas.
- The canvas itself does not expose a separate screen-reader element for every
  rectangle; folder contents provides the text alternative.

## What is measured

The scanner reads directory entries and file metadata, **not file contents**.
It does not delete, move, change permissions on, or upload scanned files. Its
only writes are the requested report and temporary output next to it.

| Behavior | Default |
| --- | --- |
| File weights | Allocated bytes, `st_blocks × 512`; falls back to logical bytes when unavailable |
| Hidden files | Included |
| Symbolic links | Recorded as links; their targets are not traversed |
| Hard links | All filenames recorded; bytes counted once per inode (override with `--count-hard-links`) |
| Unreadable or disappearing entries | Reported as partial, without aborting the whole scan |
| Credential stores | macOS `Library/Keychains` and `.keychain` / `.keychain-db` entries excluded |
| macOS cloud-provider roots | `Library/Mobile Documents` and `Library/CloudStorage` excluded to avoid hydration or stalls |
| Known virtual/mount roots | `/dev`, `/proc`, `/sys`, `/run`, `/Volumes`, `/Network`, `/System/Volumes`, simulator mount directory excluded |

Other mount points are not automatically classified as local or remote: use
`--one-file-system` when required. An explicitly selected folder inside a
mounted volume can be scanned normally. On macOS, scanning `/` with
`--one-file-system` can omit the separate Data volume; select the desired data
volume directly, or leave that option off.

`--exclude` is a repeatable, case-sensitive Python-style glob, **not** a Gitignore
parser. Patterns without `/` match entry names anywhere; patterns with `/` match
relative POSIX-style paths. An excluded directory is not descended into.

### Limits and platform notes

- APFS clones, compressed/shared blocks, snapshots, filesystem overhead and
  OS storage categories do not have a one-to-one relationship with file totals.
  This is not Apple's private “System Data” classification or a byte-perfect `df` replacement.
- Sparse files use their allocated blocks in the default mode, rather than their
  potentially enormous logical size. On Windows, allocated size may fall back
  to logical size; the summary includes `allocated_fallbacks`.
- Reports are snapshots of a **live filesystem**, not atomic volume snapshots.
  Concurrent changes may be missed or produce partial entries. Avoid scanning
  an actively modified, adversarial tree with elevated privileges.
- macOS privacy protections can hide some folders. Grant the invoking terminal
  Full Disk Access if appropriate. Do not use `sudo` by default: choose the
  smallest useful scan root first.
- CLI tests run on macOS, Linux and Windows. Browser tests run in Chromium,
  Firefox and WebKit, including offline loading through `file://`.

## Privacy and security

**Reports include filenames, folder names, paths and sizes. Treat them as private.**
No file contents are copied, but metadata can still reveal sensitive information.
`--label` only replaces the root path; it is not full anonymization.

Report output is private to its owner on POSIX systems (HTML/data files `0600`,
data directories `0700`). The viewer has no network dependency, uses a restrictive
Content Security Policy, and treats filenames as text. No real scan, personal
path, credential or machine inventory is included in this repository. The
screenshot and built-in demo are generated entirely from synthetic data.

For security reports, see [SECURITY.md](SECURITY.md).

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Report created; may include excluded/unreadable entries |
| `1` | Scan/output error, or unreadable entries with `--strict` (partial report still written) |
| `2` | Invalid command-line arguments |
| `130` | Interrupted; this run's incomplete output cleaned up |

## Develop

```sh
git clone https://github.com/AnthonyDeniau/disk-treemap.git
cd disk-treemap
npm ci                         # Node >= 22.12
npm run build                  # rebuild the bundled offline viewer
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
npm test
npx playwright install chromium
npm run test:e2e
uv build
uv run twine check dist/*.whl dist/*.tar.gz
```

`npm run dev` previews synthetic data only. The development config relaxes CSP
for the local development server; exported reports always keep the restrictive
offline policy. See [CONTRIBUTING.md](CONTRIBUTING.md) for the release, privacy
and contribution checks.

## License

[MIT](LICENSE). Bundled viewer dependencies retain their original licenses in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
