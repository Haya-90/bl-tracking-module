"""
Real database wiring for the standalone demo — a SQLite file (not
in-memory), so data survives between requests and across server restarts.

This is the file the deliverable's ASSUMPTION comments pointed to. In the
real Fregix repo this would be Postgres-backed; here it's SQLite purely so
you can run the whole thing with `python main.py` and no extra services.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./bl_tracking_demo.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Request-scoped session. Commits on success, rolls back on error — the
    repository layer only flushes (per the architecture), so this is where
    the transaction actually lands.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
