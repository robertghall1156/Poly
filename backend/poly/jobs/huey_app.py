"""Huey instance. SQLite-backed queue in the data directory — no Redis required.

Run the worker with:  cd backend && .venv/bin/poly worker
(That wraps `huey_consumer poly.jobs.tasks.huey`.)
"""
from __future__ import annotations

import os

from huey import SqliteHuey

from ..config import get_settings

_immediate = os.environ.get("POLY_JOBS_IMMEDIATE") == "1"  # tests: run tasks inline
huey = SqliteHuey(
    name="poly",
    filename=str(get_settings().data_path / "huey.db"),
    immediate=_immediate,
    utc=True,
)
