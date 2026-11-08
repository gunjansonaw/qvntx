"""Application settings.

Everything is read from environment variables (12-factor style) so the same code
runs unchanged on a laptop, in docker-compose, on Heroku and on Vercel.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT_PATH = BACKEND_DIR / "data" / "elexon_wind_snapshot.json.gz"

DATA_MODES = ("live", "snapshot")


def _default_cache_dir() -> Path:
    """Serverless platforms only allow writes under /tmp."""
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return Path("/tmp/wind-desk-cache")
    return BACKEND_DIR / ".cache"


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration."""

    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    # "live": Elexon API first; disk cache / bundled snapshot only if Elexon fails.
    # "snapshot": bundled snapshot only (offline demos, CI, tests - no network).
    data_mode: str = "live"
    cache_dir: Path = field(default_factory=_default_cache_dir)  # holds the last good live fetch
    snapshot_path: Path = DEFAULT_SNAPSHOT_PATH
    http_timeout_s: float = 30.0
    http_retries: int = 3
    # Month in which day-ahead purchase decisions are made (YYYY-MM).
    decision_month: str = "2026-01"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    static_dir: Path | None = None  # built React app, served by FastAPI when set
    admin_token: str | None = None  # enables POST /api/admin/refresh when set

    def __post_init__(self) -> None:
        if self.data_mode not in DATA_MODES:
            raise ValueError(f"DATA_MODE must be one of {DATA_MODES}, got {self.data_mode!r}")
        self.decision_days  # noqa: B018 - validates DECISION_MONTH eagerly

    @property
    def decision_days(self) -> tuple[date, date]:
        """First and last calendar day on which purchase decisions are made."""
        try:
            year, month = (int(part) for part in self.decision_month.split("-"))
            first = date(year, month, 1)
        except ValueError as exc:
            raise ValueError(f"DECISION_MONTH must be YYYY-MM, got {self.decision_month!r}") from exc
        next_month_first = date(year + month // 12, month % 12 + 1, 1)
        return first, next_month_first - timedelta(days=1)

    @property
    def delivery_days(self) -> tuple[date, date]:
        """Delivery days covered by those decisions (day-ahead: decision day + 1)."""
        first, last = self.decision_days
        return first + timedelta(days=1), last + timedelta(days=1)

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        defaults = cls()
        static_dir = env.get("STATIC_DIR")
        origins = env.get("CORS_ORIGINS")
        return cls(
            elexon_base_url=env.get("ELEXON_BASE_URL", defaults.elexon_base_url).rstrip("/"),
            data_mode=env.get("DATA_MODE", defaults.data_mode).strip().lower(),
            cache_dir=Path(env["CACHE_DIR"]) if env.get("CACHE_DIR") else defaults.cache_dir,
            snapshot_path=Path(env.get("SNAPSHOT_PATH", defaults.snapshot_path)),
            http_timeout_s=float(env.get("HTTP_TIMEOUT_S", defaults.http_timeout_s)),
            http_retries=int(env.get("HTTP_RETRIES", defaults.http_retries)),
            decision_month=env.get("DECISION_MONTH", defaults.decision_month),
            cors_origins=(
                tuple(o.strip() for o in origins.split(",") if o.strip()) if origins else defaults.cors_origins
            ),
            static_dir=Path(static_dir) if static_dir else None,
            admin_token=env.get("ADMIN_TOKEN") or None,
        )
