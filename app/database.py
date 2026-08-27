"""
PostgreSQL Database Connection and Session Management
Uses SQLAlchemy 2.0 with connection pooling and schema isolation.
"""

from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# Create SQLAlchemy Database Engine
engine = create_engine(
    settings.database_url,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={
        "options": f"-csearch_path={settings.POSTGRES_SCHEMA},public",
        "connect_timeout": 10,
    }
)

# Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base for ORM Models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request
    and ensures clean closure after request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
