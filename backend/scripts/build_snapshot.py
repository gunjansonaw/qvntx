"""Rebuild the bundled fallback snapshot from the live Elexon API.

Usage (from backend/):
    python -m scripts.build_snapshot            # writes data/elexon_wind_snapshot.json.gz
    DECISION_MONTH=2026-02 python -m scripts.build_snapshot

The snapshot is committed so the app works offline, in CI and if Elexon is down.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import replace

from app.config import Settings
from app.repository import WindDataRepository
from app.snapshot import write_snapshot


async def main() -> int:
    settings = Settings.from_env()
    repo = WindDataRepository(replace(settings, data_mode="live"))
    dataset = await repo.refresh()  # refresh() always goes to the live API first
    if dataset.source != "live":
        print(f"Live fetch failed ({repo.last_error}); snapshot NOT updated.", file=sys.stderr)
        return 1
    write_snapshot(settings.snapshot_path, dict(dataset.actuals), dataset.forecasts.runs)
    print(
        f"Wrote {settings.snapshot_path} - {len(dataset.actuals)} settlement periods, "
        f"{len(dataset.forecasts)} forecast runs, {dataset.forecast_points} forecast points"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
