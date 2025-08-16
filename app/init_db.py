from __future__ import annotations

from app.database import Base, engine
from app import models  # noqa: F401 - ensure models are imported so tables are created


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
