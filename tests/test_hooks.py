from lively_under_test.hooks import Hooks


def test_trusted_dm_metadata_only_and_owner_response(prepared):
    contact, _ = prepared
    hooks = Hooks(contact)
    contact.store.update(unanswered_streak=3)
    source = {"chat_type": "dm", "chat_id": "elsewhere", "user_id": "stranger"}
    hooks.admitted(platform="weixin", source=source, message_id="2", text="secret")
    assert contact.store.snapshot()["unanswered_streak"] == 3
    source.update(chat_id="peer", user_id="owner")
    hooks.admitted(platform="weixin", source=source, message_id="3", text="secret")
    assert contact.store.snapshot()["unanswered_streak"] == 0
    assert "secret" not in str(contact.store.snapshot())


def test_groups_cron_and_incomplete_sources_ignored(contact):
    hooks = Hooks(contact)
    hooks.admitted(
        platform="weixin", source={"chat_type": "group", "chat_id": "x", "user_id": "u"}, message_id="1"
    )
    hooks.admitted(platform="weixin", source={"chat_type": "dm", "chat_id": "x"}, message_id="1")
    contact.ctx.execution = object()
    hooks.admitted(
        platform="weixin", source={"chat_type": "dm", "chat_id": "x", "user_id": "u"}, message_id="1"
    )
    assert contact.store.snapshot() == {}


def test_local_activity_does_not_clear_backoff(contact):
    contact.store.update(unanswered_streak=3)
    hook = Hooks(contact)
    event = dict(platform="cli", session_id="s", user_message="hi", task_id="t")
    hook.before_llm(**(event | {"parent_session_id": "parent"}))
    assert "last_user_activity_at" not in contact.store.snapshot()
    hook.before_llm(**event)
    assert contact.store.snapshot()["last_user_activity_at"] > 0
    assert contact.store.snapshot()["unanswered_streak"] == 3
