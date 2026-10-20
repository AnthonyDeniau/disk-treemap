# Contributing

Small, focused issues and pull requests are welcome. Include a synthetic
reproduction and describe the expected behavior. Never submit a real disk scan,
private path, credential, machine inventory or personal screenshot.

Use Python 3.10+ and Node 22.12+. Follow the development commands in the README.
Python is formatted/linted with Ruff; TypeScript and CSS with Prettier. Test any
scanner change against links, sparse files, permission failures, unusual names,
deep trees, cancellation and existing output protection. Scanner code must not
read file contents or modify scanned entries.

The checked-in `src/disk_treemap/assets/viewer.html` is built from `web/`.
Run `npm run build` after viewer changes and include the regenerated template.
The placeholders in this file must remain placeholders; never substitute a real
tree before committing it. The Python package includes this template so users
do not need Node to install from Git or from a wheel.

## Dependency updates

Dependabot checks npm and uv weekly, and GitHub Actions monthly. Python updates
use the native uv ecosystem so `pyproject.toml` and `uv.lock` stay consistent.
Minor and patch updates are grouped; major updates remain separate and require
manual review. This also applies to pre-1.0 minor updates, which can break APIs:
the full test suite must still pass, but tests cannot prove compatibility.

The auto-merge workflow only accepts same-repository PRs authored by
`dependabot[bot]`, reads their verified update metadata and enables GitHub's
native squash auto-merge for minor/patch updates. It never checks out PR code
with write permissions. Major or unclassified updates are not auto-merged.

Repository settings must enable auto-merge and protect `main` with the required
`All checks` status from GitHub Actions, with branches up to date before merging.
That status requires every Python/platform job and the viewer job to succeed;
failed, skipped or cancelled test jobs block merging. Administrators are also
subject to protection. A dependency change that changes the bundled viewer must
include a rebuilt template; the reproducibility check will block it otherwise.

## Release checklist

1. Run all CLI/layout/browser tests, `npm audit`, Ruff, Prettier and `twine check`.
2. Rebuild the viewer and confirm the working tree has no unexpected generated changes.
3. Build wheel and sdist, run `uv run python scripts/release_artifacts.py` to remove
   machine account metadata and generate checksums, inspect their file lists,
   and install/run the wheel in a clean environment.
4. Run `python scripts/check_public.py` and inspect the staged diff and `git diff --cached --check`.
5. Publish only source, the generic viewer, synthetic docs and the tested distribution artifacts.
   Check that version strings, README install instructions and tag agree.

Do not change the no-overwrite behavior or automatic exclusions without adding
regression tests and documenting the effect. Never add automatic deletion of
scanned files to the viewer.
