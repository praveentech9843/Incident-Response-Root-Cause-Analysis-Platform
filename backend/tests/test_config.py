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
