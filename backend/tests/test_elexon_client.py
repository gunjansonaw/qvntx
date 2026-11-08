"""Client tests with an in-process mock transport (no network)."""

import asyncio
from datetime import date

import httpx
import pytest

from app.elexon_client import ElexonClient, ElexonError

from .conftest import utc

FUEL_ROW = {
    "dataset": "FUELHH",
    "publishTime": "2026-01-02T00:30:00Z",
    "startTime": "2026-01-02T00:00:00Z",
    "settlementDate": "2026-01-02",
    "settlementPeriod": 1,
    "fuelType": "WIND",
    "generation": 15538,
}


def client_for(handler, **kwargs) -> ElexonClient:
    return ElexonClient("https://example.test/api", transport=httpx.MockTransport(handler), backoff_s=0, **kwargs)


def test_actuals_are_chunked_validated_and_filtered():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        rows = [FUEL_ROW, {**FUEL_ROW, "fuelType": "CCGT"}, {**FUEL_ROW, "generation": None}]
        return httpx.Response(200, json=rows)

    records = asyncio.run(
        client_for(handler, actuals_chunk_days=7).fetch_wind_actuals(date(2026, 1, 2), date(2026, 1, 15))
    )

    assert [c["settlementDateFrom"] for c in calls] == ["2026-01-02", "2026-01-09"]
    assert all(c["fuelType"] == "WIND" for c in calls)
    # one valid WIND row per chunk; CCGT and null-generation rows are dropped
    assert len(records) == 2 and records[0].generation == 15538.0


def test_forecasts_are_deduplicated_across_chunks_and_accept_wrapped_payloads():
    row = {"publishTime": "2026-01-01T07:30:00Z", "startTime": "2026-01-02T00:00:00Z", "generation": 19960}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [row]})

    records = asyncio.run(
        client_for(handler, forecasts_chunk_days=1).fetch_wind_forecasts(utc(2026, 1, 1), utc(2026, 1, 4))
    )
    assert len(records) == 1  # three chunks returned the same row


def test_retries_transient_errors_then_succeeds():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(503) if attempts["n"] < 3 else httpx.Response(200, json=[FUEL_ROW])

    records = asyncio.run(client_for(handler, retries=3).fetch_wind_actuals(date(2026, 1, 2), date(2026, 1, 2)))
    assert attempts["n"] == 3 and len(records) == 1


def test_client_errors_are_not_retried():
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(400, json={"error": "bad request"})

    with pytest.raises(ElexonError):
        asyncio.run(client_for(handler, retries=3).fetch_wind_actuals(date(2026, 1, 2), date(2026, 1, 2)))
    assert attempts["n"] == 1
