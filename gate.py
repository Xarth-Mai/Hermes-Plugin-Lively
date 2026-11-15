"""Small, channel-neutral wake gate. No message routing or Hermes internals here."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import math
import os
from pathlib import Path
import random
import re
import sqlite3
import tempfile
import time
from zoneinfo import ZoneInfo

DEFAULTS = {
    "quiet_hours": ["23:00", "08:00"],
    "cooldown_hours": 5,
    "wake_probability": 0.15,
    "max_wakes_24h": 2,
    "max_wakes_7d": 12,
}
SOFT_KEYS = frozenset({"quiet_hours", "cooldown_hours", "wake_probability"})
DAY = 86400
WEEK = 7 * DAY


class LivelyError(ValueError):
    """Configuration or file error that can be shown to the Agent."""


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise LivelyError("Refusing to replace a symlink")
    fd, name = tempfile.mkstemp(prefix=".lively-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_json(path: Path, value) -> None:
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def _clock(value):
    return isinstance(value, str) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value)


def validate(config: dict) -> dict:
    if not isinstance(config, dict) or set(config) != set(DEFAULTS):
        raise LivelyError("Invalid Lively config keys")
    hours = config["quiet_hours"]
    if hours is not None and (
        not isinstance(hours, list) or len(hours) != 2
        or not all(_clock(t) for t in hours) or hours[0] == hours[1]
    ):
        raise LivelyError("quiet_hours must be null or two different HH:MM values")
    for name, lo, hi in (("cooldown_hours", 4, 168), ("wake_probability", 0, 1)):
        value = config[name]
        if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
            raise LivelyError(f"Invalid {name}")
    for name in ("max_wakes_24h", "max_wakes_7d"):
        value = config[name]
        if type(value) is not int or not 1 <= value <= 100:
            raise LivelyError(f"Invalid {name}")
    if config["max_wakes_24h"] > config["max_wakes_7d"]:
        raise LivelyError("Daily cap cannot exceed weekly cap")
    return config


def config_path(data: Path) -> Path:
    return Path(data) / "config.json"


def read_config(data: Path) -> dict:
    path = config_path(data)
    if path.is_symlink():
        raise LivelyError("Invalid config symlink")
    return validate(json.loads(path.read_text(encoding="utf-8")))


@contextmanager
def transaction(data: Path, *, create: bool = False):
    data = Path(data)
    if create:
        data.mkdir(parents=True, exist_ok=True, mode=0o700)
    db_path = data / "state.sqlite"
    if db_path.is_symlink():
        raise LivelyError("Invalid state symlink")
    mode = "rwc" if create else "rw"
    with sqlite3.connect(db_path.resolve().as_uri() + f"?mode={mode}", uri=True, timeout=5, isolation_level=None) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            if create:
                db.execute("CREATE TABLE IF NOT EXISTS wakes (at REAL PRIMARY KEY)")
                db.execute("CREATE TABLE IF NOT EXISTS preferences (id INTEGER PRIMARY KEY CHECK(id=1), next_probability REAL, snooze_until REAL)")
                db.execute("INSERT OR IGNORE INTO preferences (id) VALUES (1)")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise


def setup(data: Path) -> dict:
    data = Path(data)
    with transaction(data, create=True):
        path = config_path(data)
        if not path.exists():
            atomic_json(path, DEFAULTS)
        return read_config(data)


def in_quiet_hours(hours: list[str] | None, local: datetime) -> bool:
    if hours is None:
        return False
    start, end = (int(x[:2]) * 60 + int(x[3:]) for x in hours)
    minute = local.hour * 60 + local.minute
    return start <= minute < end if start < end else minute >= start or minute < end


def evaluate(data: Path, *, now: float | None = None, timezone: str | None = None, rng=None) -> dict:
    """Each successful wake atomically consumes a rolling-window slot, even if Agent is silent."""
    at = time.time() if now is None else now
    if not math.isfinite(at):
        raise LivelyError("Invalid clock")
    local = datetime.fromtimestamp(at, ZoneInfo(timezone)) if timezone else datetime.fromtimestamp(at).astimezone()
    with transaction(data) as db:
        cfg = read_config(data)
        if in_quiet_hours(cfg["quiet_hours"], local):
            return {"wakeAgent": False}
        row = db.execute("SELECT next_probability, snooze_until FROM preferences WHERE id=1").fetchone()
        if row is None:
            raise LivelyError("Missing wake preferences")
        override, snooze = row
        if snooze is not None and at < snooze:
            return {"wakeAgent": False}
        latest = db.execute("SELECT at FROM wakes ORDER BY at DESC LIMIT 1").fetchone()
        if latest and at - latest[0] < cfg["cooldown_hours"] * 3600:
            return {"wakeAgent": False}
        daily = db.execute("SELECT COUNT(*) FROM wakes WHERE at > ?", (at - DAY,)).fetchone()[0]
        weekly = db.execute("SELECT COUNT(*) FROM wakes WHERE at > ?", (at - WEEK,)).fetchone()[0]
        if daily >= cfg["max_wakes_24h"] or weekly >= cfg["max_wakes_7d"]:
            return {"wakeAgent": False}
        probability = override if override is not None else cfg["wake_probability"]
        if (random.random() if rng is None else rng.random()) >= probability:
            return {"wakeAgent": False}
        # PRIMARY KEY ensures duplicate runs at the same instant cannot claim twice.
        db.execute("INSERT INTO wakes (at) VALUES (?)", (at,))
        db.execute("DELETE FROM wakes WHERE at < ?", (at - WEEK,))
        db.execute("UPDATE preferences SET next_probability=NULL, snooze_until=NULL WHERE id=1")
        return {"wakeAgent": True, "context": {"current_time": local.isoformat()}}


def status(data: Path) -> dict:
    with transaction(data) as db:
        cfg = read_config(data)
        row = db.execute("SELECT next_probability, snooze_until FROM preferences WHERE id=1").fetchone()
        now = time.time()
        return {
            "settings": cfg,
            "next_probability": row[0] if row else None,
            "snooze_until": row[1] if row else None,
            "wakes_24h": db.execute("SELECT COUNT(*) FROM wakes WHERE at > ?", (now - DAY,)).fetchone()[0],
            "wakes_7d": db.execute("SELECT COUNT(*) FROM wakes WHERE at > ?", (now - WEEK,)).fetchone()[0],
        }


def tune(data: Path, changes: dict) -> dict:
    if not isinstance(changes, dict) or not changes or set(changes) - (SOFT_KEYS | {"next_probability", "snooze_until"}):
        raise LivelyError("Only quiet_hours, cooldown_hours, wake_probability, next_probability, snooze_until can be tuned")
    with transaction(data) as db:
        cfg = read_config(data)
        updated = {**cfg, **{k: v for k, v in changes.items() if k in SOFT_KEYS}}
        validate(updated)
        temp_prob = changes.get("next_probability")
        if "next_probability" in changes and temp_prob is not None and (
            type(temp_prob) not in (int, float) or not math.isfinite(temp_prob) or not 0 <= temp_prob <= 1
        ):
            raise LivelyError("Invalid next_probability")
        snooze = changes.get("snooze_until")
        if "snooze_until" in changes and snooze is not None and (
            type(snooze) not in (int, float) or not math.isfinite(snooze) or not time.time() <= snooze <= time.time() + 30 * DAY
        ):
            raise LivelyError("snooze_until must be a future Unix timestamp within 30 days")
        if "next_probability" in changes:
            db.execute("UPDATE preferences SET next_probability=? WHERE id=1", (temp_prob,))
        if "snooze_until" in changes:
            db.execute("UPDATE preferences SET snooze_until=? WHERE id=1", (snooze,))
        if updated != cfg:
            atomic_json(config_path(data), updated)
    return status(data)
