import os
import sys
from pathlib import Path
from typing import Generator
import pytest
from dotenv import load_dotenv

# Load backend/.env if available
_backend_env = Path(__file__).resolve().parent.parent / ".env"
if _backend_env.exists():
    load_dotenv(_backend_env)

# Ensure test environment variables BEFORE importing app, settings, or database engine
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "true"

# Define dedicated isolated test database
DEFAULT_TEST_DB_URL = "postgresql://postgres:postgres@localhost:5432/incident_platform_test"
DEV_DB_NAME = "incident_platform_dev"
TEST_DB_NAME = "incident_platform_test"

# If TEST_DATABASE_URL is provided, use it; otherwise resolve test database URL
test_db_url = os.environ.get("TEST_DATABASE_URL")
if not test_db_url:
    current_db_url = os.environ.get("DATABASE_URL", "")
    if DEV_DB_NAME in current_db_url:
        test_db_url = current_db_url.replace(DEV_DB_NAME, TEST_DB_NAME)
    elif TEST_DB_NAME in current_db_url:
        test_db_url = current_db_url
    elif "neondb" in current_db_url and "neondb_test" not in current_db_url:
        test_db_url = current_db_url.replace("/neondb?", "/neondb_test?").replace("/neondb", "/neondb_test")
    else:
        test_db_url = DEFAULT_TEST_DB_URL

# Override DATABASE_URL so all settings, engines, and SessionLocal instances bind to test DB
os.environ["DATABASE_URL"] = test_db_url

# Import all models first to ensure complete metadata registration for table creation
import app.models

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.test_safety import assert_safe_test_environment, UnsafeTestDatabaseError
from app.main import create_application, app as fastapi_app
from fastapi.testclient import TestClient


def _ensure_test_database_ready() -> None:
    """Creates the test database if it does not already exist."""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    db_url = settings.DATABASE_URL
    if "postgresql" in db_url and (TEST_DB_NAME in db_url or "test" in db_url):
        try:
            # Check if we can connect directly
            conn = psycopg2.connect(db_url)
            conn.close()
        except Exception:
            # Connect to postgres maintenance DB to create test DB
            try:
                maint_url = db_url.rsplit("/", 1)[0] + "/postgres"
                mconn = psycopg2.connect(maint_url)
                mconn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                mcur = mconn.cursor()
                target_db = "neondb_test" if "neondb" in db_url else TEST_DB_NAME
                mcur.execute(f"CREATE DATABASE {target_db};")
                mconn.close()
            except Exception:
                pass


@pytest.fixture(scope="session", autouse=True)
def enforce_test_database_isolation():
    """
    Session-level safety guard:
    1. Strictly refuses test execution if connected to incident_platform_dev.
    2. Ensures dedicated test database exists and all tables are created.
    """
    assert_safe_test_environment(settings.DATABASE_URL)
    _ensure_test_database_ready()
    Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """Test client fixture for making requests to FastAPI."""
    with TestClient(fastapi_app) as c:
        yield c

