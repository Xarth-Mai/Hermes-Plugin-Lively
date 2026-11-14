from __future__ import annotations

import json
import logging
from .common import LivelyError

logger = logging.getLogger(__name__)


def result(fn, args):
    try:
        if not isinstance(args, dict):
            raise LivelyError("Tool arguments must be a JSON object.")
        return json.dumps({"ok": True, **fn(args)}, ensure_ascii=False)
    except LivelyError as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
    except Exception as exc:
        # Do not leak private input paths, tokens, or message bodies into logs/tool output.
        logger.warning("Lively tool failed (%s)", type(exc).__name__)
        return json.dumps(
            {
                "ok": False,
                "error": "Operation failed safely (" + type(exc).__name__ + "). "
                "Check file permissions and Profile configuration; run diagnose before re-enabling contact.",
            }
        )


class Tools:
    def __init__(self, contact, gallery):
        self.contact, self.gallery = contact, gallery

    def contact_handler(self, args, **_):
        return result(self._contact, args)

    def _contact(self, args):
        action = args.get("action")
        if action in {"status", "diagnose"}:
            return self.contact.status(diagnose=action == "diagnose")
        if action == "configure":
            return self.contact.configure(args.get("settings", {}))
        if action == "prepare":
            return self.contact.prepare(args.get("destination", ""), args.get("authorized", False))
        if action == "activate":
            return self.contact.activate(args.get("job_id", ""))
        if action == "disable":
            return self.contact.disable()
        raise LivelyError(
            "Unknown contact action; use status, configure, prepare, activate, disable or diagnose."
        )

    def sticker_handler(self, args, **_):
        return result(self._stickers, args)

    def _stickers(self, args):
        action = args.get("action")
        enabled = self.contact.config()["stickers_enabled"]
        if action == "status":
            entries = self.gallery.entries()
            return {
                "enabled": enabled,
                "builtin_count": sum(x["source"] == "builtin" for x in entries),
                "user_count": sum(x["source"] == "user" for x in entries),
            }
        if action in {"list", "search"}:
            if not enabled and args.get("explicit") is not True:
                raise LivelyError(
                    "Stickers are disabled. Only list/search on an explicit user request (explicit=true)."
                )
            return {
                "items": self.gallery.search(
                    args.get("query", "") if action == "search" else "", args.get("limit", 10)
                )
            }
        if action in {"import", "remove"}:
            self.contact.guard_owner()
            if action == "import":
                return {
                    "item": self.gallery.import_image(
                        args.get("path", ""), args.get("description", ""), args.get("tags", [])
                    )
                }
            return self.gallery.remove(args.get("id", ""))
        raise LivelyError("Unknown sticker action; use status, list, search, import or remove.")
