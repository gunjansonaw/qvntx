import math

import pytest

from app.alignment import AlignedPoint
from app.metrics import ConditionalErrorBand, histogram, quantile, summarize

from .conftest import utc


def point(forecast, actual, minute=0):
    return AlignedPoint(
        start=utc(2026, 1, 2, 0, minute), actual=actual, forecast=forecast, publish_time=utc(2026, 1, 1)
    )


class TestQuantile:
    def test_matches_numpy_linear_method(self):
        values = [1.0, 2.0, 3.0, 4.0]
        assert quantile(values, 0.0) == 1.0
        assert quantile(values, 1.0) == 4.0
        assert quantile(values, 0.5) == 2.5
        assert quantile(values, 0.9) == pytest.approx(3.7)

    def test_single_value(self):
        assert quantile([7.0], 0.3) == 7.0

    def test_rejects_bad_input(self):
        with pytest.raises(ValueError):
            quantile([], 0.5)
        with pytest.raises(ValueError):
            quantile([1.0], 1.5)


class TestSummarize:
    def test_known_values(self):
        # errors (forecast - actual): +100, -100, +300, -100
        points = [point(1100, 1000), point(900, 1000), point(1300, 1000), point(1900, 2000)]
        s = summarize(points)
        assert s.matched == 4 and s.coverage == 1.0
        assert s.mae == pytest.approx(150)
        assert s.rmse == pytest.approx(math.sqrt((100**2 * 3 + 300**2) / 4))
        assert s.bias == pytest.approx(50)
        assert s.wape == pytest.approx(100 * 600 / 5000)
        assert s.mape == pytest.approx(100 * (0.1 + 0.1 + 0.3 + 0.05) / 4)
        assert s.max_over_forecast == 300 and s.max_under_forecast == -100
        assert s.over_forecast_share == pytest.approx(0.5)
        # MW over half-hour periods -> MWh
        assert s.actual_energy_mwh == pytest.approx(5000 * 0.5)
        assert s.shortfall_energy_mwh == pytest.approx(400 * 0.5)
        assert s.surplus_energy_mwh == pytest.approx(200 * 0.5)

    def test_partial_coverage_ignores_unmatched_points(self):
        points = [point(1100, 1000), point(None, 1000), point(1000, None)]
        s = summarize(points)
        assert s.periods == 3 and s.matched == 1
        assert s.coverage == pytest.approx(1 / 3)
        assert s.mae == 100

    def test_empty_is_safe(self):
        s = summarize([])
        assert s.matched == 0 and s.mae is None and s.coverage == 0.0

    def test_mape_skips_zero_actuals(self):
        s = summarize([point(100, 0), point(110, 100)])
        assert s.mape == pytest.approx(10)


class TestHistogram:
    def test_bins_aligned_to_zero_and_keep_gaps(self):
        bins = histogram([-250, 10, 20, 1200], bin_width=500)
        assert [(b.lower, b.upper, b.count) for b in bins] == [
            (-500, 0, 1),
            (0, 500, 2),
            (500, 1000, 0),
            (1000, 1500, 1),
        ]
        assert sum(b.share for b in bins) == pytest.approx(1.0)

    def test_empty(self):
        assert histogram([], 500) == []


class TestConditionalErrorBand:
    def test_quantiles_depend_on_forecast_level(self):
        low = [(1000.0, float(e)) for e in range(-50, 50)]  # small errors at low wind
        high = [(7000.0, float(e)) for e in range(0, 1000, 10)]  # large +ve errors at high wind
        band = ConditionalErrorBand(low + high, bucket_mw=3000, min_count=50)
        assert band.quantiles_for(1500)[2] < 50  # centre of the 0-3 GW bucket
        assert band.quantiles_for(7500)[2] > 800  # centre of the 6-9 GW bucket

    def test_interpolates_between_bucket_centres(self):
        pairs = [(1000.0, 0.0)] * 60 + [(4000.0, 1000.0)] * 60  # centres 1.5 GW and 4.5 GW
        band = ConditionalErrorBand(pairs, bucket_mw=3000, min_count=50)
        assert band.quantiles_for(3000) == pytest.approx((500.0, 500.0, 500.0))

    def test_sparse_buckets_are_ignored_and_ends_are_clamped(self):
        pairs = [(1000.0, 0.0)] * 60 + [(10000.0, 999.0)] * 3
        band = ConditionalErrorBand(pairs, bucket_mw=3000, min_count=50)
        assert len(band.buckets) == 1
        assert band.quantiles_for(10000) == (0.0, 0.0, 0.0)

    def test_no_data(self):
        assert ConditionalErrorBand([], min_count=1).quantiles_for(1000) is None
