"""Forecast error metrics - pure functions, no I/O, no third-party dependencies.

Sign convention: ``error = forecast - actual`` (MW).
* error > 0 -> wind over-forecast -> buyer is short and must procure more.
* error < 0 -> wind under-forecast -> buyer is long (surplus).
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

from .alignment import AlignedPoint

HOURS_PER_PERIOD = 0.5  # MW over a half-hour settlement period -> MWh


def quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile of pre-sorted data (same as numpy's default)."""
    if not sorted_values:
        raise ValueError("quantile of empty sequence")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be within [0, 1]")
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


@dataclass(frozen=True)
class ErrorSummary:
    """Accuracy statistics for a set of aligned settlement periods."""

    periods: int  # settlement periods requested
    matched: int  # periods with both an actual and a forecast
    coverage: float  # matched / periods
    mae: float | None  # mean absolute error (MW)
    rmse: float | None  # root mean squared error (MW)
    bias: float | None  # mean error (MW); > 0 means systematic over-forecast
    wape: float | None  # sum|e| / sum(actual), % - robust "percentage error"
    mape: float | None  # mean(|e| / actual), % - shown for familiarity, unstable at low output
    median_abs_error: float | None
    p90_abs_error: float | None  # 90% of periods had |error| below this
    error_p10: float | None  # signed error quantiles
    error_p50: float | None
    error_p90: float | None
    max_over_forecast: float | None  # largest positive error
    max_under_forecast: float | None  # most negative error
    over_forecast_share: float | None  # fraction of periods where wind came in below forecast
    actual_mean: float | None
    forecast_mean: float | None
    actual_energy_mwh: float
    forecast_energy_mwh: float
    shortfall_energy_mwh: float  # energy wind failed to deliver vs plan (sum of positive errors)
    surplus_energy_mwh: float  # energy delivered above plan (sum of negative errors)
    min_lead_hours: float | None
    max_lead_hours: float | None


def summarize(points: Sequence[AlignedPoint]) -> ErrorSummary:
    """Compute accuracy statistics over periods that have both an actual and a forecast."""
    pairs = [(p.forecast, p.actual) for p in points if p.forecast is not None and p.actual is not None]
    leads = [p.lead_hours for p in points if p.lead_hours is not None]
    n = len(pairs)
    coverage = n / len(points) if points else 0.0
    lead_range = (min(leads), max(leads)) if leads else (None, None)

    if n == 0:
        return ErrorSummary(
            periods=len(points), matched=0, coverage=coverage,
            mae=None, rmse=None, bias=None, wape=None, mape=None,
            median_abs_error=None, p90_abs_error=None,
            error_p10=None, error_p50=None, error_p90=None,
            max_over_forecast=None, max_under_forecast=None, over_forecast_share=None,
            actual_mean=None, forecast_mean=None,
            actual_energy_mwh=0.0, forecast_energy_mwh=0.0,
            shortfall_energy_mwh=0.0, surplus_energy_mwh=0.0,
            min_lead_hours=lead_range[0], max_lead_hours=lead_range[1],
        )  # fmt: skip

    errors = [f - a for f, a in pairs]
    abs_errors = sorted(abs(e) for e in errors)
    signed = sorted(errors)
    actual_total = sum(a for _, a in pairs)
    forecast_total = sum(f for f, _ in pairs)
    positive_actuals = [(abs(f - a), a) for f, a in pairs if a > 0]

    return ErrorSummary(
        periods=len(points),
        matched=n,
        coverage=coverage,
        mae=sum(abs_errors) / n,
        rmse=math.sqrt(sum(e * e for e in errors) / n),
        bias=sum(errors) / n,
        wape=100 * sum(abs_errors) / actual_total if actual_total > 0 else None,
        mape=(100 * sum(e / a for e, a in positive_actuals) / len(positive_actuals) if positive_actuals else None),
        median_abs_error=quantile(abs_errors, 0.5),
        p90_abs_error=quantile(abs_errors, 0.9),
        error_p10=quantile(signed, 0.1),
        error_p50=quantile(signed, 0.5),
        error_p90=quantile(signed, 0.9),
        max_over_forecast=signed[-1],
        max_under_forecast=signed[0],
        over_forecast_share=sum(1 for e in errors if e > 0) / n,
        actual_mean=actual_total / n,
        forecast_mean=forecast_total / n,
        actual_energy_mwh=actual_total * HOURS_PER_PERIOD,
        forecast_energy_mwh=forecast_total * HOURS_PER_PERIOD,
        shortfall_energy_mwh=sum(e for e in errors if e > 0) * HOURS_PER_PERIOD,
        surplus_energy_mwh=-sum(e for e in errors if e < 0) * HOURS_PER_PERIOD,
        min_lead_hours=lead_range[0],
        max_lead_hours=lead_range[1],
    )


