import ast
from datetime import datetime, timezone
import json
import sqlite3
import subprocess
import sys

import pytest

from lively_under_test import host
from lively_under_test.preflight import evaluate

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc).timestamp()


def binding(contact):
    tree = ast.parse(contact.script.read_text())
    return next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "BINDING"
    )


def idle_store(home):
    with sqlite3.connect(home / "state.db") as db:
        db.executescript("""
            CREATE TABLE session_turn_leases(conversation_id TEXT, expires_at REAL);
            CREATE TABLE worker_executions(kind TEXT, status TEXT);
            CREATE TABLE session_admissions(principal_id TEXT, status TEXT);
        """)


@pytest.fixture
def gated(prepared, monkeypatch):
    contact, job = prepared
    idle_store(contact.home)
    contact.store.update(last_user_activity_at=NOW - 7200)
    monkeypatch.setattr(host, "local_datetime", lambda now, config: datetime.fromtimestamp(now, timezone.utc))
    return contact, job, binding(contact)


def test_eligible_claim_then_no_second_wake(gated):
    contact, _, metadata = gated
    assert evaluate(metadata, contact.script, now=NOW)["wakeAgent"]
    assert not evaluate(metadata, contact.script, now=NOW)["wakeAgent"]


def test_disabled_plugin_and_config_never_claim(gated):
    contact, _, metadata = gated
    contact.test_config["plugins"]["enabled"] = []
    assert evaluate(metadata, contact.script, now=NOW)["reason"] == "plugin_disabled"
    contact.test_config["plugins"]["enabled"] = ["lively"]
    contact.ctx.values["proactive_enabled"] = False
    assert not evaluate(metadata, contact.script, now=NOW)["wakeAgent"]
    assert "last_contact_attempt_at" not in contact.store.snapshot()


def test_reinstall_or_script_change_blocks(gated):
    contact, _, metadata = gated
    (contact.root / ".lively-install-id").write_text("new-install")
    assert not evaluate(metadata, contact.script, now=NOW)["wakeAgent"]
    (contact.root / ".lively-install-id").write_text(metadata["install_id"])
    contact.script.write_text(contact.script.read_text() + "\n# changed\n")
    assert evaluate(metadata, contact.script, now=NOW)["reason"] == "script_changed"


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO session_turn_leases VALUES ('coding', 9999999999)",
        "INSERT INTO worker_executions VALUES ('child','running')",
        "INSERT INTO session_admissions VALUES ('user','queued')",
        "INSERT INTO session_admissions VALUES ('user','unknown')",
    ],
)
def test_busy_work_prevents_wake(gated, sql):
    contact, _, metadata = gated
    with sqlite3.connect(contact.home / "state.db") as db:
        db.execute(sql)
    assert evaluate(metadata, contact.script, now=NOW)["reason"] == "work_active"


def test_cron_preflight_own_admission_does_not_block(gated):
    contact, _, metadata = gated
    with sqlite3.connect(contact.home / "state.db") as db:
        db.execute("INSERT INTO session_admissions VALUES ('cron-owner','started')")
        db.execute("INSERT INTO worker_executions VALUES ('cron','running')")
    assert evaluate(metadata, contact.script, now=NOW)["wakeAgent"]


def test_task_tampering_and_pause(gated):
    contact, job, metadata = gated
    path = contact.home / "cron/jobs.json"
    job["enabled"] = False
    path.write_text(json.dumps({"jobs": [job]}))
    assert evaluate(metadata, contact.script, now=NOW)["reason"] == "job_paused"
    job.update(enabled=True, deliver="all")
    path.write_text(json.dumps({"jobs": [job]}))
    with pytest.raises(ValueError):
        evaluate(metadata, contact.script, now=NOW)


def test_surviving_script_after_uninstall_returns_zero_false(prepared):
    contact, _ = prepared
    (contact.root / ".lively-install-id").unlink()
    proc = subprocess.run([sys.executable, str(contact.script)], capture_output=True, text=True)
    assert proc.returncode == 0
    assert json.loads(proc.stdout.splitlines()[-1])["wakeAgent"] is False


def test_source_template_is_safe_when_run_unprepared():
    from conftest import ROOT

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/lively-preflight.py")], capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["wakeAgent"] is False


def test_corrupt_database_never_recreated(gated):
    contact, _, _ = gated
    path = contact.home / "state.db"
    path.unlink()
    with pytest.raises(sqlite3.OperationalError):
        host.work_idle(contact.home, NOW)
    assert not path.exists()


def test_unrelated_script_not_overwritten(contact):
    from lively_under_test.hooks import Hooks

    Hooks(contact).admitted(
        platform="weixin", source={"chat_type": "dm", "chat_id": "peer", "user_id": "u"}, message_id="1"
    )
    unrelated = contact.home / "scripts/lively-preflight.py"
    unrelated.parent.mkdir()
    unrelated.write_text("# user script")
    contact.prepare("weixin:peer", True)
    assert unrelated.read_text() == "# user script"
    assert contact.script != unrelated


def test_new_preparation_revokes_old_script_binding(gated):
    contact, _, old_binding = gated
    old_script = contact.script
    contact.disable()
    contact.prepare("weixin:peer", True)
    assert old_script != contact.script
    assert not evaluate(old_binding, old_script, now=NOW)["wakeAgent"]


def test_account_switch_blocks(gated, monkeypatch):
    contact, _, metadata = gated
    monkeypatch.setattr(host, "weixin_account", lambda _: "different-account")
    assert evaluate(metadata, contact.script, now=NOW)["reason"] == "weixin_unavailable"


def test_duplicate_script_usage_blocks_even_for_other_destination(gated):
    contact, job, metadata = gated
    other = job | {"id": "unrelated", "deliver": "weixin:other-peer"}
    (contact.home / "cron/jobs.json").write_text(json.dumps({"jobs": [job, other]}))
    assert evaluate(metadata, contact.script, now=NOW)["reason"] == "duplicate_script_binding"
