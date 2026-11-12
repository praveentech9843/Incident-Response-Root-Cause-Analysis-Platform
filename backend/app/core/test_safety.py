"""
Test Safety Guard Module.

Enforces that automated tests and destructive test fixtures run strictly
against an isolated test database (e.g. 'incident_platform_test'), and NEVER
against the shared development database ('incident_platform_dev') or production.
"""
from typing import Optional
from app.core.config import settings


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when tests or destructive fixtures attempt to run against development or production databases."""
    pass


DEV_DATABASE_NAME = "incident_platform_dev"
TEST_DATABASE_NAME = "incident_platform_test"


def is_safe_test_database(db_url: Optional[str] = None) -> bool:
    """
    Checks whether the given database URL (or settings.DATABASE_URL) is a safe test database.
    Returns False if connected to 'incident_platform_dev' or non-test databases.
    """
    target_url = (db_url or settings.DATABASE_URL or "").lower()
    if DEV_DATABASE_NAME in target_url:
        return False
    if ("_dev" in target_url or "/dev" in target_url) and "test" not in target_url:
        return False
    return True


def mask_database_credentials(url: str) -> str:
    """Masks user credentials in database URLs for safe logging and error reporting."""
    if not url:
        return ""
    import re
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


def assert_safe_test_environment(db_url: Optional[str] = None) -> None:
    """
    Safety guard: Verifies that tests are strictly running against a dedicated test database.
    Refuses execution if connected to the development database ('incident_platform_dev')
    or if the database name indicates a non-test environment.
    """
    target_url = (db_url or settings.DATABASE_URL or "").lower()

    if DEV_DATABASE_NAME in target_url:
        safe_url = mask_database_credentials(target_url)
        raise UnsafeTestDatabaseError(
            f"SAFETY GUARD TRIGGERED: Refusing destructive test execution on development database '{safe_url}'. "
            f"Automated test suites must run against a dedicated isolated test database (e.g. '{TEST_DATABASE_NAME}')."
        )

    # General guard: refuse if database is explicitly dev without test in the name
    if ("_dev" in target_url or "/dev" in target_url) and "test" not in target_url:
        safe_url = mask_database_credentials(target_url)
        raise UnsafeTestDatabaseError(
            f"SAFETY GUARD TRIGGERED: Database URL '{safe_url}' appears to be a development database. "
            "Refusing test execution."
        )
