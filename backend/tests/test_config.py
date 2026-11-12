import os
from unittest import mock
from app.core.config import Settings


def test_default_config_loading():
    """Verify that configuration settings load with sensible defaults."""
    cfg = Settings()
    assert cfg.APP_NAME == "AI-Powered Incident Response & RCA Platform"
    assert cfg.API_V1_PREFIX == "/api/v1"
    assert isinstance(cfg.CORS_ORIGINS, list)
    assert len(cfg.CORS_ORIGINS) > 0
    assert "postgresql://" in cfg.DATABASE_URL or "sqlite" in cfg.DATABASE_URL


def test_custom_env_config_loading():
    """Verify that settings correctly load custom environment variables."""
    custom_env = {
        "DATABASE_URL": "postgresql://testuser:testpass@localhost:5432/testdb",
        "APP_ENV": "staging",
        "SECRET_KEY": "super-secret-staging-key-12345",
        "CORS_ORIGINS": '["http://staging.example.com"]',
        "DB_POOL_SIZE": "15",
    }
    with mock.patch.dict(os.environ, custom_env):
        cfg = Settings()
        assert cfg.DATABASE_URL == "postgresql://testuser:testpass@localhost:5432/testdb"
        assert cfg.APP_ENV == "staging"
        assert cfg.SECRET_KEY == "super-secret-staging-key-12345"
        assert cfg.CORS_ORIGINS == ["http://staging.example.com"]
        assert cfg.DB_POOL_SIZE == 15


def test_postgres_scheme_normalization():
    """Verify that postgres:// (common in Neon, Render, Heroku) is normalized to postgresql://."""
    legacy_env = {
        "DATABASE_URL": "postgres://neondb_owner:npg_secret@ep-cool.neon.tech/neondb?sslmode=require",
        "TEST_DATABASE_URL": "postgres://neondb_owner:npg_secret@ep-cool.neon.tech/neondb_test?sslmode=require",
    }
    with mock.patch.dict(os.environ, legacy_env):
        cfg = Settings()
        assert cfg.DATABASE_URL.startswith("postgresql://")
        assert cfg.TEST_DATABASE_URL.startswith("postgresql://")
        assert "postgres://" not in cfg.DATABASE_URL
        assert "postgres://" not in cfg.TEST_DATABASE_URL


def test_postgresql_and_psycopg_driver_url_handling():
    """
    Regression test verifying:
    - postgresql:// is preserved and resolves to psycopg2
    - postgresql+psycopg2:// is preserved and resolves to psycopg2
    - postgresql+psycopg:// is normalized to postgresql:// to prevent ModuleNotFoundError: No module named 'psycopg'
    - Handles leading/trailing whitespace, newlines, and surrounding quotes
    - Handles postgresql+psycopg3://, postgres+psycopg://, postgres+psycopg3://
    - Credential masking protects database secrets in logs and assertions
    """
    from app.core.config import normalize_database_url
    from app.core.test_safety import mask_database_credentials

    # 1. postgresql://
    url_pg = "postgresql://myuser:mypassword@ep-cool.neon.tech/neondb?sslmode=require"
    norm_pg = normalize_database_url(url_pg)
    assert norm_pg.startswith("postgresql://")
    assert not norm_pg.startswith("postgresql+psycopg://")

    # 2. postgresql+psycopg2://
    url_psycopg2 = "postgresql+psycopg2://myuser:mypassword@ep-cool.neon.tech/neondb?sslmode=require"
    norm_psycopg2 = normalize_database_url(url_psycopg2)
    assert norm_psycopg2.startswith("postgresql+psycopg2://")

    # 3. postgresql+psycopg:// (psycopg v3 scheme) -> normalized to postgresql://
    url_psycopg3 = "postgresql+psycopg://myuser:mypassword@ep-cool.neon.tech/neondb?sslmode=require"
    norm_psycopg3 = normalize_database_url(url_psycopg3)
    assert norm_psycopg3.startswith("postgresql://")
    assert "+psycopg:" not in norm_psycopg3
    assert "+psycopg/" not in norm_psycopg3

    # 4. Whitespace and newlines
    url_whitespace = "   \n  postgresql+psycopg://myuser:mypassword@ep-cool.neon.tech/neondb?sslmode=require  \t  "
    norm_whitespace = normalize_database_url(url_whitespace)
    assert norm_whitespace.startswith("postgresql://")
    assert "+psycopg" not in norm_whitespace

    # 5. Surrounding double quotes
    url_dquotes = '"postgresql+psycopg://myuser:mypassword@ep-cool.neon.tech/neondb?sslmode=require"'
    norm_dquotes = normalize_database_url(url_dquotes)
    assert norm_dquotes.startswith("postgresql://")
    assert "+psycopg" not in norm_dquotes

    # 6. Surrounding single quotes
    url_squotes = "'postgresql+psycopg://myuser:mypassword@ep-cool.neon.tech/neondb?sslmode=require'"
    norm_squotes = normalize_database_url(url_squotes)
    assert norm_squotes.startswith("postgresql://")
    assert "+psycopg" not in norm_squotes

    # 7. postgresql+psycopg3://
    url_v3 = "postgresql+psycopg3://myuser:mypassword@ep-cool.neon.tech/neondb?sslmode=require"
    norm_v3 = normalize_database_url(url_v3)
    assert norm_v3.startswith("postgresql://")
    assert "+psycopg" not in norm_v3

    # 8. postgres+psycopg3://
    url_pg_v3 = "postgres+psycopg3://myuser:mypassword@ep-cool.neon.tech/neondb?sslmode=require"
    norm_pg_v3 = normalize_database_url(url_pg_v3)
    assert norm_pg_v3.startswith("postgresql://")
    assert "+psycopg" not in norm_pg_v3

    # 9. Case insensitivity
    url_upper = "POSTGRESQL+PSYCOPG://myuser:mypassword@ep-cool.neon.tech/neondb?sslmode=require"
    norm_upper = normalize_database_url(url_upper)
    assert norm_upper.startswith("postgresql://")
    assert "+psycopg" not in norm_upper

    # 10. Credential masking ensures passwords are not exposed
    masked = mask_database_credentials(url_pg)
    assert "mypassword" not in masked
    assert "myuser:***@" in masked
