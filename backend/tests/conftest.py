"""Shared fixtures. Tests never touch the network: API tests use the bundled snapshot."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.domain import ForecastArchive, ForecastRun, WindDataset  # noqa: E402
from app.main import create_app  # noqa: E402


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def make_run(publish: datetime, start: datetime, values: list[float]) -> ForecastRun:
    """Hourly run beginning at ``start``."""
    return ForecastRun(publish, {start + timedelta(hours=i): v for i, v in enumerate(values)})


def make_dataset(actuals: dict[datetime, float], runs: list[ForecastRun]) -> WindDataset:
    return WindDataset(actuals=actuals, forecasts=ForecastArchive(runs), source="test", retrieved_at=utc(2026, 2, 2))


@pytest.fixture(scope="module")
def snapshot_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    return Settings(data_mode="snapshot", cache_dir=tmp_path_factory.mktemp("cache"), admin_token="secret-token")


@pytest.fixture(scope="module")
def client(snapshot_settings: Settings) -> Iterator[TestClient]:
    """One app per test module: the dataset is immutable, so sharing is safe and fast."""
    with TestClient(create_app(snapshot_settings)) as test_client:
        yield test_client
