"""Live-first loading: Elexon is always tried first; cache/snapshot only on failure."""

import asyncio
from dataclasses import replace

import pytest

from app.config import Settings
from app.domain import ActualRecord, ForecastRecord
from app.elexon_client import ElexonError
from app.repository import DataUnavailableError, WindDataRepository

from .conftest import utc


class FakeClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def fetch_wind_actuals(self, first, last):
        self.calls += 1
        if self.fail:
            raise ElexonError("boom")
        return [ActualRecord(utc(2026, 1, 2), utc(2026, 1, 2, 0, 30), 1000.0)]

    async def fetch_wind_forecasts(self, publish_from, publish_to):
        if self.fail:
            raise ElexonError("boom")
        return [ForecastRecord(utc(2026, 1, 1, 7, 30), utc(2026, 1, 2), 1200.0)]


@pytest.fixture
def live_settings(tmp_path) -> Settings:
    return Settings(data_mode="live", cache_dir=tmp_path / "cache")


def load(settings, client):
    repo = WindDataRepository(settings, client=client)
    return repo, asyncio.run(repo.analytics()).dataset


def test_every_start_fetches_live_even_when_a_cache_exists(live_settings):
    client = FakeClient()
    _, first = load(live_settings, client)
    _, second = load(live_settings, client)  # simulates an app restart
    assert first.source == second.source == "live"
    assert client.calls == 2


def test_dataset_is_held_in_memory_within_a_process(live_settings):
    client = FakeClient()
    repo = WindDataRepository(live_settings, client=client)

    async def two_requests():
        await repo.analytics()
        await repo.analytics()

    asyncio.run(two_requests())
    assert client.calls == 1


def test_last_good_live_fetch_is_the_first_fallback(live_settings):
    load(live_settings, FakeClient())  # successful live fetch writes the disk cache
    repo, dataset = load(live_settings, FakeClient(fail=True))
    assert dataset.source == "disk-cache"
    assert "boom" in repo.last_error


def test_bundled_snapshot_is_the_last_resort(live_settings):
    _, dataset = load(live_settings, FakeClient(fail=True))
    assert dataset.source == "snapshot"
    assert len(dataset.actuals) == 31 * 48  # 2 Jan .. 1 Feb


def test_refresh_switches_back_to_live_when_elexon_recovers(live_settings):
    client = FakeClient(fail=True)
    repo = WindDataRepository(live_settings, client=client)

    async def scenario():
        assert (await repo.analytics()).dataset.source == "snapshot"
        client.fail = False
        return await repo.refresh()

    assert asyncio.run(scenario()).source == "live"


def test_failed_refresh_keeps_serving_current_data(live_settings):
    client = FakeClient()
    repo = WindDataRepository(live_settings, client=client)

    async def scenario():
        await repo.analytics()
        client.fail = True
        return await repo.refresh()

    assert asyncio.run(scenario()).source == "live"
    assert "boom" in repo.last_error


def test_no_source_at_all_raises(live_settings, tmp_path):
    settings = replace(live_settings, snapshot_path=tmp_path / "missing.json.gz")
    with pytest.raises(DataUnavailableError):
        load(settings, FakeClient(fail=True))
