"""
Dependency and DBAPI driver verification test.

Verifies that:
1. psycopg2 is installed and importable.
2. SQLAlchemy correctly resolves the postgresql dialect to the psycopg2 DBAPI.
3. The PostgreSQL engine initializes cleanly without ModuleNotFoundError.
"""
import pytest
from app.core.config import settings


def test_psycopg2_importable():
    """Verify that psycopg2 is installed and can be imported directly."""
    import psycopg2
    assert hasattr(psycopg2, "__version__")
    assert isinstance(psycopg2.__version__, str)
    assert len(psycopg2.__version__) > 0


def test_sqlalchemy_postgresql_dialect_uses_psycopg2():
    """Verify that SQLAlchemy initializes the postgresql dialect using psycopg2 as the DBAPI."""
    from sqlalchemy import create_engine

    # Test standard postgresql URL
    engine = create_engine("postgresql://user:password@localhost:5432/testdb")
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg2"
    assert engine.dialect.dbapi.__name__ == "psycopg2"


def test_sqlalchemy_engine_initialization_with_settings():
    """Verify that the engine initialized from application settings loads the psycopg2 dialect."""
    from app.core.database import engine

    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg2"
    assert engine.dialect.dbapi.__name__ == "psycopg2"

