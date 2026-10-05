"""Tests for the promotion-policy script (.github/scripts/promotion.py)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "promotion.py"
spec = importlib.util.spec_from_file_location("promotion", SCRIPT)
assert spec is not None and spec.loader is not None
promotion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promotion)

REPO = "McIndi/recut"


@pytest.mark.parametrize(
    "base,head",
    [
        ("dev", "feature/x"),
        ("dev", "fix/package-discovery"),
        ("qa", "dev"),
        ("prod", "qa"),
        ("main", "prod"),
    ],
)
def test_allowed_routes(base: str, head: str) -> None:
    assert promotion.allowed(base, head, REPO, REPO)


@pytest.mark.parametrize(
    "base,head",
    [
        ("dev", "dev"),
        ("dev", "main"),
        ("dev", "feature/"),
        ("dev", "hotfix/x"),
        ("qa", "feature/x"),
        ("qa", "prod"),
        ("prod", "dev"),
        ("main", "qa"),
        ("main", "feature/x"),
        ("unknown", "dev"),
    ],
)
def test_rejected_routes(base: str, head: str) -> None:
    assert not promotion.allowed(base, head, REPO, REPO)


@pytest.mark.parametrize("head_repo", ["someone/recut", "", "McIndi/other"])
def test_fork_or_missing_head_repo_rejected(head_repo: str) -> None:
    assert not promotion.allowed("dev", "feature/x", head_repo, REPO)


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_script_exit_codes() -> None:
    assert run_script("dev", "feature/x", REPO, REPO).returncode == 0
    assert run_script("main", "feature/x", REPO, REPO).returncode == 1
    assert run_script("dev", "feature/x", "fork/recut", REPO).returncode == 1
    assert run_script("dev").returncode == 2
