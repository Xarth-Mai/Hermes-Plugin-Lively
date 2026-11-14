"""Small, dependency-free persistence helpers. No chat contents are stored."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import tempfile
from contextlib import contextmanager


class LivelyError(ValueError):
    """An actionable error safe to return to the calling agent."""


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise LivelyError("Refusing a symlink destination. Remove the link and retry.")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, value) -> None:
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Store:
    def __init__(self, directory: Path, *, create: bool = True):
        self.path = Path(directory) / "data.db"
        self._allow_create = create and not self.path.exists()
        if self.path.is_symlink():
            raise LivelyError("State database must not be a symlink.")
        if create:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            with self.transaction() as db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)"
                )
                db.execute("INSERT OR IGNORE INTO state VALUES (1, '{}')")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, slot INTEGER UNIQUE, at REAL NOT NULL)"
                )
                db.execute("CREATE INDEX IF NOT EXISTS attempt_time ON attempts(at)")
            self.path.chmod(0o600)
        elif not self.path.is_file():
            raise LivelyError("State is missing. Run prepare again.")
        self._allow_create = False

    @contextmanager
    def transaction(self):
        # mode=rw cannot silently recreate a deleted/corrupt authorization store.
        if self.path.is_symlink():
            raise LivelyError("State database must not be a symlink.")
        uri = self.path.resolve().as_uri() + ("?mode=rwc" if self._allow_create else "?mode=rw")
        db = sqlite3.connect(uri, uri=True, timeout=2, isolation_level=None)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def load(db) -> dict:
        value = json.loads(db.execute("SELECT value FROM state WHERE id=1").fetchone()[0])
        if not isinstance(value, dict):
            raise LivelyError("Invalid state. Disable contact and run diagnose.")
        return value

    @staticmethod
    def save(db, state: dict):
        db.execute("UPDATE state SET value=? WHERE id=1", (json.dumps(state),))

    def snapshot(self):
        with self.transaction() as db:
            return self.load(db)

    def update(self, **changes):
        with self.transaction() as db:
            state = self.load(db)
            state.update(changes)
            self.save(db, state)
        return state
