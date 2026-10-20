from pathlib import Path
from runpy import run_path


def test_secret_check_does_not_confuse_the_project_name_with_a_token():
    checks = run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "check_public.py"))
    pattern = checks["PATTERNS"]["API secret"]
    assert pattern.search("disk-treemap-data-000000000000") is None
    assert pattern.search("sk-" + "proj-" + "a" * 30)
    assert pattern.search("sk-" + "a" * 48)
