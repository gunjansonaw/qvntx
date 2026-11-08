import pytest

from app.alignment import AlignedPoint
from app.metrics import ConditionalErrorBand
from app.procurement import plan_procurement

from .conftest import utc


def point(day, hour, forecast, actual):
    return AlignedPoint(start=utc(2026, 1, day, hour), actual=actual, forecast=forecast, publish_time=utc(2026, 1, 1))


def flat_band(error: float) -> ConditionalErrorBand:
    """Every forecast level misses by exactly ``error`` MW."""
    return ConditionalErrorBand([(1000.0, error)] * 60, bucket_mw=3000, min_count=50)


def test_firm_wind_is_forecast_minus_the_error_quantile():
    plan = plan_procurement([point(2, 0, 10_000, 9_500)], flat_band(1_000), confidence=0.9)
    row = plan.total
    assert row.firm_energy_mwh == pytest.approx(9_000 * 0.5)  # MW over half an hour
    assert row.extra_cover_mwh == pytest.approx(1_000 * 0.5)
    assert row.peak_extra_cover_mw == pytest.approx(1_000)
    assert row.covered_share == 1.0  # actual 9,500 >= firm 9,000


def test_firm_wind_never_goes_negative():
    plan = plan_procurement([point(2, 0, 500, 0)], flat_band(2_000), confidence=0.9)
    assert plan.total.firm_energy_mwh == 0.0
    assert plan.total.extra_cover_mwh == pytest.approx(500 * 0.5)


def test_rows_per_delivery_day_and_backtest_share():
    points = [point(2, 0, 5_000, 3_000), point(2, 1, 5_000, 4_500), point(3, 0, 5_000, None)]
    plan = plan_procurement(points, flat_band(1_000), confidence=0.9)
    day2, day3 = plan.days
    assert day2.covered_share == 0.5  # 3,000 < firm 4,000; 4,500 >= 4,000
    assert day3.actual_energy_mwh is None and day3.covered_share is None
    assert plan.total.periods == 3


def test_higher_confidence_means_less_firm_wind():
    errors = [(8_000.0, float(e)) for e in range(-1_000, 4_000, 50)]
    band = ConditionalErrorBand(errors, bucket_mw=3000, min_count=50)
    points = [point(2, 0, 8_000, 7_000)]
    firm = [plan_procurement(points, band, c).total.firm_energy_mwh for c in (0.8, 0.9, 0.95)]
    assert firm[0] > firm[1] > firm[2]


def test_rejects_silly_confidence():
    with pytest.raises(ValueError):
        plan_procurement([], flat_band(0), confidence=1.0)
