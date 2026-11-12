from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.core.config import normalize_database_url, settings

# Ensure database URL uses valid SQLAlchemy dialect scheme selecting psycopg2
# Normalization occurs immediately before engine creation
database_url = normalize_database_url(settings.DATABASE_URL)

# Guard against any unstripped psycopg v3 dialect variants
if "+psycopg" in database_url and "+psycopg2" not in database_url:
    database_url = normalize_database_url(database_url)

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
