"""Timestamp alignment: pair every settlement period with its actual and its forecast."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from .domain import SETTLEMENT_PERIOD, UK_TZ, WindDataset
from .policies import SelectionPolicy


@dataclass(frozen=True, slots=True)
class AlignedPoint:
    """One settlement period: what happened vs what we believed at decision time."""

    start: datetime  # UTC
    actual: float | None  # MW (FUELHH)
    forecast: float | None  # MW (WINDFOR, possibly interpolated)
    publish_time: datetime | None  # run the forecast came from

    @property
    def error(self) -> float | None:
        """forecast - actual (MW). Positive = over-forecast = shortfall to procure."""
        if self.actual is None or self.forecast is None:
            return None
        return self.forecast - self.actual

    @property
    def lead_hours(self) -> float | None:
        if self.publish_time is None:
            return None
        return (self.start - self.publish_time).total_seconds() / 3600

    @property
    def delivery_day(self) -> date:
        return self.start.astimezone(UK_TZ).date()


def settlement_periods(first_day: date, last_day: date) -> list[datetime]:
    """UTC start of every settlement period across UK delivery days (inclusive).

    Stepping from local midnight to local midnight means clock-change days
    automatically get 46 or 50 periods instead of 48.
    """
    start = datetime.combine(first_day, time(0), tzinfo=UK_TZ).astimezone(UTC)
    end = datetime.combine(last_day + timedelta(days=1), time(0), tzinfo=UK_TZ).astimezone(UTC)
    count = int((end - start) / SETTLEMENT_PERIOD)
    return [start + i * SETTLEMENT_PERIOD for i in range(count)]


def align(dataset: WindDataset, policy: SelectionPolicy, targets: list[datetime]) -> list[AlignedPoint]:
    """Attach the actual and the policy-selected forecast to each target period."""
    points: list[AlignedPoint] = []
    for target in targets:
        hit = dataset.forecasts.latest_as_of(target, policy.cutoff_for(target))
        run, value = hit if hit else (None, None)
        points.append(
            AlignedPoint(
                start=target,
                actual=dataset.actuals.get(target),
                forecast=value,
                publish_time=run.publish_time if run else None,
            )
        )
    return points
