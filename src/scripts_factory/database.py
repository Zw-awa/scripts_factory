from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, URL, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def create_database_engine(path: Path) -> Engine:
    engine = create_engine(URL.create("sqlite", database=str(path)), future=True)

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(memory_id UNINDEXED, content, kind, scope)"))
        connection.execute(text("CREATE TRIGGER IF NOT EXISTS memory_fts_insert AFTER INSERT ON memories BEGIN INSERT INTO memory_fts(memory_id, content, kind, scope) VALUES (new.id, new.content, new.kind, new.scope); END"))
        connection.execute(text("CREATE TRIGGER IF NOT EXISTS memory_fts_update AFTER UPDATE ON memories BEGIN DELETE FROM memory_fts WHERE memory_id = old.id; INSERT INTO memory_fts(memory_id, content, kind, scope) VALUES (new.id, new.content, new.kind, new.scope); END"))
        connection.execute(text("CREATE TRIGGER IF NOT EXISTS memory_fts_delete AFTER DELETE ON memories BEGIN DELETE FROM memory_fts WHERE memory_id = old.id; END"))


class Database:
    def __init__(self, path: Path):
        self.engine = create_database_engine(path)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
