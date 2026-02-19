from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from .config import PollerSettings


def build_engine(settings: PollerSettings):
    settings.ensure_runtime_dirs()
    url = f"sqlite:///{settings.db_path}"
    return create_engine(url, echo=False, connect_args={"check_same_thread": False})


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)


def session_scope(engine):
    return Session(engine)