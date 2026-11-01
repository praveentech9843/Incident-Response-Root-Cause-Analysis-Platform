from fastapi import FastAPI
from app.main import create_application


def test_create_application():
    """Verify that the FastAPI application instance can be created cleanly."""
    application = create_application()
    assert isinstance(application, FastAPI)
    assert application.title == "AI-Powered Incident Response & RCA Platform"
    assert application.version is not None
