"""Observe trusted user activity without retaining message bodies or consuming events."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class Hooks:
    def __init__(self, contact):
        self.contact = contact

    def admitted(self, **event):
        try:
            source = event.get("source", {})
            if (
                event.get("platform") != "weixin"
                or not isinstance(source, dict)
                or source.get("chat_type") != "dm"
                or not source.get("user_id")
                or not source.get("chat_id")
                or not event.get("message_id")
            ):
                return
            if self.contact.ctx.current_cron_execution() is not None:
                return
            chat, user = str(source["chat_id"]), str(source["user_id"])
            if any(c in chat for c in (":", ",", "\n", "\r")):
                return
            now = time.time()
            with self.contact.store.transaction() as db:
                state = self.contact.store.load(db)
                peers = state.setdefault("peers", {})
                destination = f"weixin:{chat}"
                # Bounded identifiers/metadata only. Current owner is never evicted.
                if destination not in peers and len(peers) >= 32:
                    for key in list(peers):
                        if key != state.get("destination"):
                            del peers[key]
                            break
                peers[destination] = {"chat_id": chat, "user_id": user, "at": now}
                state["last_user_activity_at"] = now
                if chat == state.get("chat_id") and user == state.get("user_id"):
                    state["unanswered_streak"] = 0
                self.contact.store.save(db, state)
        except Exception:
            logger.warning("Lively activity observation unavailable; contact gate remains conservative.")

    def before_llm(self, **event):
        try:
            if (
                event.get("parent_session_id")
                or self.contact.ctx.current_cron_execution() is not None
                or event.get("platform") not in {"cli", "tui", "desktop", "acp"}
                or self.contact.ctx.session_surface() not in {"cli", "tui", "desktop", "acp"}
                or not event.get("session_id")
                or not event.get("user_message")
                or str(event.get("task_id", "")).startswith(("cron:", "subagent:", "background:"))
            ):
                return
            # This is a work/activity signal only, never a response to a Weixin contact.
            self.contact.store.update(last_user_activity_at=time.time())
        except Exception:
            logger.warning("Lively local activity observation unavailable.")
