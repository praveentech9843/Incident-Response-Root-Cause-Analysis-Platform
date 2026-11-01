from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, DeclarativeMeta
from app.core.database import engine, SessionLocal, Base, get_db


def test_database_engine_and_base():
    """Verify that SQLAlchemy engine, SessionLocal, and Base are configured."""
    assert isinstance(engine, Engine)
    assert SessionLocal is not None
    assert isinstance(Base, DeclarativeMeta)


def test_get_db_session_lifecycle():
    """Verify that get_db yields a session and closes cleanly."""
    gen = get_db()
    db_session = next(gen)
    assert isinstance(db_session, Session)
    try:
        next(gen)
    except StopIteration:
        pass  # Expected when generator terminates
