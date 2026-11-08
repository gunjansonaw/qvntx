"""HTTP routes. Thin by design: validate input, call analytics, map to schemas."""

from __future__ import annotations

import hmac
from datetime import date, time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from . import __version__
from .analytics import WindAnalytics
from .config import Settings
from .metrics import ErrorSummary
from .policies import DEFAULT_GATE, GATE_PRESETS, DayAheadGate, FixedLead, SelectionPolicy
from .procurement import ProcurementRow
from .repository import WindDataRepository
from .schemas import (
    BandBucketOut,
    BandOut,
    DailyOut,
    DatasetInfo,
    EvaluationResponse,
    GatePoint,
    GatePresetOut,
    GateSweepResponse,
    HealthResponse,
    HistogramBinOut,
    HourlyOut,
    LeadCurveResponse,
    LeadPoint,
    LevelOut,
    MetaResponse,
    PolicyOut,
    ProcurementResponse,
    ProcurementRowOut,
    SeriesPoint,
    SeriesResponse,
    SummaryOut,
    WindowOut,
)

router = APIRouter(prefix="/api")

GATE_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
MAX_LEAD_HOURS = 48.0
BAND_COVERAGE = 0.8  # P10..P90


# -- dependencies ------------------------------------------------------------


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_repository(request: Request) -> WindDataRepository:
    return request.app.state.repository


async def get_analytics(repo: Annotated[WindDataRepository, Depends(get_repository)]) -> WindAnalytics:
    return await repo.analytics()


def selection_policy(
    mode: Annotated[Literal["dayahead", "lead"], Query(description="Forecast selection policy")] = "dayahead",
    gate: Annotated[
        str, Query(pattern=GATE_PATTERN, description="dayahead: decision time HH:MM (UK) on D-1")
    ] = DEFAULT_GATE.strftime("%H:%M"),
    lead: Annotated[
        float, Query(ge=0, le=MAX_LEAD_HOURS, description="lead: minimum forecast lead time in hours")
    ] = 24.0,
) -> SelectionPolicy:
    if mode == "dayahead":
        hours, minutes = (int(part) for part in gate.split(":"))
        return DayAheadGate(time(hours, minutes))
    return FixedLead(lead)


def day_range(
    settings: Annotated[Settings, Depends(get_settings)],
    start: Annotated[date | None, Query(description="First delivery day (inclusive)")] = None,
    end: Annotated[date | None, Query(description="Last delivery day (inclusive)")] = None,
) -> tuple[date, date]:
    first, last = settings.delivery_days
    start, end = start or first, end or last
    if start > end:
        raise HTTPException(422, "start must be on or before end")
    if start < first or end > last:
        raise HTTPException(422, f"Delivery days must be within {first} .. {last}")
    return start, end


PolicyDep = Annotated[SelectionPolicy, Depends(selection_policy)]
RangeDep = Annotated[tuple[date, date], Depends(day_range)]
AnalyticsDep = Annotated[WindAnalytics, Depends(get_analytics)]


# -- mappers -----------------------------------------------------------------


def _policy_out(policy: SelectionPolicy) -> PolicyOut:
    if isinstance(policy, DayAheadGate):
        return PolicyOut(mode="dayahead", gate=policy.gate.strftime("%H:%M"), description=policy.describe())
    assert isinstance(policy, FixedLead)
    return PolicyOut(mode="lead", lead_hours=policy.hours, description=policy.describe())


def _window(days: tuple[date, date]) -> WindowOut:
    return WindowOut(first_day=days[0], last_day=days[1])


def _curve_fields(summary: ErrorSummary) -> dict:
    return dict(
        matched=summary.matched,
        coverage=summary.coverage,
        mae=summary.mae,
        rmse=summary.rmse,
        bias=summary.bias,
        p90_abs_error=summary.p90_abs_error,
    )


def _presets() -> list[GatePresetOut]:
    return [GatePresetOut(key=p.key, label=p.label, gate=p.gate.strftime("%H:%M"), note=p.note) for p in GATE_PRESETS]


