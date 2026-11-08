"""Pydantic response models - the public API contract (also drives /docs).

Fields are snake_case in Python and camelCase on the wire for the JS client.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from .metrics import ErrorSummary


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SummaryOut(CamelModel):
    periods: int
    matched: int
    coverage: float
    mae: float | None
    rmse: float | None
    bias: float | None
    wape: float | None
    mape: float | None
    median_abs_error: float | None
    p90_abs_error: float | None
    error_p10: float | None
    error_p50: float | None
    error_p90: float | None
    max_over_forecast: float | None
    max_under_forecast: float | None
    over_forecast_share: float | None
    actual_mean: float | None
    forecast_mean: float | None
    actual_energy_mwh: float
    forecast_energy_mwh: float
    shortfall_energy_mwh: float
    surplus_energy_mwh: float
    min_lead_hours: float | None
    max_lead_hours: float | None

    @classmethod
    def of(cls, summary: ErrorSummary) -> SummaryOut:
        return cls(**asdict(summary))


class PolicyOut(CamelModel):
    mode: Literal["dayahead", "lead"]
    gate: str | None = None  # "HH:MM" UK time on D-1 (dayahead mode)
    lead_hours: float | None = None  # (lead mode)
    description: str


class WindowOut(CamelModel):
    first_day: date
    last_day: date


class SeriesPoint(CamelModel):
    time: datetime  # settlement period start (UTC)
    actual: float | None
    forecast: float | None
    error: float | None  # forecast - actual
    # Plausible outturn given the forecast (level-conditioned empirical quantiles):
    p10: float | None  # 10% chance outturn is below this (forecast - error P90)
    p50: float | None  # bias-adjusted central estimate (forecast - error P50)
    p90: float | None  # 10% chance outturn is above this (forecast - error P10)
    publish_time: datetime | None
    lead_hours: float | None


class BandBucketOut(CamelModel):
    lower: float  # forecast level range (MW)
    upper: float
    count: int
    error_p10: float
    error_p50: float
    error_p90: float


class BandOut(CamelModel):
    coverage: float  # nominal coverage of the band (0.8 = P10..P90)
    method: str
    buckets: list[BandBucketOut]


class SeriesResponse(CamelModel):
    policy: PolicyOut
    window: WindowOut
    band: BandOut
    summary: SummaryOut
    points: list[SeriesPoint]


class HistogramBinOut(CamelModel):
    lower: float
    upper: float
    count: int
    share: float


class HourlyOut(CamelModel):
    hour: int
    matched: int
    mae: float | None
    rmse: float | None
    bias: float | None


class DailyOut(CamelModel):
    day: date
    matched: int
    coverage: float
    mae: float | None
    rmse: float | None
    bias: float | None
    wape: float | None
    actual_energy_mwh: float
    forecast_energy_mwh: float
    shortfall_energy_mwh: float
    surplus_energy_mwh: float
    run_publish_times: list[datetime]


class LevelOut(CamelModel):
    lower: float  # forecast level range (MW)
    upper: float
    matched: int
    mae: float | None
    rmse: float | None
    bias: float | None


class EvaluationResponse(CamelModel):
    policy: PolicyOut
    window: WindowOut
    summary: SummaryOut
    histogram: list[HistogramBinOut]
    by_hour: list[HourlyOut]
    by_day: list[DailyOut]
    by_forecast_level: list[LevelOut]


class CurvePoint(CamelModel):
    matched: int
    coverage: float
    mae: float | None
    rmse: float | None
    bias: float | None
    p90_abs_error: float | None


class LeadPoint(CurvePoint):
    lead_hours: float


class LeadCurveResponse(CamelModel):
    window: WindowOut
    points: list[LeadPoint]


class GatePoint(CurvePoint):
    gate: str  # "HH:MM" UK time on D-1
    typical_run: str | None


class GatePresetOut(CamelModel):
    key: str
    label: str
    gate: str
    note: str


class GateSweepResponse(CamelModel):
    window: WindowOut
    presets: list[GatePresetOut]
    points: list[GatePoint]


class ProcurementRowOut(CamelModel):
    day: date | None  # None for the whole-window total
    periods: int
    forecast_energy_mwh: float
    firm_energy_mwh: float  # wind met or exceeded at the requested confidence
    extra_cover_mwh: float  # forecast - firm: to buy on top of the raw forecast
    peak_extra_cover_mw: float | None
    actual_energy_mwh: float | None
    covered_share: float | None  # back-test: share of periods with actual >= firm
    run_publish_times: list[datetime]


class ProcurementResponse(CamelModel):
    policy: PolicyOut
    window: WindowOut
    confidence: float
    method: str
    total: ProcurementRowOut
    days: list[ProcurementRowOut]


class DatasetInfo(CamelModel):
    source: str
    retrieved_at: datetime
    actual_periods: int
    forecast_runs: int
    forecast_points: int
    first_run_published: datetime | None
    last_run_published: datetime | None


class MetaResponse(CamelModel):
    decision_days: WindowOut
    delivery_days: WindowOut
    presets: list[GatePresetOut]
    default_gate: str
    max_lead_hours: float
    dataset: DatasetInfo


class HealthResponse(CamelModel):
    status: Literal["ok"]
    version: str
    data_mode: str
    data_loaded: bool
    source: str | None
    retrieved_at: datetime | None
    last_error: str | None
