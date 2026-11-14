"""Fail-closed gate, callable from the surviving managed script without a loaded plugin."""

from __future__ import annotations

import hashlib
from pathlib import Path
import time

from .common import Store
from .contact import claim, validate_job
from . import host


def evaluate(binding: dict, script: Path, *, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    root, home, data = (Path(binding[k]) for k in ("root", "home", "data"))
    config = host.load_config(home)
    if not host.enabled(config, binding["plugin_id"]):
        return {"wakeAgent": False, "reason": "plugin_disabled"}
    if (root / ".lively-install-id").read_text().strip() != binding["install_id"]:
        return {"wakeAgent": False, "reason": "installation_changed"}
    source = root / "scripts" / "lively-preflight.py"
    if hashlib.sha256(source.read_bytes()).hexdigest() != binding["template_sha256"]:
        return {"wakeAgent": False, "reason": "script_version_changed"}
    store = Store(data, create=False)
    state = store.snapshot()
    if any(state.get(k) != v for k, v in binding.items()):
        return {"wakeAgent": False, "reason": "binding_changed"}
    if not state.get("authorized"):
        return {"wakeAgent": False, "reason": "not_authorized"}
    if hashlib.sha256(script.read_bytes()).hexdigest() != state.get("script_sha256"):
        return {"wakeAgent": False, "reason": "script_changed"}
    settings = host.settings(config, binding["plugin_id"], root)
    if not settings["proactive_enabled"]:
        return {"wakeAgent": False, "reason": "proactive_disabled"}
    job = host.read_job(home, state["job_id"])
    validate_job(job, state, script)
    if not host.unique_script_binding(home, script, state["job_id"]):
        return {"wakeAgent": False, "reason": "duplicate_script_binding"}
    if not job.get("enabled"):
        return {"wakeAgent": False, "reason": "job_paused"}
    if not host.platform_ready(config) or host.weixin_account(config) != binding["account_id"]:
        return {"wakeAgent": False, "reason": "weixin_unavailable"}
    if not host.work_idle(home, now):
        return {"wakeAgent": False, "reason": "work_active"}
    return claim(
        store, settings, now, host.local_datetime(now, config), binding | {"job_id": state["job_id"]}
    )
