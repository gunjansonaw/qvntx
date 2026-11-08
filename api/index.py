"""Vercel serverless entrypoint.

Vercel serves the static React build from frontend/dist and routes /api/* here
(see vercel.json). This module just exposes the same FastAPI app used everywhere else.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401  (re-exported for the Vercel Python runtime)