@dataclass(frozen=True)
class LevelBucket:
    """Signed-error quantiles for forecasts within [lower, upper) MW."""

    lower: float
    upper: float
    count: int
    error_p10: float
    error_p50: float
    error_p90: float


class ConditionalErrorBand:
    """Empirical forecast-error quantiles conditioned on the forecast level.

    Error is strongly level-dependent for wind (bigger forecasts miss by more), so a
    single global band is too wide at low wind and too narrow at high wind. Forecasts
    are bucketed by MW and buckets with fewer than ``min_count`` samples are ignored
    rather than trusting a handful of points. Quantiles for a given forecast are
    interpolated between the centres of neighbouring buckets (and clamped beyond the
    outermost ones), so the band has no artificial steps at bucket edges.
    """

    def __init__(self, pairs: Sequence[tuple[float, float]], bucket_mw: float = 3000.0, min_count: int = 50) -> None:
        """``pairs`` are (forecast, error) tuples."""
        if bucket_mw <= 0:
            raise ValueError("bucket_mw must be positive")
        self.bucket_mw = bucket_mw
        grouped: dict[int, list[float]] = {}
        for forecast, error in pairs:
            grouped.setdefault(self._index(forecast), []).append(error)
        self._buckets: dict[int, LevelBucket] = {}
        self._sorted_errors: dict[int, list[float]] = {}
        for index, errors in sorted(grouped.items()):
            if len(errors) < min_count:
                continue
            ordered = sorted(errors)
            self._sorted_errors[index] = ordered
            self._buckets[index] = LevelBucket(
                lower=index * bucket_mw,
                upper=(index + 1) * bucket_mw,
                count=len(ordered),
                error_p10=quantile(ordered, 0.1),
                error_p50=quantile(ordered, 0.5),
                error_p90=quantile(ordered, 0.9),
            )

    def _index(self, forecast: float) -> int:
        return math.floor(forecast / self.bucket_mw)

    @property
    def buckets(self) -> list[LevelBucket]:
        return list(self._buckets.values())

    def error_quantile(self, forecast: float, q: float) -> float | None:
        """Signed-error quantile ``q`` at this forecast level, or None without data.

        E.g. ``q=0.9`` gives the error exceeded in only 10% of periods, so
        ``forecast - error_quantile(forecast, 0.9)`` is the wind volume delivered in
        90% of periods ("firm" wind at 90% confidence).
        """
        indices = list(self._sorted_errors)  # ordered by level
        if not indices:
            return None
        centres = [(index + 0.5) * self.bucket_mw for index in indices]

        def at(position: int) -> float:
            return quantile(self._sorted_errors[indices[position]], q)

        if forecast <= centres[0]:
            return at(0)
        if forecast >= centres[-1]:
            return at(-1)
        upper = bisect_right(centres, forecast)
        weight = (forecast - centres[upper - 1]) / (centres[upper] - centres[upper - 1])
        return at(upper - 1) + (at(upper) - at(upper - 1)) * weight

    def quantiles_for(self, forecast: float) -> tuple[float, float, float] | None:
        """Signed-error (P10, P50, P90) for a forecast level, or None without data."""
        if not self._sorted_errors:
            return None
        return (
            self.error_quantile(forecast, 0.1),
            self.error_quantile(forecast, 0.5),
            self.error_quantile(forecast, 0.9),
        )  # type: ignore[return-value]


@dataclass(frozen=True)
class HistogramBin:
    lower: float
    upper: float
    count: int
    share: float  # fraction of all errors in this bin


def histogram(errors: Sequence[float], bin_width: float) -> list[HistogramBin]:
    """Fixed-width histogram with bin edges aligned to multiples of ``bin_width``.

    Aligning edges to zero keeps the over/under-forecast split on a bin boundary,
    and empty interior bins are kept so the distribution's shape is honest.
    """
    if bin_width <= 0:
        raise ValueError("bin_width must be positive")
    if not errors:
        return []
    counts: dict[int, int] = {}
    for error in errors:
        index = math.floor(error / bin_width)
        counts[index] = counts.get(index, 0) + 1
    total = len(errors)
    return [
        HistogramBin(
            lower=i * bin_width,
            upper=(i + 1) * bin_width,
            count=counts.get(i, 0),
            share=counts.get(i, 0) / total,
        )
        for i in range(min(counts), max(counts) + 1)
    ]
