import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.core.config import normalize_database_url, settings

# Resolve database URL from settings with environment fallback to prevent cached bypasses
raw_url = settings.DATABASE_URL or os.environ.get("DATABASE_URL", "")
database_url = normalize_database_url(raw_url)

# Final safety lock: ensure any PostgreSQL URL explicitly specifies +psycopg2 driver
if "://" in database_url and not database_url.startswith("sqlite"):
    scheme, rest = database_url.split("://", 1)
    if scheme.lower() != "postgresql+psycopg2":
        database_url = f"postgresql+psycopg2://{rest}"

# Engine configuration with dialect-specific options
connect_args = {}
engine_kwargs = {}

if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_pre_ping": True,
        }
    )

engine = create_engine(
    database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base declarative class for future database models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a transactional database session.
    Closes the session automatically when the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
