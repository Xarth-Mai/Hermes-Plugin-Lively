from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json

import pytest

from lively_under_test.common import LivelyError, Store
from lively_under_test.contact import claim, in_quiet_hours, validate_job
from lively_under_test.settings import defaults, validate
from conftest import ROOT

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc).timestamp()
LOCAL = datetime.fromtimestamp(NOW, timezone.utc)


def eligible(contact):
    contact.store.update(authorized=True, last_user_activity_at=NOW - 7200, unanswered_streak=0)
    return defaults(ROOT) | {"proactive_enabled": True}


def test_opt_in_and_known_dm_required(contact):
    assert contact.config()["proactive_enabled"] is False
    assert not (contact.home / "cron").exists()
    with pytest.raises(LivelyError, match="explicitly"):
        contact.prepare("weixin:peer")
    with pytest.raises(LivelyError, match="Unknown"):
        contact.prepare("weixin:peer", True)
    with pytest.raises(LivelyError, match="prepare/activate"):
        contact.configure({"proactive_enabled": True})


def test_lifecycle_and_idempotency(prepared):
    contact, job = prepared
    assert contact.status(True)["job_valid"]
    assert contact.prepare("weixin:peer", True)["job_id"] == job["id"]
    assert contact.activate(job["id"])["authorized"]
    assert contact.disable()["job_id_to_pause"] == job["id"]
    assert not contact.store.snapshot()["authorized"]
    assert not contact.config()["proactive_enabled"]
    assert contact.disable()["authorized"] is False


def test_wrong_task_not_authorized(contact):
    from lively_under_test.hooks import Hooks

    Hooks(contact).admitted(
        platform="weixin", source={"chat_type": "dm", "chat_id": "peer", "user_id": "u"}, message_id="1"
    )
    contact.prepare("weixin:peer", True)
    with pytest.raises(LivelyError, match="not found"):
        contact.activate("guessed")
    assert not contact.store.snapshot()["authorized"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("deliver", "all"),
        ("failure_deliver", "origin"),
        ("skills", ["other"]),
        ("attach_to_session", False),
        ("script", "/tmp/other.py"),
        ("prompt", "bad"),
    ],
)
def test_binding_changes_rejected(prepared, field, value):
    contact, job = prepared
    with pytest.raises(LivelyError):
        validate_job(job | {field: value}, contact.store.snapshot(), contact.script)


def test_revocation_survives_failed_config_write(prepared, monkeypatch):
    contact, _ = prepared
    monkeypatch.setattr(contact.ctx, "set_config", lambda *_: (_ for _ in ()).throw(OSError()))
    with pytest.raises(OSError):
        contact.disable()
    assert not contact.store.snapshot()["authorized"]


def test_only_owner_and_not_cron_can_manage(prepared):
    contact, _ = prepared
    contact.ctx.surface, contact.ctx.chat = "weixin", "intruder"
    with pytest.raises(LivelyError):
        contact.disable()
    contact.ctx.chat = "peer"
    contact.disable()
    contact.ctx.execution = object()
    with pytest.raises(LivelyError, match="Cron"):
        contact.configure({"stickers_enabled": False})


@pytest.mark.parametrize(
    "clock,quiet", [("22:59", False), ("23:00", True), ("00:00", True), ("07:59", True), ("08:00", False)]
)
def test_cross_midnight(clock, quiet):
    assert in_quiet_hours(defaults(ROOT), datetime.fromisoformat(f"2026-11-14T{clock}")) is quiet


@pytest.mark.parametrize(
    "patch",
    [
        {"quiet_start": "24:00"},
        {"quiet_end": "8:00"},
        {"quiet_start": "08:00", "quiet_end": "08:00"},
        {"proactive_frequency": "daily"},
        {"quiet_hours_enabled": 1},
        {"unknown": True},
    ],
)
def test_invalid_config(patch):
    with pytest.raises(LivelyError):
        validate(defaults(ROOT) | patch, ROOT)


def test_atomic_claim_across_connections(contact):
    config = eligible(contact)

    def run(_):
        return claim(Store(contact.data, create=False), config, NOW, LOCAL)["wakeAgent"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(run, range(16)))
    assert sum(outcomes) == 1
    assert contact.store.snapshot()["unanswered_streak"] == 1


def test_attempt_budget_and_backoff(contact):
    config = eligible(contact)
    assert claim(contact.store, config, NOW, LOCAL)["wakeAgent"]
    assert claim(contact.store, config, NOW + 48 * 3600, LOCAL)["wakeAgent"]
    assert claim(contact.store, config, NOW + 96 * 3600, LOCAL)["reason"] == "cooldown"
    assert claim(contact.store, config, NOW + 144 * 3600, LOCAL)["reason"] == "attempt_budget"
    assert claim(contact.store, config, NOW + 8 * 86400, LOCAL)["wakeAgent"]


def test_unknown_activity_clock_reversal_and_disabled(contact):
    config = eligible(contact)
    contact.store.update(last_user_activity_at=None)
    assert not claim(contact.store, config, NOW, LOCAL)["wakeAgent"]
    contact.store.update(last_user_activity_at=NOW + 1)
    assert not claim(contact.store, config, NOW, LOCAL)["wakeAgent"]
    assert not claim(contact.store, config | {"proactive_enabled": False}, NOW, LOCAL)["wakeAgent"]


def test_profile_and_personal_data_isolation(prepared, tmp_path):
    contact, _ = prepared
    other = Store(tmp_path / "other-profile")
    assert other.snapshot() == {}
    assert "This is never stored" not in json.dumps(contact.store.snapshot())


@pytest.mark.parametrize(
    "frequency,interval,cap",
    [("occasional", 48 * 3600, 2), ("regular", 24 * 3600, 4), ("clingy", 12 * 3600, 1)],
)
def test_each_frequency_rolling_cap(contact, frequency, interval, cap):
    config = eligible(contact) | {"proactive_frequency": frequency}
    for index in range(cap):
        contact.store.update(unanswered_streak=0)
        assert claim(contact.store, config, NOW + interval * index, LOCAL)["wakeAgent"]
    contact.store.update(unanswered_streak=0)
    outcome = claim(contact.store, config, NOW + interval * cap, LOCAL)
    assert outcome["reason"] == "attempt_budget"


def test_old_claim_cannot_use_new_authorization(contact):
    config = eligible(contact)
    contact.store.update(install_id="new", job_id="new-job")
    outcome = claim(contact.store, config, NOW, LOCAL, {"install_id": "old", "job_id": "old-job"})
    assert outcome["reason"] == "binding_changed"
    assert "last_contact_attempt_at" not in contact.store.snapshot()


def test_reinstallation_revokes_stored_authorization(prepared):
    from lively_under_test.contact import Contact

    contact, _ = prepared
    (contact.root / ".lively-install-id").unlink()
    reinstalled = Contact(contact.ctx, contact.root, contact.home)
    assert not reinstalled.store.snapshot()["authorized"]
    with pytest.raises(LivelyError, match="prepare missing"):
        reinstalled.activate("real-job")
