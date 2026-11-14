"""Offline contract check against a pinned Hermes source checkout. No live model or Weixin sends.

Usage: python scripts/check-hermes.py --source /path/to/hermes-agent
Runs in a disposable Profile; network connects are refused. This harness intentionally inspects
host internals to test the runtime, while plugin production code uses published imports only.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

BASELINE = "bfe20f5586b3a26259f71669ad49ac85bd173f10"
ROOT = Path(__file__).resolve().parents[1]


def denied(*args, **kwargs):
    raise AssertionError("Contract tests must not access the network")


def check(source: Path):
    assert not source.is_relative_to(ROOT), "Keep the Hermes checkout outside the plugin directory."
    sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    assert sha == BASELINE, f"Expected pinned Hermes {BASELINE}, got {sha}"
    sys.path.insert(0, str(source))
    from hermes_cli.plugin_dev import doctor_plugin
    from hermes_cli.plugin_validate import validate_plugin_dir

    doctor = doctor_plugin(ROOT)
    assert not doctor.findings, doctor.findings
    validation = validate_plugin_dir(ROOT)
    assert all(ok for _, ok, _ in validation.checks), validation.checks
    assert not validation.warnings, validation.warnings
    socket.create_connection = socket.socket.connect = socket.socket.connect_ex = denied
    with tempfile.TemporaryDirectory(prefix="lively-contract-") as tmp:
        home = Path(tmp)
        os.environ["HERMES_HOME"] = str(home)
        os.environ["HERMES_BUNDLED_PLUGINS"] = str(home / "no-bundled")
        from hermes_cli.config import yaml
        from hermes_cli.plugins import PluginManager
        from gateway.session_context import set_session_vars, clear_session_vars

        target = home / "plugins" / "lively"
        target.parent.mkdir()
        shutil.copytree(
            ROOT,
            target,
            ignore=shutil.ignore_patterns(
                ".git", ".lively-install-id", "__pycache__", ".pytest_cache", ".ruff_cache"
            ),
        )
        cfg = {
            "plugins": {"enabled": ["lively"], "isolation": "in_process"},
            "timezone": "UTC",
            "cron": {"wrap_response": False},
            "platforms": {
                "weixin": {
                    "enabled": True,
                    "token": "contract-test-not-a-real-token",
                    "extra": {"account_id": "test-account", "dm_policy": "allowlist", "allow_from": ["peer"]},
                }
            },
        }
        config_path = home / "config.yaml"
        config_path.write_text(yaml.safe_dump(cfg))
        manager = PluginManager()
        manifests = manager._scan_directory(target.parent, source="user")
        assert len(manifests) == 1
        manager._load_plugin(manifests[0])
        loaded = manager._plugins["lively"]
        assert loaded.enabled and not loaded.error, loaded.error
        assert len(manager.render_system_prompt_sections({"session_id": "contract"})) == 1
        hooks = manager._hooks["post_gateway_admission"][0].__self__
        contact = hooks.contact
        host = importlib.import_module(loaded.module.__name__ + ".host")
        assert not contact.config()["proactive_enabled"]
        assert host.platform_ready(host.load_config(home))
        from hermes_state import SessionDB

        db = SessionDB(home / "state.db")
        assert host.work_idle(home)
        assert db.acquire_session_turn_lease("coding-test", "contract-holder", ttl_seconds=60)
        assert not host.work_idle(home)
        db.release_session_turn_lease("coding-test", "contract-holder")
        assert host.work_idle(home)
        hooks.admitted(
            platform="weixin",
            source={"chat_type": "dm", "chat_id": "peer", "user_id": "peer"},
            message_id="contract-inbound",
            text="must never be persisted",
        )
        tokens = set_session_vars(platform="cli", chat_id="", chat_name="")
        try:
            contact.configure({"quiet_hours_enabled": False})
            parameters = contact.prepare("weixin:peer", True)["cron_parameters"]
            from cron.jobs import create_job, get_job, resume_job, pause_job

            job = create_job(**{k: v for k, v in parameters.items() if k != "action"})
            assert not get_job(job["id"])["enabled"]
            contact.activate(job["id"])
            resume_job(job["id"])
            contact.store.update(last_user_activity_at=time.time() - 7201)
            metadata = {
                k: contact.store.snapshot()[k]
                for k in (
                    "account_id",
                    "script",
                    "root",
                    "home",
                    "data",
                    "plugin_id",
                    "install_id",
                    "template_sha256",
                )
            }
            gate = importlib.import_module(loaded.module.__name__ + ".preflight")
            assert gate.evaluate(metadata, contact.script)["wakeAgent"]
            assert not gate.evaluate(metadata, contact.script)["wakeAgent"]
            from cron.scheduler_prompt import _parse_wake_gate, _job_skill_names

            assert _parse_wake_gate('{"wakeAgent":false}') is False
            assert _job_skill_names(get_job(job["id"])) == ["lively:proactive-contact"]
            from cron.scheduler_script import _run_job_script

            ok, output = _run_job_script(str(contact.script))
            assert ok, output
            assert _parse_wake_gate(output) is False
            contact.disable()
            assert not gate.evaluate(metadata, contact.script)["wakeAgent"]
            pause_job(job["id"])
            assert not contact.status(True)["job_enabled"]
            # Disabled/removal detection does not require an unload callback.
            cfg["plugins"]["enabled"] = []
            config_path.write_text(yaml.safe_dump(cfg))
            ok, output = _run_job_script(str(contact.script))
            assert ok and _parse_wake_gate(output) is False, output
            (target / ".lively-install-id").unlink()
            ok, output = _run_job_script(str(contact.script))
            assert ok and _parse_wake_gate(output) is False, output
        finally:
            clear_session_vars(tokens)
            db.close()
    print(
        json.dumps(
            {
                "hermes_commit": sha,
                "python": sys.version.split()[0],
                "doctor": "passed",
                "validation": "passed",
                "native_cron_and_preflight": "passed",
                "work_lease_probe": "passed",
                "live_weixin": "not tested",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    check(parser.parse_args().source.resolve())
