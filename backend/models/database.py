"""
Database configuration for the ERP system.

Provides SQLAlchemy engine, session factory, declarative base,
and a dependency-injection compatible get_db() generator.

Supports both SQLite (local development) and PostgreSQL (production)
via the DATABASE_URL environment variable.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Determine database URL
# ---------------------------------------------------------------------------
# If DATABASE_URL is set (e.g. on Render / Railway), use PostgreSQL.
# Otherwise fall back to local SQLite for development.

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    # Render / Heroku provide postgres:// but SQLAlchemy 2.x requires
    # postgresql:// — fix it automatically.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
else:
    SQLALCHEMY_DATABASE_URL = "sqlite:///./erp_system.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a SQLAlchemy session.

    Usage::

        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
