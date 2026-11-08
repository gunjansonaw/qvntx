"""Core domain model: wind outturn, forecast runs and 'as-of' forecast lookups.

Terminology used throughout the code base:

* **target / startTime** - start of the half-hourly settlement period being delivered.
* **run** - one WINDFOR publication: an hourly forecast curve issued at ``publish_time``.
* **cutoff** - the moment a decision is taken. Only runs published at or before it
  are visible, which keeps the evaluation free of look-ahead bias.
* **error** - ``forecast - actual`` in MW. Positive = wind over-forecast, so the
  buyer is short and must procure the gap; negative = surplus.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

UK_TZ = ZoneInfo("Europe/London")
SETTLEMENT_PERIOD = timedelta(minutes=30)  # FUELHH resolution
FORECAST_STEP = timedelta(hours=1)  # WINDFOR resolution


class ActualRecord(NamedTuple):
    """One FUELHH row for fuel type WIND."""

    start: datetime
    publish: datetime
    generation: float


class ForecastRecord(NamedTuple):
    """One WINDFOR row."""

    publish: datetime
    start: datetime
    generation: float


@dataclass(frozen=True, slots=True)
class ForecastRun:
    """A single forecast publication (hourly values keyed by UTC start time)."""

    publish_time: datetime
    values: Mapping[datetime, float]

    def value_at(self, target: datetime) -> float | None:
        """Forecast MW for ``target``, or ``None`` if this run does not cover it.

        Settlement periods are half-hourly but WINDFOR is hourly, so an HH:30 target
        is linearly interpolated between the two surrounding hourly values *of the
        same run* - never by mixing runs, which would blend different vintages.
        """
        exact = self.values.get(target)
        if exact is not None:
            return exact
        floor = target.replace(minute=0, second=0, microsecond=0)
        lower = self.values.get(floor)
        upper = self.values.get(floor + FORECAST_STEP)
        if lower is None or upper is None:
            return None
        weight = (target - floor) / FORECAST_STEP
        return lower + (upper - lower) * weight


class ForecastArchive:
    """Time-ordered forecast runs supporting 'what did we know at time X' lookups."""

    # How many older runs to try if the newest visible run lacks the target
    # (e.g. a partial publication). Eight runs is roughly one day of WINDFOR.
    MAX_LOOKBACK = 8

    def __init__(self, runs: Iterable[ForecastRun]) -> None:
        self._runs = sorted(runs, key=lambda run: run.publish_time)
        self._publish_times = [run.publish_time for run in self._runs]

    def __len__(self) -> int:
        return len(self._runs)

    @property
    def runs(self) -> list[ForecastRun]:
        return list(self._runs)

    def latest_as_of(self, target: datetime, cutoff: datetime) -> tuple[ForecastRun, float] | None:
        """Newest run published at or before ``cutoff`` that has a value for ``target``."""
        newest = bisect_right(self._publish_times, cutoff) - 1
        oldest = max(-1, newest - self.MAX_LOOKBACK)
        for index in range(newest, oldest, -1):
            run = self._runs[index]
            value = run.value_at(target)
            if value is not None:
                return run, value
        return None


@dataclass(frozen=True)
class WindDataset:
    """Everything the analytics layer needs, plus where it came from."""

    actuals: Mapping[datetime, float]
    forecasts: ForecastArchive
    source: str  # "live" | "disk-cache" | "snapshot"
    retrieved_at: datetime

    @property
    def forecast_points(self) -> int:
        return sum(len(run.values) for run in self.forecasts.runs)


def build_actuals(records: Iterable[ActualRecord]) -> dict[datetime, float]:
    """Index outturn by settlement period, keeping the latest publication if revised."""
    latest: dict[datetime, ActualRecord] = {}
    for record in records:
        current = latest.get(record.start)
        if current is None or record.publish >= current.publish:
            latest[record.start] = record
    return {start: record.generation for start, record in sorted(latest.items())}


def build_runs(records: Iterable[ForecastRecord]) -> list[ForecastRun]:
    """Group forecast rows into runs.

    Each WINDFOR publication spans a fixed window that starts *before* its publish
    time; those leading rows are not forecasts (the outcome was partly known) and
    are dropped so every retained value has a non-negative lead time.
    """
    grouped: dict[datetime, dict[datetime, float]] = {}
    for record in records:
        if record.start < record.publish:
            continue
        grouped.setdefault(record.publish, {})[record.start] = record.generation
    return [
        ForecastRun(publish_time=publish, values=dict(sorted(values.items())))
        for publish, values in sorted(grouped.items())
        if values
    ]
