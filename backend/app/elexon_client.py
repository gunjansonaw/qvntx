"""Async client for the Elexon BMRS Insights API (no API key required).

Large ranges are split into bounded chunks that are fetched concurrently, each with
timeouts and exponential-backoff retries. Rows are validated individually so one
malformed record cannot poison a whole payload.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError

from .domain import ActualRecord, ForecastRecord

log = logging.getLogger(__name__)

FUELHH_STREAM = "/datasets/FUELHH/stream"
WINDFOR_STREAM = "/datasets/WINDFOR/stream"
WIND_FUEL_TYPE = "WIND"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ElexonError(RuntimeError):
    """Raised when Elexon cannot be reached or returns an unusable response."""


class _FuelHHRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    startTime: AwareDatetime
    publishTime: AwareDatetime
    fuelType: str
    generation: float


class _WindForRow(BaseModel):
    model_config = ConfigDict(extra="ignore")
    startTime: AwareDatetime
    publishTime: AwareDatetime
    generation: float


class ElexonClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 30.0,
        retries: int = 3,
        max_concurrency: int = 4,
        actuals_chunk_days: int = 7,
        forecasts_chunk_days: int = 7,
        transport: httpx.AsyncBaseTransport | None = None,  # injectable for tests
        backoff_s: float = 0.5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s
        self._retries = retries
        self._max_concurrency = max_concurrency
        self._actuals_chunk = timedelta(days=actuals_chunk_days)
        self._forecasts_chunk = timedelta(days=forecasts_chunk_days)
        self._transport = transport
        self._backoff_s = backoff_s

    # -- public API ----------------------------------------------------------

    async def fetch_wind_actuals(self, first_day: date, last_day: date) -> list[ActualRecord]:
        """Half-hourly wind outturn (FUELHH) for settlement days first..last inclusive."""
        windows = [
            {
                "settlementDateFrom": start.isoformat(),
                "settlementDateTo": end.isoformat(),
                "fuelType": WIND_FUEL_TYPE,
            }
            for start, end in _day_chunks(first_day, last_day, self._actuals_chunk)
        ]
        rows = await self._fetch_all(FUELHH_STREAM, windows)
        records = []
        for row in _validated(rows, _FuelHHRow):
            if row.fuelType.upper() == WIND_FUEL_TYPE:
                records.append(ActualRecord(row.startTime, row.publishTime, row.generation))
        return records

    async def fetch_wind_forecasts(self, publish_from: datetime, publish_to: datetime) -> list[ForecastRecord]:
        """All WINDFOR rows published within [publish_from, publish_to)."""
        windows = [
            {"publishDateTimeFrom": _iso_z(start), "publishDateTimeTo": _iso_z(end)}
            for start, end in _time_chunks(publish_from, publish_to, self._forecasts_chunk)
        ]
        rows = await self._fetch_all(WINDFOR_STREAM, windows)
        unique = {
            (row.publishTime, row.startTime): ForecastRecord(row.publishTime, row.startTime, row.generation)
            for row in _validated(rows, _WindForRow)
        }
        return list(unique.values())

    # -- transport ---------------------------------------------------------

    async def _fetch_all(self, path: str, windows: list[dict[str, str]]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
            headers={"Accept": "application/json", "User-Agent": "wind-desk/1.0"},
        ) as client:
            # Created per call so the semaphore is bound to the running event loop.
            semaphore = asyncio.Semaphore(self._max_concurrency)
            chunks = await asyncio.gather(*(self._get_rows(client, semaphore, path, params) for params in windows))
        return [row for chunk in chunks for row in chunk]

    async def _get_rows(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        path: str,
        params: dict[str, str],
    ) -> list[dict[str, Any]]:
        async with semaphore:
            for attempt in range(self._retries + 1):
                try:
                    response = await client.get(path, params=params)
                    if response.status_code in RETRYABLE_STATUS:
                        raise httpx.HTTPStatusError(
                            f"retryable status {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                    response.raise_for_status()
                    return _extract_rows(response.json())
                except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                    retryable = not isinstance(exc, httpx.HTTPStatusError) or (
                        exc.response.status_code in RETRYABLE_STATUS
                    )
                    if not retryable or attempt == self._retries:
                        raise ElexonError(f"GET {path} {params} failed: {exc}") from exc
                    delay = self._backoff_s * 2**attempt
                    log.warning("Elexon %s failed (%s); retry %d in %.1fs", path, exc, attempt + 1, delay)
                    await asyncio.sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    """Stream endpoints return a bare list; non-stream ones wrap it in {"data": [...]}."""
    if isinstance(payload, dict):
        payload = payload.get("data", [])
    if not isinstance(payload, list):
        raise ValueError(f"unexpected payload type {type(payload).__name__}")
    return payload


def _validated(rows: list[dict[str, Any]], model: type[BaseModel]) -> Iterator[Any]:
    rejected = 0
    for row in rows:
        try:
            yield model.model_validate(row)
        except ValidationError:
            rejected += 1
    if rejected:
        log.warning("Dropped %d malformed %s rows out of %d", rejected, model.__name__, len(rows))


def _day_chunks(first: date, last: date, size: timedelta) -> Iterator[tuple[date, date]]:
    """Inclusive day windows covering first..last."""
    start = first
    while start <= last:
        end = min(start + size - timedelta(days=1), last)
        yield start, end
        start = end + timedelta(days=1)


def _time_chunks(start: datetime, end: datetime, size: timedelta) -> Iterator[tuple[datetime, datetime]]:
    """Contiguous windows covering [start, end). Overlap at edges is de-duplicated later."""
    cursor = start
    while cursor < end:
        upper = min(cursor + size, end)
        yield cursor, upper
        cursor = upper


def _iso_z(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")
