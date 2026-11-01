import os
import psycopg2
import pytest

from app.core.config import settings
from app.core.test_safety import (
    assert_safe_test_environment,
    is_safe_test_database,
    UnsafeTestDatabaseError,
    DEV_DATABASE_NAME,
    TEST_DATABASE_NAME,
)
from app.core.database import SessionLocal
from app.models.user import User


def test_safety_guard_refuses_development_database():
    """Verify that safety guard strictly refuses execution on incident_platform_dev."""
    dev_url = "postgresql://postgres:postgres@localhost:5432/incident_platform_dev"
    with pytest.raises(UnsafeTestDatabaseError) as exc_info:
        assert_safe_test_environment(dev_url)
    assert "SAFETY GUARD TRIGGERED" in str(exc_info.value)
    assert "incident_platform_dev" in str(exc_info.value)
    assert not is_safe_test_database(dev_url)


def test_safety_guard_refuses_generic_dev_database_pattern():
    """Verify that safety guard rejects any database matching development patterns."""
    generic_dev_url = "postgresql://user:pass@localhost:5432/company_prod_dev"
    with pytest.raises(UnsafeTestDatabaseError) as exc_info:
        assert_safe_test_environment(generic_dev_url)
    assert "SAFETY GUARD TRIGGERED" in str(exc_info.value)
    assert not is_safe_test_database(generic_dev_url)


def test_safety_guard_allows_test_database():
    """Verify that safety guard permits dedicated isolated test databases."""
    test_url = "postgresql://postgres:postgres@localhost:5432/incident_platform_test"
    # Must not raise
    assert_safe_test_environment(test_url)
    assert is_safe_test_database(test_url)


def test_pytest_active_database_is_isolated_test_database():
    """Verify that tests execute strictly against the isolated test database, never dev."""
    active_url = settings.DATABASE_URL.lower()
    assert TEST_DATABASE_NAME in active_url or "test" in active_url
    assert DEV_DATABASE_NAME not in active_url
    assert settings.APP_ENV == "test"
    # Guard must validate active settings
    assert_safe_test_environment()


def test_development_database_and_real_accounts_untouched():
    """
    Verify that the shared development database is completely isolated from test execution
    and that real non-test records (including praveen) remain preserved.
    """
    dev_url = "postgresql://postgres:postgres@localhost:5432/incident_platform_dev"
    conn = psycopg2.connect(dev_url)
    try:
        cur = conn.cursor()
        # Verify praveen account exists in development database
        cur.execute("SELECT username, role, is_active FROM users WHERE username = 'praveen';")
        user = cur.fetchone()
        assert user is not None, "Development account 'praveen' must remain intact in incident_platform_dev"
        assert user[0] == "praveen"
        assert user[2] is True  # is_active

        # Verify development database has existing records that were not wiped
        cur.execute("SELECT count(*) FROM incidents;")
        incident_count = cur.fetchone()[0]
        assert incident_count > 0, "Development incidents must remain intact in incident_platform_dev"
    finally:
        conn.close()


def test_phase7_e2e_defaults_to_test_database():
    """Verify that verify_phase7_e2e defaults DB_URL to incident_platform_test."""
    from verify_phase7_e2e import DB_URL as p7_db_url
    assert TEST_DATABASE_NAME in p7_db_url.lower()
    assert DEV_DATABASE_NAME not in p7_db_url.lower()
    assert_safe_test_environment(p7_db_url)


def test_phase7_e2e_refuses_dev_backend():
    """Verify that verify_phase7_e2e refuses mutating requests if target backend has environment='development'."""
    from unittest.mock import MagicMock
    from verify_phase7_e2e import verify_target_backend_safety

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "environment": "development"}
    mock_client.get.return_value = mock_resp

    with pytest.raises(UnsafeTestDatabaseError) as exc_info:
        verify_target_backend_safety(mock_client, "http://localhost:8000")
    assert "SAFETY GUARD TRIGGERED" in str(exc_info.value)
    assert "development" in str(exc_info.value)


def test_phase7_e2e_refuses_failed_backend_probe():
    """Verify that verify_phase7_e2e refuses execution if health probe returns non-200."""
    from unittest.mock import MagicMock
    from verify_phase7_e2e import verify_target_backend_safety

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_client.get.return_value = mock_resp

    with pytest.raises(UnsafeTestDatabaseError) as exc_info:
        verify_target_backend_safety(mock_client, "http://localhost:8000")
    assert "SAFETY GUARD TRIGGERED" in str(exc_info.value)


def test_phase7_e2e_allows_test_backend():
    """Verify that verify_phase7_e2e allows execution when target backend returns environment='test'."""
    from unittest.mock import MagicMock
    from verify_phase7_e2e import verify_target_backend_safety

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok", "environment": "test"}
    mock_client.get.return_value = mock_resp

    health = verify_target_backend_safety(mock_client, "http://localhost:8001")
    assert health["environment"] == "test"


def test_phase8_e2e_safety_guard_refuses_dev_db(monkeypatch):
    """Verify that verify_phase8_e2e safety guard refuses execution if pointing to dev database."""
    from verify_phase8_e2e import enforce_phase8_test_isolation

    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/incident_platform_dev")
    with pytest.raises(UnsafeTestDatabaseError) as exc_info:
        enforce_phase8_test_isolation()
    assert "SAFETY GUARD TRIGGERED" in str(exc_info.value)
    assert "incident_platform_dev" in str(exc_info.value)


def test_phase8_e2e_safety_guard_refuses_non_test_env(monkeypatch):
    """Verify that verify_phase8_e2e safety guard refuses execution if APP_ENV is not test."""
    from verify_phase8_e2e import enforce_phase8_test_isolation

    monkeypatch.setattr(settings, "APP_ENV", "development")
    with pytest.raises(UnsafeTestDatabaseError) as exc_info:
        enforce_phase8_test_isolation()
    assert "SAFETY GUARD TRIGGERED" in str(exc_info.value)
    assert "APP_ENV='test'" in str(exc_info.value)


def test_phase8_e2e_safety_guard_allows_test_env():
    """Verify that verify_phase8_e2e safety guard passes under valid test configuration."""
    from verify_phase8_e2e import enforce_phase8_test_isolation

    # In active test environment, APP_ENV=test and DATABASE_URL=TEST_DATABASE_URL
    enforce_phase8_test_isolation()

