from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped database session.

    Commits once the request handler returns successfully, or rolls back if
    it raises -- the orchestration layer it is used with
    (app/services/reading_orchestration.py) deliberately never commits or
    rolls back itself, so the caller (here, the API request boundary) must
    (Documentation/READING_INTEGRATION_DESIGN.md Section 14,
    INTERPRETATION_API_DESIGN.md Section 14). A GET request performs no
    write, so the commit() on its path is a harmless no-op, not a risk.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
