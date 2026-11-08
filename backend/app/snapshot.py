"""Gzipped-JSON persistence for datasets (disk cache + bundled fallback snapshot).

Format (schema 1), kept deliberately human-readable:

    {
      "schema": 1,
      "writtenAt": "2026-11-08T12:00:00Z",
      "source": "Elexon BMRS Insights API (FUELHH, WINDFOR)",
      "actuals":   [["2026-01-02T00:00:00Z", 15538.0], ...],          # start, MW
      "forecasts": [["2026-01-01T07:30:00Z", "2026-01-02T00:00:00Z", 19960.0], ...]
                                                                       # publish, start, MW
    }
"""

from __future__ import annotations

import gzip
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .domain import ForecastRun

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SnapshotContents:
    actuals: dict[datetime, float]
    runs: list[ForecastRun]
    written_at: datetime


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def write_snapshot(path: Path, actuals: dict[datetime, float], runs: list[ForecastRun]) -> None:
    """Atomically write a snapshot (temp file + rename) so readers never see half a file."""
    payload = {
        "schema": SCHEMA_VERSION,
        "writtenAt": _iso(datetime.now(UTC)),
        "source": "Elexon BMRS Insights API (FUELHH, WINDFOR)",
        "actuals": [[_iso(start), value] for start, value in sorted(actuals.items())],
        "forecasts": [
            [_iso(run.publish_time), _iso(start), value] for run in runs for start, value in run.values.items()
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
            gz.write(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def read_snapshot(path: Path) -> SnapshotContents:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"unsupported snapshot schema {payload.get('schema')!r} in {path}")

    actuals = {_parse(start): float(value) for start, value in payload["actuals"]}
    grouped: dict[datetime, dict[datetime, float]] = {}
    for publish, start, value in payload["forecasts"]:
        grouped.setdefault(_parse(publish), {})[_parse(start)] = float(value)
    runs = [ForecastRun(publish, dict(sorted(values.items()))) for publish, values in sorted(grouped.items())]
    return SnapshotContents(actuals=actuals, runs=runs, written_at=_parse(payload["writtenAt"]))
