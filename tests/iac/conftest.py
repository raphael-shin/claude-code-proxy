from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def iac_snapshot_dir() -> Path:
    return Path(__file__).resolve().parent / "snapshots"
