"""Data access: live-first, with fallback caching.

Load order in ``live`` mode (first success wins):

1. Elexon live API      - always tried first when the app starts (or on refresh).
                          A successful fetch is kept in memory for the process
                          lifetime and also written to the disk cache.
2. disk cache           - the last successful live fetch; used ONLY if Elexon fails.
3. bundled snapshot     - same Elexon FUELHH/WINDFOR data, committed with the repo;
                          used ONLY if Elexon fails and there is no disk cache,
                          so a demo never breaks.

While serving fallback data the repository keeps retrying Elexon in the background
(at most every ``LIVE_RETRY_SECONDS``) and switches to live data as soon as it can.
The data source is always reported to the UI (``/api/health``, ``/api/meta``).

``snapshot`` mode skips the network entirely - useful offline and in CI/tests.
"""

from __future__ import annotations

import asyncio
import logging
import time as clock
from datetime import UTC, datetime, time, timedelta

from .analytics import WindAnalytics
from .config import Settings
from .domain import ForecastArchive, ForecastRun, WindDataset, build_actuals, build_runs
from .elexon_client import ElexonClient, ElexonError
from .snapshot import read_snapshot, write_snapshot

log = logging.getLogger(__name__)

CACHE_FILE_NAME = "elexon_wind_cache.json.gz"
# Forecasts are fetched from a few days before the first delivery day so that
# long-lead (up to 48 h) and early-gate policies still find a visible run.
FORECAST_LOOKBACK = timedelta(days=3)
LIVE_RETRY_SECONDS = 300


class DataUnavailableError(RuntimeError):
    """No data source (live, cache or snapshot) could be loaded."""


class WindDataRepository:
    def __init__(self, settings: Settings, client: ElexonClient | None = None) -> None:
        self._settings = settings
        self._client = client or ElexonClient(
            settings.elexon_base_url,
            timeout_s=settings.http_timeout_s,
            retries=settings.http_retries,
        )
        self._lock = asyncio.Lock()
        self._analytics: WindAnalytics | None = None
        self._last_live_attempt = float("-inf")
        self._retry_task: asyncio.Task | None = None
        self.last_error: str | None = None

    @property
    def cache_path(self):
        return self._settings.cache_dir / CACHE_FILE_NAME

    @property
    def loaded_dataset(self) -> WindDataset | None:
        """The dataset if already loaded - never triggers I/O."""
        return self._analytics.dataset if self._analytics else None

    async def analytics(self) -> WindAnalytics:
        """Analytics over the current dataset, loading it (live first) on first use."""
        if self._analytics is None:
            async with self._lock:  # one loader at a time; others wait for its result
                if self._analytics is None:
                    self._analytics = WindAnalytics(await self._load())
        elif self._analytics.dataset.source != "live" and self._settings.data_mode == "live":
            self._schedule_live_retry()
        return self._analytics

    async def refresh(self) -> WindDataset:
        """Force a live re-fetch. If Elexon fails, keep serving the current dataset."""
        async with self._lock:
            if self._analytics is None:
                self._analytics = WindAnalytics(await self._load())
                return self._analytics.dataset
            try:
                self._analytics = WindAnalytics(await self._from_live())
            except ElexonError as exc:
                self.last_error = str(exc)
                log.error("Live refresh failed; keeping %s data: %s", self._analytics.dataset.source, exc)
            return self._analytics.dataset

    # -- loading strategy ------------------------------------------------

    async def _load(self) -> WindDataset:
        if self._settings.data_mode == "snapshot":
            return self._from_snapshot()

        try:
            return await self._from_live()
        except ElexonError as exc:
            self.last_error = str(exc)
            log.error("Live Elexon fetch failed, using fallback data: %s", exc)

        if self.cache_path.exists():
            try:
                return self._from_file(self.cache_path, source="disk-cache")
            except Exception as exc:  # corrupt cache: fall through to the snapshot
                log.warning("Disk cache unreadable: %s", exc)
        return self._from_snapshot()

    async def _from_live(self) -> WindDataset:
        self._last_live_attempt = clock.monotonic()
        first_day, last_day = self._settings.delivery_days
        publish_from = datetime.combine(first_day, time(0), tzinfo=UTC) - FORECAST_LOOKBACK
        publish_to = datetime.combine(last_day + timedelta(days=1), time(0), tzinfo=UTC)

        started = clock.perf_counter()
        actual_records, forecast_records = await asyncio.gather(
            self._client.fetch_wind_actuals(first_day, last_day),
            self._client.fetch_wind_forecasts(publish_from, publish_to),
        )
        actuals = build_actuals(actual_records)
        runs = build_runs(forecast_records)
        if not actuals or not runs:
            raise ElexonError("Elexon returned no wind data for the configured window")
        log.info(
            "Fetched %d actuals and %d forecast runs live from Elexon in %.1fs",
            len(actuals), len(runs), clock.perf_counter() - started,
        )  # fmt: skip

        try:  # keep the last good live fetch as a fallback for future outages
            write_snapshot(self.cache_path, actuals, runs)
        except OSError as exc:  # read-only FS etc. - caching is best effort
            log.warning("Could not write cache %s: %s", self.cache_path, exc)
        self.last_error = None
        return _dataset(actuals, runs, source="live", retrieved_at=datetime.now(UTC))

    def _schedule_live_retry(self) -> None:
        """While on fallback data, retry Elexon in the background (rate-limited)."""
        if self._retry_task and not self._retry_task.done():
            return
        if clock.monotonic() - self._last_live_attempt < LIVE_RETRY_SECONDS:
            return
        self._retry_task = asyncio.create_task(self.refresh())

    def _from_snapshot(self) -> WindDataset:
        path = self._settings.snapshot_path
        if not path.exists():
            raise DataUnavailableError(f"No data available: live fetch failed and snapshot {path} is missing")
        return self._from_file(path, source="snapshot")

    @staticmethod
    def _from_file(path, source: str) -> WindDataset:
        contents = read_snapshot(path)
        return _dataset(contents.actuals, contents.runs, source=source, retrieved_at=contents.written_at)


def _dataset(actuals, runs: list[ForecastRun], source: str, retrieved_at: datetime) -> WindDataset:
    return WindDataset(
        actuals=actuals,
        forecasts=ForecastArchive(runs),
        source=source,
        retrieved_at=retrieved_at,
    )
