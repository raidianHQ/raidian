import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.seed.seed import seed_reference_data


@pytest.fixture()
def db_session():
    """A fresh, isolated in-memory SQLite database per test.

    Foreign key enforcement is off by default in SQLite and must be turned on
    per-connection, or the RESTRICT/CASCADE ondelete behavior defined on the
    models would silently not be enforced during tests.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def seeded_session(db_session: Session) -> Session:
    """A db_session with the real Rider-Waite-Smith reference data (78
    cards, correspondences, spreads) already seeded -- for tests that need
    genuine card themes (e.g. the Interpretation Engine) rather than the
    minimal placeholder content tests/factories.py builds.
    """
    seed_reference_data(db_session)
    db_session.commit()
    return db_session
