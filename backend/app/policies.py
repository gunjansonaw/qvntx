"""Forecast selection policies - *which* forecast counts for a given target period.

A policy maps each target settlement period to a decision cutoff. The forecast used
is then the latest run published at or before that cutoff
(see ``ForecastArchive.latest_as_of``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Protocol

from .domain import UK_TZ


class SelectionPolicy(Protocol):
    """Anything that can tell us when the decision for ``target`` is taken."""

    def cutoff_for(self, target: datetime) -> datetime: ...

    def describe(self) -> str: ...


@dataclass(frozen=True)
class DayAheadGate:
    """Decide at a fixed UK clock time on the day before delivery (D-1).

    This mirrors how a day-ahead desk works: every settlement period of delivery
    day D is bought in one auction on D-1, so they all share the same forecast run.
    Delivery days are UK settlement days (local midnight to midnight), so the
    policy stays correct across GMT/BST clock changes.
    """

    gate: time

    def cutoff_for(self, target: datetime) -> datetime:
        delivery_day = target.astimezone(UK_TZ).date()
        decision = datetime.combine(delivery_day - timedelta(days=1), self.gate, tzinfo=UK_TZ)
        return decision.astimezone(UTC)

    def describe(self) -> str:
        return f"Latest forecast published by {self.gate:%H:%M} UK time on the day before delivery"


@dataclass(frozen=True)
class FixedLead:
    """Use the latest forecast published at least ``hours`` before each target period."""

    hours: float

    def cutoff_for(self, target: datetime) -> datetime:
        return target - timedelta(hours=self.hours)

    def describe(self) -> str:
        return f"Latest forecast published at least {self.hours:g} h before each period"


@dataclass(frozen=True)
class GatePreset:
    key: str
    label: str
    gate: time
    note: str


# GB day-ahead auction gate closures (UK local time). Sources are cited in the README.
GATE_PRESETS: tuple[GatePreset, ...] = (
    GatePreset("epex", "EPEX GB day-ahead", time(9, 20), "EPEX SPOT GB hourly auction"),
    GatePreset("n2ex", "Nord Pool N2EX day-ahead", time(9, 50), "Nord Pool GB day-ahead auction"),
)
DEFAULT_GATE = GATE_PRESETS[0].gate
