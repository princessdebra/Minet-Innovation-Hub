"""Imports every mapped class so `Base.metadata` is complete.

Use this (not `app.models`) anywhere the full schema is needed: Alembic's env,
`init_db.py`, and tests that create tables.
"""
from . import lms_models, models  # noqa: F401

__all__ = ["models", "lms_models"]
