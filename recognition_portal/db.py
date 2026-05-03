import os
from contextlib import contextmanager
from pathlib import Path

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool


Base = declarative_base()


def database_url_from_env(instance_path: str) -> str:
    default_path = Path(instance_path) / "portal.db"
    os.makedirs(default_path.parent, exist_ok=True)
    return os.getenv("DATABASE_URL", f"sqlite:///{default_path}")


def build_engine(database_url: str):
    engine_kwargs: dict = {"future": True}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    if database_url in {"sqlite://", "sqlite:///:memory:"}:
        engine_kwargs["poolclass"] = StaticPool
    return create_engine(database_url, **engine_kwargs)


def init_database(app: Flask) -> None:
    from . import models  # noqa: F401

    engine = build_engine(app.config["DATABASE_URL"])
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    Base.metadata.create_all(engine)
    app.extensions["database"] = {
        "engine": engine,
        "session_factory": session_factory,
    }


@contextmanager
def session_scope(app: Flask):
    session = app.extensions["database"]["session_factory"]()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
