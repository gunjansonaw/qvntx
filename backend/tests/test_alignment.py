from datetime import date, time, timedelta

import pytest

from app.alignment import align, settlement_periods
from app.domain import ActualRecord, ForecastRecord, build_actuals, build_runs
from app.policies import DayAheadGate, FixedLead

from .conftest import make_dataset, make_run, utc


class TestForecastRun:
    def test_half_hour_is_interpolated_within_the_same_run(self):
        run = make_run(utc(2026, 1, 1, 7, 30), utc(2026, 1, 2, 0), [1000, 2000])
        assert run.value_at(utc(2026, 1, 2, 0)) == 1000
        assert run.value_at(utc(2026, 1, 2, 0, 30)) == 1500
        assert run.value_at(utc(2026, 1, 2, 1, 30)) is None  # no upper neighbour


class TestForecastArchive:
    def test_picks_latest_run_published_at_or_before_cutoff(self):
        target = utc(2026, 1, 2, 12)
        early = make_run(utc(2026, 1, 1, 4, 30), target, [100])
        on_time = make_run(utc(2026, 1, 1, 9, 30), target, [200])
        too_late = make_run(utc(2026, 1, 1, 11, 30), target, [300])
        dataset = make_dataset({}, [too_late, early, on_time])  # order must not matter

        run, value = dataset.forecasts.latest_as_of(target, cutoff=utc(2026, 1, 1, 9, 30))
        assert (run.publish_time, value) == (on_time.publish_time, 200)

        run, value = dataset.forecasts.latest_as_of(target, cutoff=utc(2026, 1, 1, 9, 29))
        assert value == 100  # 09:30 run not yet published -> no look-ahead

    def test_falls_back_to_older_run_when_newest_lacks_target(self):
        target = utc(2026, 1, 3, 12)
        covers = make_run(utc(2026, 1, 1, 4, 30), target, [500])
        partial = make_run(utc(2026, 1, 1, 9, 30), utc(2026, 1, 2, 0), [1, 2, 3])
        dataset = make_dataset({}, [covers, partial])
        assert dataset.forecasts.latest_as_of(target, utc(2026, 1, 1, 10))[1] == 500

    def test_nothing_before_cutoff(self):
        dataset = make_dataset({}, [make_run(utc(2026, 1, 1, 9, 30), utc(2026, 1, 2), [1])])
        assert dataset.forecasts.latest_as_of(utc(2026, 1, 2), utc(2026, 1, 1)) is None


class TestPolicies:
    def test_day_ahead_gate_in_winter_gmt(self):
        policy = DayAheadGate(time(9, 20))
        assert policy.cutoff_for(utc(2026, 1, 15, 23, 30)) == utc(2026, 1, 14, 9, 20)

    def test_day_ahead_gate_in_summer_bst(self):
        # 23:30 UTC on 14 Jul is 00:30 BST on 15 Jul -> delivery day 15 Jul, gate 09:20 BST = 08:20 UTC
        policy = DayAheadGate(time(9, 20))
        assert policy.cutoff_for(utc(2026, 7, 14, 23, 30)) == utc(2026, 7, 14, 8, 20)

    def test_fixed_lead(self):
        assert FixedLead(4).cutoff_for(utc(2026, 1, 2, 12)) == utc(2026, 1, 2, 8)


class TestSettlementPeriods:
    def test_normal_day_has_48_periods(self):
        periods = settlement_periods(date(2026, 1, 2), date(2026, 1, 2))
        assert len(periods) == 48
        assert periods[0] == utc(2026, 1, 2, 0) and periods[-1] == utc(2026, 1, 2, 23, 30)

    @pytest.mark.parametrize(("day", "expected"), [(date(2026, 3, 29), 46), (date(2026, 10, 25), 50)])
    def test_clock_change_days(self, day, expected):
        assert len(settlement_periods(day, day)) == expected


class TestAlign:
    def test_pairs_actuals_with_day_ahead_forecast(self):
        run_used = make_run(utc(2026, 1, 1, 7, 30), utc(2026, 1, 2, 0), [1000.0] * 25)
        run_late = make_run(utc(2026, 1, 1, 11, 30), utc(2026, 1, 2, 0), [9999.0] * 25)
        actuals = {utc(2026, 1, 2, 0): 800.0}
        dataset = make_dataset(actuals, [run_used, run_late])
        points = align(dataset, DayAheadGate(time(9, 20)), settlement_periods(date(2026, 1, 2), date(2026, 1, 2)))

        assert len(points) == 48
        first = points[0]
        assert first.forecast == 1000 and first.actual == 800 and first.error == 200
        assert first.publish_time == run_used.publish_time
        assert first.lead_hours == pytest.approx(16.5)
        assert points[1].actual is None and points[1].error is None


class TestBuilders:
    def test_build_runs_drops_rows_before_publish_time(self):
        publish = utc(2026, 1, 1, 9, 30)
        records = [
            ForecastRecord(publish, publish - timedelta(hours=1), 1.0),  # hindcast -> dropped
            ForecastRecord(publish, utc(2026, 1, 1, 10), 2.0),
        ]
        (run,) = build_runs(records)
        assert list(run.values.values()) == [2.0]

    def test_build_actuals_keeps_latest_revision(self):
        start = utc(2026, 1, 2)
        records = [
            ActualRecord(start, utc(2026, 1, 2, 0, 30), 100.0),
            ActualRecord(start, utc(2026, 1, 2, 5), 120.0),  # revised later
        ]
        assert build_actuals(records) == {start: 120.0}
