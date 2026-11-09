"""API contract tests against the bundled January 2026 snapshot."""

import pytest

PERIODS = 31 * 48  # delivery days 2 Jan .. 1 Feb 2026


def test_health_does_not_require_data(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["dataMode"] == "snapshot"


def test_docs_are_served_under_api_prefix(client):
    # Only /api/* reaches the backend behind Vite, nginx and Vercel, so the docs must live there.
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/openapi.json").json()["info"]["title"] == "Wind Desk API"


def test_meta_describes_window_and_provenance(client):
    body = client.get("/api/meta").json()
    assert body["decisionDays"] == {"firstDay": "2026-01-01", "lastDay": "2026-01-31"}
    assert body["deliveryDays"] == {"firstDay": "2026-01-02", "lastDay": "2026-02-01"}
    assert {p["gate"] for p in body["presets"]} == {"09:20", "09:50"}
    assert body["dataset"]["source"] == "snapshot"
    assert body["dataset"]["actualPeriods"] == PERIODS


def test_series_day_ahead_default(client):
    body = client.get("/api/series").json()
    assert body["policy"]["mode"] == "dayahead" and body["policy"]["gate"] == "09:20"
    points = body["points"]
    assert len(points) == PERIODS
    first = points[0]
    assert first["time"] == "2026-01-02T00:00:00Z"
    assert first["publishTime"] == "2026-01-01T07:30:00Z"  # latest run before 09:20 on D-1
    assert first["error"] == pytest.approx(first["forecast"] - first["actual"])
    assert first["p10"] <= first["p50"] <= first["p90"]
    assert body["summary"]["coverage"] == 1.0
    assert body["band"]["buckets"]


def test_later_gate_sees_later_run(client):
    body = client.get("/api/series", params={"gate": "09:50", "start": "2026-01-10", "end": "2026-01-10"}).json()
    assert len(body["points"]) == 48
    assert {p["publishTime"] for p in body["points"]} == {"2026-01-09T09:30:00Z"}


def test_fixed_lead_mode_respects_lead(client):
    body = client.get("/api/series", params={"mode": "lead", "lead": 6}).json()
    assert body["policy"] == {
        "mode": "lead",
        "gate": None,
        "leadHours": 6.0,
        "description": "Latest forecast published at least 6 h before each period",
    }
    assert all(p["leadHours"] >= 6 for p in body["points"] if p["leadHours"] is not None)


def test_evaluation_breakdowns(client):
    body = client.get("/api/evaluation").json()
    assert len(body["byHour"]) == 24
    assert len(body["byDay"]) == 31
    assert sum(b["count"] for b in body["histogram"]) == PERIODS
    assert body["byForecastLevel"]
    summary = body["summary"]
    assert summary["rmse"] >= summary["mae"] > 0


def test_lead_curve_and_gate_sweep(client):
    lead = client.get("/api/lead-curve").json()["points"]
    assert [p["leadHours"] for p in lead] == list(range(49))
    sweep = client.get("/api/gate-sweep").json()
    gates = [p["gate"] for p in sweep["points"]]
    assert len(gates) == 48 + 2  # 30-minute grid plus the exact 09:20 / 09:50 gate closures
    assert gates == sorted(gates) and {"09:20", "09:50"} <= set(gates)
    by_gate = {p["gate"]: p for p in sweep["points"]}
    assert by_gate["09:20"]["typicalRun"] == "07:30 D-1"
    assert by_gate["09:50"]["typicalRun"] == "09:30 D-1"


def test_procurement_plan(client):
    body = client.get("/api/procurement").json()
    assert body["confidence"] == 0.9
    assert len(body["days"]) == 31
    total = body["total"]
    assert total["periods"] == PERIODS
    assert total["firmEnergyMwh"] + total["extraCoverMwh"] == pytest.approx(total["forecastEnergyMwh"])
    # In-sample, a 90% plan should hold in roughly 90% of periods.
    assert 0.85 <= total["coveredShare"] <= 0.95


def test_procurement_confidence_is_monotonic(client):
    firm = [
        client.get("/api/procurement", params={"confidence": c}).json()["total"]["firmEnergyMwh"]
        for c in (0.8, 0.9, 0.95)
    ]
    assert firm[0] > firm[1] > firm[2]


@pytest.mark.parametrize("confidence", [0.3, 1.0])
def test_procurement_rejects_out_of_range_confidence(client, confidence):
    assert client.get("/api/procurement", params={"confidence": confidence}).status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"gate": "9:20"},
        {"gate": "25:00"},
        {"mode": "lead", "lead": 72},
        {"mode": "weekly"},
        {"start": "2025-12-01"},
        {"start": "2026-01-20", "end": "2026-01-10"},
    ],
)
def test_invalid_parameters_are_rejected(client, params):
    assert client.get("/api/series", params=params).status_code == 422


def test_admin_refresh_requires_token(client):
    assert client.post("/api/admin/refresh").status_code == 401
    assert client.post("/api/admin/refresh", headers={"X-Admin-Token": "wrong"}).status_code == 401