# -- routes ------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[WindDataRepository, Depends(get_repository)],
) -> HealthResponse:
    """Liveness probe. Never triggers a data load, so it is safe for container health checks."""
    loaded = repo.loaded_dataset
    return HealthResponse(
        status="ok",
        version=__version__,
        data_mode=settings.data_mode,
        data_loaded=loaded is not None,
        source=loaded.source if loaded else None,
        retrieved_at=loaded.retrieved_at if loaded else None,
        last_error=repo.last_error,
    )


@router.get("/meta", response_model=MetaResponse, tags=["data"])
async def meta(settings: Annotated[Settings, Depends(get_settings)], analytics: AnalyticsDep) -> MetaResponse:
    """Analysis window, gate presets and data provenance."""
    dataset = analytics.dataset
    runs = dataset.forecasts.runs
    return MetaResponse(
        decision_days=_window(settings.decision_days),
        delivery_days=_window(settings.delivery_days),
        presets=_presets(),
        default_gate=DEFAULT_GATE.strftime("%H:%M"),
        max_lead_hours=MAX_LEAD_HOURS,
        dataset=DatasetInfo(
            source=dataset.source,
            retrieved_at=dataset.retrieved_at,
            actual_periods=len(dataset.actuals),
            forecast_runs=len(runs),
            forecast_points=dataset.forecast_points,
            first_run_published=runs[0].publish_time if runs else None,
            last_run_published=runs[-1].publish_time if runs else None,
        ),
    )


@router.get("/series", response_model=SeriesResponse, tags=["analysis"])
async def series(policy: PolicyDep, days: RangeDep, analytics: AnalyticsDep) -> SeriesResponse:
    """Half-hourly actual vs selected forecast, with an empirical P10-P50-P90 outturn band.

    For each forecast the band applies the signed-error quantiles at its forecast level:
    ``P10 = forecast - errorP90``, ``P50 = forecast - errorP50``,
    ``P90 = forecast - errorP10`` (floored at 0 MW).
    """
    points = analytics.aligned(policy, *days)
    summary = analytics.evaluate(policy, *days).summary
    band = analytics.error_band(policy, *days)

    def outturn_quantiles(forecast: float | None) -> tuple[float | None, float | None, float | None]:
        quantiles = band.quantiles_for(forecast) if forecast is not None else None
        if forecast is None or quantiles is None:
            return None, None, None
        error_p10, error_p50, error_p90 = quantiles
        return (
            max(0.0, forecast - error_p90),
            max(0.0, forecast - error_p50),
            max(0.0, forecast - error_p10),
        )

    series_points = []
    for p in points:
        p10, p50, p90 = outturn_quantiles(p.forecast)
        series_points.append(
            SeriesPoint(
                time=p.start,
                actual=p.actual,
                forecast=p.forecast,
                error=p.error,
                p10=p10,
                p50=p50,
                p90=p90,
                publish_time=p.publish_time,
                lead_hours=p.lead_hours,
            )
        )

    return SeriesResponse(
        policy=_policy_out(policy),
        window=_window(days),
        band=BandOut(
            coverage=BAND_COVERAGE,
            method=(
                "Empirical P10/P50/P90 of forecast error over the selected window, "
                f"conditioned on forecast level ({band.bucket_mw / 1000:g} GW buckets)"
            ),
            buckets=[BandBucketOut(**vars(b)) for b in band.buckets],
        ),
        summary=SummaryOut.of(summary),
        points=series_points,
    )


