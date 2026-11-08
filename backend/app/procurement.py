"""Procurement planning: how much wind the desk can count on, and how much to cover.

The client's question is "how much power must we buy beyond what wind provides?".
The total also needs the client's own demand forecast (out of scope: the brief limits
data to Elexon wind). What wind data *can* answer is the wind side of that sum:

* **firm wind**  - wind volume met or exceeded in ``confidence`` share of periods,
                   ``firm = forecast - error_quantile(forecast, confidence)`` using the
                   level-conditioned error distribution (floored at 0 MW).
* **extra cover** - ``forecast - firm``: what must be bought on top of planning against
                   the raw forecast to reach that confidence level.

So, per settlement period: ``power to buy = demand - firm wind``.

The plan is back-tested against what actually happened: ``covered_share`` is the
fraction of periods in which actual wind was at least the firm volume.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from .alignment import AlignedPoint
from .metrics import HOURS_PER_PERIOD, ConditionalErrorBand


@dataclass(frozen=True)
class ProcurementRow:
    """Plan for one delivery day (``day`` set) or for the whole window (``day`` None)."""

    day: date | None
    periods: int  # settlement periods with a forecast
    forecast_energy_mwh: float
    firm_energy_mwh: float
    extra_cover_mwh: float
    peak_extra_cover_mw: float | None  # largest half-hourly gap: capacity to have on hand
    actual_energy_mwh: float | None  # outcome (over periods that have an actual)
    covered_share: float | None  # back-test: share of periods with actual >= firm
    run_publish_times: tuple[datetime, ...]


@dataclass(frozen=True)
class ProcurementPlan:
    confidence: float
    total: ProcurementRow
    days: list[ProcurementRow]


@dataclass(frozen=True)
class _PeriodPlan:
    point: AlignedPoint
    firm_mw: float

    @property
    def extra_mw(self) -> float:
        return self.point.forecast - self.firm_mw  # type: ignore[operator]


def plan_procurement(points: Sequence[AlignedPoint], band: ConditionalErrorBand, confidence: float) -> ProcurementPlan:
    if not 0.5 <= confidence < 1.0:
        raise ValueError("confidence must be within [0.5, 1)")

    periods: list[_PeriodPlan] = []
    for point in points:
        if point.forecast is None:
            continue
        haircut = band.error_quantile(point.forecast, confidence)
        if haircut is None:
            continue
        periods.append(_PeriodPlan(point, firm_mw=max(0.0, point.forecast - haircut)))

    by_day: dict[date, list[_PeriodPlan]] = {}
    for period in periods:
        by_day.setdefault(period.point.delivery_day, []).append(period)

    return ProcurementPlan(
        confidence=confidence,
        total=_row(None, periods),
        days=[_row(day, rows) for day, rows in sorted(by_day.items())],
    )


def _row(day: date | None, periods: Iterable[_PeriodPlan]) -> ProcurementRow:
    periods = list(periods)
    with_actual = [p for p in periods if p.point.actual is not None]
    return ProcurementRow(
        day=day,
        periods=len(periods),
        forecast_energy_mwh=sum(p.point.forecast for p in periods) * HOURS_PER_PERIOD,  # type: ignore[misc]
        firm_energy_mwh=sum(p.firm_mw for p in periods) * HOURS_PER_PERIOD,
        extra_cover_mwh=sum(p.extra_mw for p in periods) * HOURS_PER_PERIOD,
        peak_extra_cover_mw=max((p.extra_mw for p in periods), default=None),
        actual_energy_mwh=(
            sum(p.point.actual for p in with_actual) * HOURS_PER_PERIOD if with_actual else None  # type: ignore[misc]
        ),
        covered_share=(
            sum(1 for p in with_actual if p.point.actual >= p.firm_mw) / len(with_actual) if with_actual else None
        ),
        run_publish_times=tuple(sorted({p.point.publish_time for p in periods if p.point.publish_time})),
    )
