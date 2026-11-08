"""Analytics service: turns a ``WindDataset`` into the views the dashboard needs.

The dataset is immutable for the lifetime of an instance, so results are memoised
in a small LRU keyed by (policy, day range). A data refresh builds a new instance.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import TypeVar

from .alignment import AlignedPoint, align, settlement_periods
from .domain import UK_TZ, WindDataset
from .metrics import ConditionalErrorBand, ErrorSummary, HistogramBin, histogram, summarize
from .policies import GATE_PRESETS, DayAheadGate, FixedLead, SelectionPolicy
from .procurement import ProcurementPlan, plan_procurement

T = TypeVar("T")

HISTOGRAM_BIN_MW = 500.0
LEVEL_BUCKET_MW = 3000.0
BAND_MIN_SAMPLES = 50
DEFAULT_LEADS: tuple[float, ...] = tuple(float(h) for h in range(0, 49))
GATE_SWEEP_STEP_MINUTES = 30


@dataclass(frozen=True)
class DailyStat:
    day: date
    summary: ErrorSummary
    run_publish_times: tuple[datetime, ...]  # forecast runs used for this day


@dataclass(frozen=True)
class HourlyStat:
    hour: int  # UK local hour of day
    summary: ErrorSummary


@dataclass(frozen=True)
class LevelStat:
    lower: float  # forecast level range, MW
    upper: float
    summary: ErrorSummary


@dataclass(frozen=True)
class Evaluation:
    summary: ErrorSummary
    histogram: list[HistogramBin]
    by_hour: list[HourlyStat]
    by_day: list[DailyStat]
    by_forecast_level: list[LevelStat]


@dataclass(frozen=True)
class LeadStat:
    lead_hours: float
    summary: ErrorSummary


@dataclass(frozen=True)
class GateStat:
    gate: time
    summary: ErrorSummary
    typical_run: str | None  # e.g. "07:30 D-1": the run usually in force at this gate


class _LRU:
    """Tiny bounded memo table (functools.lru_cache leaks when used on methods)."""

    def __init__(self, maxsize: int) -> None:
        self._data: OrderedDict[Hashable, object] = OrderedDict()
        self._maxsize = maxsize

    def get_or_compute(self, key: Hashable, compute: Callable[[], T]) -> T:
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]  # type: ignore[return-value]
        value = compute()
        self._data[key] = value
        if len(self._data) > self._maxsize:
            self._data.popitem(last=False)
        return value


class WindAnalytics:
    def __init__(self, dataset: WindDataset, cache_size: int = 256) -> None:
        self.dataset = dataset
        self._cache = _LRU(cache_size)

    # -- building blocks -------------------------------------------------

    def aligned(self, policy: SelectionPolicy, first: date, last: date) -> list[AlignedPoint]:
        return self._cache.get_or_compute(
            ("aligned", policy, first, last),
            lambda: align(self.dataset, policy, settlement_periods(first, last)),
        )

    # -- views -------------------------------------------------------------

    def evaluate(self, policy: SelectionPolicy, first: date, last: date) -> Evaluation:
        """Headline metrics plus error breakdowns for one selection policy."""

        def compute() -> Evaluation:
            points = self.aligned(policy, first, last)
            errors = [p.error for p in points if p.error is not None]
            by_hour = _group(points, lambda p: p.start.astimezone(UK_TZ).hour)
            by_day = _group(points, lambda p: p.delivery_day)
            by_level = _group(
                (p for p in points if p.forecast is not None),
                lambda p: int(p.forecast // LEVEL_BUCKET_MW),
            )
            return Evaluation(
                summary=summarize(points),
                histogram=histogram(errors, HISTOGRAM_BIN_MW),
                by_hour=[HourlyStat(hour, summarize(pts)) for hour, pts in sorted(by_hour.items())],
                by_day=[
                    DailyStat(
                        day=day,
                        summary=summarize(pts),
                        run_publish_times=tuple(sorted({p.publish_time for p in pts if p.publish_time})),
                    )
                    for day, pts in sorted(by_day.items())
                ],
                by_forecast_level=[
                    LevelStat(index * LEVEL_BUCKET_MW, (index + 1) * LEVEL_BUCKET_MW, summarize(pts))
                    for index, pts in sorted(by_level.items())
                ],
            )

        return self._cache.get_or_compute(("evaluate", policy, first, last), compute)

    def procurement(self, policy: SelectionPolicy, first: date, last: date, confidence: float) -> ProcurementPlan:
        """Firm wind and extra cover per delivery day at the requested confidence level."""
        return self._cache.get_or_compute(
            ("procurement", policy, first, last, confidence),
            lambda: plan_procurement(
                self.aligned(policy, first, last), self.error_band(policy, first, last), confidence
            ),
        )

    def error_band(self, policy: SelectionPolicy, first: date, last: date) -> ConditionalErrorBand:
        """Level-conditioned error quantiles used to draw the P10-P90 outturn band."""
        return self._cache.get_or_compute(
            ("error_band", policy, first, last),
            lambda: ConditionalErrorBand(
                [(p.forecast, p.error) for p in self.aligned(policy, first, last) if p.error is not None],
                bucket_mw=LEVEL_BUCKET_MW,
                min_count=BAND_MIN_SAMPLES,
            ),
        )

    def lead_curve(self, first: date, last: date, leads: Iterable[float] = DEFAULT_LEADS) -> list[LeadStat]:
        """How accuracy decays with forecast lead time (fixed-lead policies)."""
        leads = tuple(leads)
        return self._cache.get_or_compute(
            ("lead_curve", leads, first, last),
            lambda: [LeadStat(lead, summarize(self.aligned(FixedLead(lead), first, last))) for lead in leads],
        )

    def gate_sweep(self, first: date, last: date, step_minutes: int = GATE_SWEEP_STEP_MINUTES) -> list[GateStat]:
        """Accuracy as a function of the decision time on D-1.

        Answers: "if we took our day-ahead decision at HH:MM, how good was the
        forecast we could have seen?" - the curve steps down each time a new
        WINDFOR run lands.
        """

        def compute() -> list[GateStat]:
            grid = {time(m // 60, m % 60) for m in range(0, 24 * 60, step_minutes)}
            # Include the real auction gate closures exactly, not just the nearest grid step.
            gates = sorted(grid | {preset.gate for preset in GATE_PRESETS})
            stats = []
            for gate in gates:
                points = self.aligned(DayAheadGate(gate), first, last)
                stats.append(GateStat(gate, summarize(points), _typical_run(points)))
            return stats

        return self._cache.get_or_compute(("gate_sweep", step_minutes, first, last), compute)


def _group(points: Iterable[AlignedPoint], key: Callable[[AlignedPoint], Hashable]) -> dict:
    groups: dict[Hashable, list[AlignedPoint]] = {}
    for point in points:
        groups.setdefault(key(point), []).append(point)
    return groups


def _typical_run(points: Iterable[AlignedPoint]) -> str | None:
    """Most common run label, relative to delivery day, e.g. '07:30 D-1'."""
    labels = Counter()
    for point in points:
        if point.publish_time is None:
            continue
        published = point.publish_time.astimezone(UK_TZ)
        days_before = (point.delivery_day - published.date()).days
        labels[f"{published:%H:%M} D-{days_before}"] += 1
    return labels.most_common(1)[0][0] if labels else None