@router.get("/evaluation", response_model=EvaluationResponse, tags=["analysis"])
async def evaluation(policy: PolicyDep, days: RangeDep, analytics: AnalyticsDep) -> EvaluationResponse:
    """Accuracy metrics, error distribution, and breakdowns by hour of day and delivery day."""
    result = analytics.evaluate(policy, *days)
    return EvaluationResponse(
        policy=_policy_out(policy),
        window=_window(days),
        summary=SummaryOut.of(result.summary),
        histogram=[HistogramBinOut(**vars(b)) for b in result.histogram],
        by_hour=[
            HourlyOut(
                hour=h.hour, matched=h.summary.matched, mae=h.summary.mae, rmse=h.summary.rmse, bias=h.summary.bias
            )
            for h in result.by_hour
        ],
        by_day=[
            DailyOut(
                day=d.day,
                matched=d.summary.matched,
                coverage=d.summary.coverage,
                mae=d.summary.mae,
                rmse=d.summary.rmse,
                bias=d.summary.bias,
                wape=d.summary.wape,
                actual_energy_mwh=d.summary.actual_energy_mwh,
                forecast_energy_mwh=d.summary.forecast_energy_mwh,
                shortfall_energy_mwh=d.summary.shortfall_energy_mwh,
                surplus_energy_mwh=d.summary.surplus_energy_mwh,
                run_publish_times=list(d.run_publish_times),
            )
            for d in result.by_day
        ],
        by_forecast_level=[
            LevelOut(
                lower=lv.lower,
                upper=lv.upper,
                matched=lv.summary.matched,
                mae=lv.summary.mae,
                rmse=lv.summary.rmse,
                bias=lv.summary.bias,
            )
            for lv in result.by_forecast_level
        ],
    )


@router.get("/lead-curve", response_model=LeadCurveResponse, tags=["analysis"])
async def lead_curve(days: RangeDep, analytics: AnalyticsDep) -> LeadCurveResponse:
    """Error vs forecast lead time (0-48 h), using fixed-lead selection."""
    return LeadCurveResponse(
        window=_window(days),
        points=[LeadPoint(lead_hours=s.lead_hours, **_curve_fields(s.summary)) for s in analytics.lead_curve(*days)],
    )


@router.get("/gate-sweep", response_model=GateSweepResponse, tags=["analysis"])
async def gate_sweep(days: RangeDep, analytics: AnalyticsDep) -> GateSweepResponse:
    """Error vs day-ahead decision time on D-1, in 30-minute steps."""
    return GateSweepResponse(
        window=_window(days),
        presets=_presets(),
        points=[
            GatePoint(gate=s.gate.strftime("%H:%M"), typical_run=s.typical_run, **_curve_fields(s.summary))
            for s in analytics.gate_sweep(*days)
        ],
    )


@router.get("/procurement", response_model=ProcurementResponse, tags=["analysis"])
async def procurement(
    policy: PolicyDep,
    days: RangeDep,
    analytics: AnalyticsDep,
    confidence: Annotated[
        float, Query(ge=0.5, le=0.99, description="Share of periods the firm wind volume must be met (e.g. 0.9)")
    ] = 0.9,
) -> ProcurementResponse:
    """Wind the desk can count on (firm wind) and extra cover to buy, per delivery day.

    ``firm = forecast - error quantile at the requested confidence`` (level-conditioned).
    Power to buy per period = demand - firm wind; demand is outside this dataset's scope.
    """
    plan = analytics.procurement(policy, *days, confidence=round(confidence, 3))

    def row(r: ProcurementRow) -> ProcurementRowOut:
        return ProcurementRowOut(**{**vars(r), "run_publish_times": list(r.run_publish_times)})

    return ProcurementResponse(
        policy=_policy_out(policy),
        window=_window(days),
        confidence=plan.confidence,
        method=(
            "Firm wind = forecast minus the forecast-error quantile at the chosen confidence, "
            "conditioned on forecast level and calibrated on the selected window"
        ),
        total=row(plan.total),
        days=[row(d) for d in plan.days],
    )


@router.post("/admin/refresh", response_model=HealthResponse, tags=["system"])
async def refresh(
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[WindDataRepository, Depends(get_repository)],
    x_admin_token: Annotated[str | None, Header()] = None,
) -> HealthResponse:
    """Force a live re-fetch from Elexon. Disabled unless ADMIN_TOKEN is configured."""
    if not settings.admin_token:
        raise HTTPException(404, "Not found")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(401, "Invalid admin token")
    await repo.refresh()
    return await health(settings, repo)
