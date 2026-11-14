"""Narrow adapter for the pinned Hermes contracts; preflight only reads host state."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import time

from .common import LivelyError
from .settings import defaults, validate

BASELINE = "bfe20f5586b3a26259f71669ad49ac85bd173f10"
WRAP_REMINDER = (
    "请自行在当前 Profile 的 config.yaml 设置 cron.wrap_response: false，关闭 Cron 任务包装。"
    "这会影响该 Profile 的全部 Cron。插件不会自动修改；Agent 代安装时也必须向用户提醒。"
)


def load_config(home: Path) -> dict:
    from hermes_constants import get_hermes_home

    if Path(get_hermes_home()).resolve() != home.resolve():
        raise LivelyError("Profile scope mismatch. Run this tool in the owning Hermes Profile.")
    # Reject missing/malformed raw configuration before the host's forgiving merged loader.
    from hermes_cli.config import yaml

    raw = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LivelyError("Profile config is missing or invalid. Repair config.yaml first.")
    from hermes_cli.config import load_config_readonly

    config = load_config_readonly()
    if not isinstance(config, dict):
        raise LivelyError("Cannot read Profile configuration.")
    return config


def enabled(config: dict, plugin_id: str) -> bool:
    plugins = config.get("plugins", {})
    names = {plugin_id, "lively"}
    allow, deny = plugins.get("enabled"), plugins.get("disabled", [])
    return (
        isinstance(allow, list)
        and bool(names.intersection(allow))
        and isinstance(deny, list)
        and not names.intersection(deny)
    )


def settings(config: dict, plugin_id: str, root: Path) -> dict:
    entry = config.get("plugins", {}).get("entries", {}).get(plugin_id, {})
    values = defaults(root)
    # Same legacy fallback as PluginContext.get_config.
    values.update(entry.get("config", {}))
    values.update(entry.get("settings", {}))
    return validate(values, root)


def read_jobs(home: Path) -> list[dict]:
    # Strict read instead of load_jobs(), which can repair/write the user's job store.
    path = home / "cron" / "jobs.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data["jobs"] if isinstance(data, dict) else data
    if not isinstance(jobs, list) or any(not isinstance(j, dict) for j in jobs):
        raise LivelyError("Invalid Cron store. Repair it with Hermes before activation.")
    return jobs


def read_job(home: Path, job_id: str) -> dict | None:
    matches = [j for j in read_jobs(home) if j.get("id") == job_id]
    if len(matches) > 1:
        raise LivelyError("Duplicate Cron IDs. Repair the Cron store.")
    return matches[0] if matches else None


def unique_script_binding(home: Path, script: Path, job_id: str) -> bool:
    users = []
    for job in read_jobs(home):
        if not job.get("script"):
            continue
        path = Path(job["script"]).expanduser()
        if not path.is_absolute():
            path = home / "scripts" / path
        if path.resolve() == script.resolve():
            users.append(job.get("id"))
    return users == [job_id]


def work_idle(home: Path, at: float | None = None) -> bool:
    """Read-only, fail-closed probe of durable turns, admissions and background workers.

    The preflight runs before its own agent acquires a turn lease. Its Cron admission/worker
    is ignored; other active Cron conversations still hold turn leases and block contact.
    Schema changes or a missing store raise, causing the outer gate to skip.
    """
    at = time.time() if at is None else at
    with sqlite3.connect((home / "state.db").resolve().as_uri() + "?mode=ro", uri=True, timeout=1) as db:
        queries = [
            ("SELECT 1 FROM session_turn_leases WHERE expires_at > ? LIMIT 1", (at,)),
            ("SELECT 1 FROM worker_executions WHERE kind != 'cron' AND status != 'terminal' LIMIT 1", ()),
            (
                "SELECT 1 FROM session_admissions WHERE principal_id != 'cron-owner' "
                "AND status IN ('queued','started','unknown') LIMIT 1",
                (),
            ),
        ]
        return not any(db.execute(sql, params).fetchone() for sql, params in queries)


def local_datetime(at: float, config: dict):
    from datetime import datetime
    import os
    from zoneinfo import ZoneInfo
    from hermes_constants import get_hermes_home, get_process_hermes_home

    # An environment timezone belongs to the process Profile, never a routed satellite.
    multiplex = config.get("gateway", {}).get("multiplex_profiles", config.get("multiplex_profiles", False))
    own_process = Path(get_hermes_home()).resolve() == Path(get_process_hermes_home()).resolve()
    env_zone = os.getenv("HERMES_TIMEZONE", "").strip() if own_process and not multiplex else ""
    name = env_zone or config.get("timezone", "")
    return datetime.fromtimestamp(at, ZoneInfo(name)) if name else datetime.fromtimestamp(at).astimezone()


def session_identity(ctx) -> tuple[str, str]:
    from gateway.session_context import get_session_env

    surface = ctx.session_surface()
    chat = get_session_env("HERMES_SESSION_CHAT_ID", "")
    if surface == "weixin" and get_session_env("HERMES_SESSION_CHAT_TYPE", "") != "dm":
        chat = ""
    return surface, chat


def platform_ready(config: dict) -> bool:
    # Use the native loader: gateway setup may save credentials in .env rather than config.yaml.
    # This reads configuration only and does not connect, log in, or copy any credentials.
    from gateway.config import Platform, load_gateway_config

    gateway = load_gateway_config(strict=True)
    platform = gateway.platforms.get(Platform.WEIXIN)
    return bool(platform and platform.enabled and platform.extra.get("dm_policy") != "disabled")


def weixin_account(config: dict) -> str:
    from gateway.config import Platform, load_gateway_config

    platform = load_gateway_config(strict=True).platforms.get(Platform.WEIXIN)
    account = str(platform.extra.get("account_id") or "") if platform else ""
    if not account:
        raise LivelyError("Weixin account is unavailable. Complete hermes gateway setup first.")
    return account
