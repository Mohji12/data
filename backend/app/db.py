from __future__ import annotations
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import get_settings


settings = get_settings()

engine = create_engine(
    settings.sqlalchemy_database_uri,
    pool_pre_ping=True,
    pool_recycle=280,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "connect_timeout": 15,
        "read_timeout": 30,
        "write_timeout": 30,
    },
    # echo=True, # Log SQL queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
