"""Authorization, task binding and atomic contact opportunity limits."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
import uuid

from .common import LivelyError, Store, atomic_write
from . import host
from .settings import defaults, validate

POLICY = {
    "occasional": (48 * 3600, 7 * 86400, 2),
    "regular": (24 * 3600, 7 * 86400, 4),
    "clingy": (12 * 3600, 86400, 1),
}
SCRIPT_MARKER = "# Managed by Hermes Lively v1\n"
PROMPT = (
    "Load lively:proactive-contact. A local preflight has granted one contact opportunity. "
    "Respect SOUL, USER, memory and the current work priority. Decide whether a brief, natural "
    "message to the authorized person fits. A small hello or curiosity needs no important update. "
    "Do not invent shared experiences or ask "
    "setup questions. Return only [SILENT] if there is nothing worthwhile. Otherwise your final "
    "reply is delivered automatically: do not use send_message or create another schedule."
)


def in_quiet_hours(config: dict, local) -> bool:
    if not config["quiet_hours_enabled"]:
        return False
    minute = local.hour * 60 + local.minute
    start, end = [int(t[:2]) * 60 + int(t[3:]) for t in (config["quiet_start"], config["quiet_end"])]
    return start <= minute < end if start < end else minute >= start or minute < end


def claim(store: Store, config: dict, now: float, local, expected_binding: dict | None = None) -> dict:
    """All attempt limits and the time-slot claim share one SQLite write transaction."""
    with store.transaction() as db:
        state = store.load(db)
        reason = None
        if expected_binding and any(state.get(k) != v for k, v in expected_binding.items()):
            reason = "binding_changed"
        elif not state.get("authorized") or not config["proactive_enabled"]:
            reason = "not_authorized"
        elif in_quiet_hours(config, local):
            reason = "quiet_hours"
        elif state.get("last_user_activity_at") is None or now - state["last_user_activity_at"] < 7200:
            reason = "user_active_or_unknown"
        else:
            interval, window, cap = POLICY[config["proactive_frequency"]]
            streak = max(0, int(state.get("unanswered_streak", 0)))
            cooldown = min(interval * 2 ** min(max(streak - 1, 0), 10), 7 * 86400)
            last = state.get("last_contact_attempt_at")
            if last is not None and now - last < cooldown:
                reason = "cooldown"
            elif (
                db.execute("SELECT COUNT(*) FROM attempts WHERE at > ?", (now - window,)).fetchone()[0] >= cap
            ):
                reason = "attempt_budget"
            elif db.execute("SELECT 1 FROM attempts WHERE slot=?", (int(now // 1800),)).fetchone():
                reason = "already_claimed"
        state["last_check_at"] = now
        state["last_skip_reason"] = reason
        if reason:
            store.save(db, state)
            return {"wakeAgent": False, "reason": reason}
        attempt_id = uuid.uuid4().hex
        db.execute("INSERT INTO attempts VALUES (?, ?, ?)", (attempt_id, int(now // 1800), now))
        db.execute("DELETE FROM attempts WHERE at < ?", (now - 90 * 86400,))
        state.update(
            last_contact_attempt_at=now,
            unanswered_streak=state.get("unanswered_streak", 0) + 1,
            last_attempt_id=attempt_id,
        )
        store.save(db, state)
        return {
            "wakeAgent": True,
            "context": {
                "reason": "eligible",
                "attempt_id": attempt_id,
                "current_time": local.isoformat(),
                "destination": state.get("destination"),
                "last_user_activity_at": state.get("last_user_activity_at"),
            },
        }


def validate_job(job: dict | None, state: dict, script: Path, *, paused: bool = False):
    if not job:
        raise LivelyError("Cron job not found. Create the paused job returned by prepare, then retry.")
    schedule = job.get("schedule", {})
    expected = {
        "name": "lively-proactive",
        "deliver": state["destination"],
        "failure_deliver": "local",
        "attach_to_session": True,
        "script": str(script),
        "prompt": PROMPT,
    }
    if any(job.get(k) != v for k, v in expected.items()):
        raise LivelyError("Cron binding differs from prepare. Restore its returned parameters and retry.")
    if (
        schedule.get("kind") != "interval"
        or schedule.get("minutes") != 30
        or job.get("skills") != ["lively:proactive-contact"]
        or job.get("no_agent", False)
        or job.get("monitor_script")
        or job.get("monitor_url")
        or job.get("context_from")
        or job.get("repeat", {}).get("times") is not None
    ):
        raise LivelyError("Cron must be a recurring 30m agent job with only the Lively skill and script.")
    if paused and job.get("enabled", True):
        raise LivelyError("Pause the Cron job before activate; resume only after successful activation.")


class Contact:
    def __init__(self, ctx, root: Path, home: Path | None = None):
        self.ctx, self.root = ctx, root
        self.data = Path(ctx.state.data_dir)
        # Native data namespace may change; the host owns this path, not the plugin slug.
        if home is None:
            from hermes_constants import get_hermes_home

            home = get_hermes_home()
        self.home = Path(home).resolve()
        self.store = Store(self.data)
        state = self.store.snapshot()
        identity = root / ".lively-install-id"
        if state.get("authorized") and (
            not identity.is_file()
            or identity.is_symlink()
            or identity.read_text().strip() != state.get("install_id")
            or state.get("root") != str(root)
        ):
            self.store.update(authorized=False, prepared=False)

    @property
    def script(self):
        path = Path(self.store.snapshot().get("script", self.home / "scripts" / "lively-preflight.py"))
        if not path.is_absolute() or not path.resolve().is_relative_to((self.home / "scripts").resolve()):
            raise LivelyError("Invalid managed script path. Disable contact and repair state.")
        return path

    def config(self):
        return validate({k: self.ctx.get_config(k, v) for k, v in defaults(self.root).items()}, self.root)

    def guard_owner(self):
        surface, chat = host.session_identity(self.ctx)
        if self.ctx.current_cron_execution() is not None:
            raise LivelyError("Contact settings require a user conversation, not a Cron run.")
        if surface in {"cli", "tui", "desktop", "acp"}:
            return
        state = self.store.snapshot()
        if surface != "weixin" or not chat or (state.get("chat_id") and chat != state["chat_id"]):
            raise LivelyError("Manage contact from the authorized Weixin DM or this Profile's local UI.")

    def install_identity(self):
        path = self.root / ".lively-install-id"
        if path.is_symlink():
            raise LivelyError("Remove the symlink at .lively-install-id and prepare again.")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w") as f:
                f.write(uuid.uuid4().hex)
        return path.read_text(encoding="ascii").strip()

    def prepare(self, destination: str, authorized: bool = False):
        self.guard_owner()
        if authorized is not True:
            raise LivelyError(
                "Ask the user to explicitly authorize proactive contact and its destination first."
            )
        state = self.store.snapshot()
        peers = state.get("peers", {})
        peer = peers.get(destination)
        if not peer:
            raise LivelyError(
                "Unknown destination. Send a DM to Hermes in Weixin first, then choose its observed target."
            )
        surface, chat = host.session_identity(self.ctx)
        if surface == "weixin" and chat != peer["chat_id"]:
            raise LivelyError("A Weixin user may only authorize their own DM.")
        config = host.load_config(self.home)
        if not host.enabled(config, self.ctx.plugin_id) or not host.platform_ready(config):
            raise LivelyError("Enable Lively and configure the built-in Weixin gateway before prepare.")
        if config.get("plugins", {}).get("isolation", "in_process") != "in_process":
            raise LivelyError(
                "Proactive contact currently requires plugins.isolation: in_process. "
                "Do not change this global setting without the operator's choice."
            )
        # Idempotent active prepare: return the same job instead of creating a second one.
        if (
            state.get("authorized")
            and state.get("destination") == destination
            and state.get("install_id") == self.install_identity()
            and state.get("account_id") == host.weixin_account(config)
            and state.get("template_sha256")
            == hashlib.sha256((self.root / "scripts/lively-preflight.py").read_bytes()).hexdigest()
            and self.script.is_file()
            and state.get("script_sha256") == hashlib.sha256(self.script.read_bytes()).hexdigest()
        ):
            validate_job(host.read_job(self.home, state["job_id"]), state, self.script)
            return {"already_active": True, "job_id": state["job_id"], "reminder": host.WRAP_REMINDER}
        self.ctx.set_config("proactive_enabled", False)
        self.store.update(authorized=False)
        script = self.home / "scripts" / f"lively-preflight-{uuid.uuid4().hex}.py"
        metadata = {
            "account_id": host.weixin_account(config),
            "script": str(script),
            "root": str(self.root),
            "home": str(self.home),
            "data": str(self.data),
            "plugin_id": self.ctx.plugin_id,
            "install_id": self.install_identity(),
        }
        template = (self.root / "scripts" / "lively-preflight.py").read_text(encoding="utf-8")
        metadata["template_sha256"] = hashlib.sha256(template.encode()).hexdigest()
        content = template.replace("BINDING = None", "BINDING = " + repr(metadata)).encode()
        if script.exists():
            previous = script.read_bytes()
            known_hash = state.get("script_sha256")
            if previous != content and hashlib.sha256(previous).hexdigest() != known_hash:
                raise LivelyError(
                    "Preflight file is not owned by this installation. Move it aside and prepare again."
                )
        atomic_write(script, content)
        self.store.update(
            **metadata,
            script_sha256=hashlib.sha256(content).hexdigest(),
            destination=destination,
            chat_id=peer["chat_id"],
            user_id=peer["user_id"],
            prepared=True,
            job_id=None,
        )
        params = {
            "action": "create",
            "name": "lively-proactive",
            "schedule": "30m",
            "prompt": PROMPT,
            "skills": ["lively:proactive-contact"],
            "script": str(script),
            "deliver": destination,
            "failure_deliver": "local",
            "attach_to_session": True,
            "paused": True,
            "paused_reason": "Awaiting Lively authorization verification",
        }
        return {
            "cron_parameters": params,
            "reminder": host.WRAP_REMINDER,
            "previous_job_to_pause": state.get("job_id"),
            "next": "Pause any previous_job_to_pause. Create paused via cronjob_manage; activate with returned job_id; resume and diagnose. "
            "If resume/verification fails, call disable and pause the job.",
        }

    def activate(self, job_id: str):
        self.guard_owner()
        state = self.store.snapshot()
        if not state.get("prepared") or state.get("install_id") != self.install_identity():
            raise LivelyError(
                "Installation changed or prepare missing. Obtain authorization and prepare again."
            )
        config = host.load_config(self.home)
        if (
            not host.enabled(config, self.ctx.plugin_id)
            or not host.platform_ready(config)
            or host.weixin_account(config) != state.get("account_id")
        ):
            raise LivelyError("Plugin/Weixin account changed. Obtain authorization and prepare again.")
        if hashlib.sha256(self.script.read_bytes()).hexdigest() != state.get(
            "script_sha256"
        ) or hashlib.sha256(
            (self.root / "scripts/lively-preflight.py").read_bytes()
        ).hexdigest() != state.get("template_sha256"):
            raise LivelyError("Preflight version/content changed. Disable and prepare again.")
        if host.read_job(self.home, job_id) is None:
            raise LivelyError("Cron job not found. Create the paused job returned by prepare, then retry.")
        if not host.unique_script_binding(self.home, self.script, job_id):
            raise LivelyError(
                "The preflight must be referenced by only this Cron job. Remove duplicate bindings."
            )
        job = host.read_job(self.home, job_id)
        validate_job(job, state, self.script, paused=not state.get("authorized", False))
        if state.get("authorized") and state.get("job_id") != job_id:
            raise LivelyError("Another job is already bound. Disable it before replacing the binding.")
        self.store.update(authorized=True, job_id=job_id)
        try:
            self.ctx.set_config("proactive_enabled", True)
        except Exception:
            self.store.update(authorized=False)
            raise
        return {
            "job_id": job_id,
            "authorized": True,
            "next": "Resume this job, then diagnose; disable on failure.",
            "reminder": host.WRAP_REMINDER,
        }

    def disable(self):
        self.guard_owner()
        # State revocation first also protects against a later config write failure.
        state = self.store.update(authorized=False)
        self.ctx.set_config("proactive_enabled", False)
        return {
            "authorized": False,
            "job_id_to_pause": state.get("job_id"),
            "next": "Pause or remove only this job using cronjob_manage. Qualification is already revoked.",
        }

    def configure(self, values: dict):
        self.guard_owner()
        if "proactive_enabled" in values:
            raise LivelyError("Use prepare/activate or disable to change proactive_enabled.")
        merged = validate(self.config() | values, self.root)
        for key in values:
            self.ctx.set_config(key, merged[key])
        return {"settings": self.config()}

    def status(self, diagnose: bool = False):
        self.guard_owner()
        state, config = self.store.snapshot(), self.config()
        result = {
            "settings": config,
            "authorized": state.get("authorized", False),
            "destination": state.get("destination"),
            "job_id": state.get("job_id"),
            "observed_destinations": list(state.get("peers", {})),
            "last_user_activity_at": state.get("last_user_activity_at"),
            "last_contact_attempt_at": state.get("last_contact_attempt_at"),
            "unanswered_opportunities": state.get("unanswered_streak", 0),
            "last_skip_reason": state.get("last_skip_reason"),
            "delivery": "No delivery confirmation recorded; attempts are not receipts.",
            "reminder": host.WRAP_REMINDER,
        }
        now = time.time()
        interval, window, cap = POLICY[config["proactive_frequency"]]
        streak = int(state.get("unanswered_streak", 0))
        cooldown = min(interval * 2 ** min(max(streak - 1, 0), 10), 7 * 86400)
        lower_bound = max(
            now,
            (state.get("last_user_activity_at") or now) + 7200,
            (state.get("last_contact_attempt_at") or 0) + cooldown,
        )
        with self.store.transaction() as db:
            recent = [
                row[0]
                for row in db.execute(
                    "SELECT at FROM attempts WHERE at > ? ORDER BY at DESC", (now - window,)
                )
            ]
        if len(recent) >= cap:
            lower_bound = max(lower_bound, recent[cap - 1] + window)
        result["next_possible_at_lower_bound"] = lower_bound if state.get("authorized") else None
        result["timing_note"] = (
            "Lower bound only; quiet hours, busy work, platform availability and silence may defer it."
        )
        cfg = host.load_config(self.home)
        result["cron_wrap_response"] = cfg.get("cron", {}).get("wrap_response", True)
        result["plugin_enabled"] = host.enabled(cfg, self.ctx.plugin_id)
        if diagnose and state.get("job_id"):
            job = host.read_job(self.home, state["job_id"])
            try:
                validate_job(job, state, self.script)
                expected_hash = state.get("script_sha256")
                if hashlib.sha256(self.script.read_bytes()).hexdigest() != expected_hash:
                    raise LivelyError("Preflight changed. Disable and prepare again.")
                if hashlib.sha256(
                    (self.root / "scripts/lively-preflight.py").read_bytes()
                ).hexdigest() != state.get("template_sha256"):
                    raise LivelyError("Preflight version changed. Disable and prepare again.")
                if not host.unique_script_binding(self.home, self.script, state["job_id"]):
                    raise LivelyError(
                        "Multiple Cron jobs reference this preflight. Remove duplicate bindings."
                    )
                if not host.platform_ready(cfg) or host.weixin_account(cfg) != state.get("account_id"):
                    raise LivelyError("Weixin account changed or unavailable. Reconnect and prepare again.")
                result["job_valid"] = True
            except (LivelyError, OSError) as exc:
                result.update(job_valid=False, repair=str(exc))
            result["job_enabled"] = bool(job and job.get("enabled"))
            result["host_last_status"] = job.get("last_status") if job else None
        return result
