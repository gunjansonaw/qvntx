"""The root requirements.txt (Vercel) must pin exactly what backend/requirements.txt pins."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _pins(path: Path) -> set[str]:
    lines = (line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines())
    return {line for line in lines if line}


@pytest.mark.skipif(not (REPO_ROOT / "requirements.txt").exists(), reason="repo root not available")
def test_vercel_requirements_match_backend():
    assert _pins(REPO_ROOT / "requirements.txt") == _pins(REPO_ROOT / "backend" / "requirements.txt")
