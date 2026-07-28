from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Ensure model metadata is registered for Alembic and table creation.
from app.db import models  # noqa: E402,F401
