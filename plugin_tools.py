"""Small Hermes tool adapters; no channel-specific behavior."""
from __future__ import annotations
import json
import logging
from pathlib import Path

from . import gate
from .stickers import Gallery

logger = logging.getLogger(__name__)


def reply(fn):
    try:
        return json.dumps({"ok": True, **fn()}, ensure_ascii=False)
    except gate.LivelyError as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Lively tool failed: %s", type(exc).__name__)
        return json.dumps({"ok": False, "error": "Lively operation failed; inspect Profile and file permissions."})


class Tools:
    def __init__(self, ctx, root: Path, home: Path | None = None):
        self.ctx, self.root = ctx, root
        self.data = Path(ctx.state.data_dir)
        if home is None:
            from hermes_constants import get_hermes_home
            home = get_hermes_home()
        self.home = Path(home).resolve()

    def _prepare(self):
        if getattr(self.ctx, "current_cron_execution", lambda: None)() is not None:
            raise gate.LivelyError("Prepare requires an interactive user session")
        cfg = gate.setup(self.data)
        template = (self.root / "scripts/lively-gate.py").read_text(encoding="utf-8")
        binding = {"root": str(self.root), "data": str(self.data), "home": str(self.home)}
        content = template.replace("BINDING = None", "BINDING = " + repr(binding))
        path = self.home / "scripts/lively-gate.py"
        if path.exists() and not path.read_text(encoding="utf-8").startswith("# Managed by Hermes Lively."):
            raise gate.LivelyError("Refusing to replace an unmanaged script: scripts/lively-gate.py")
        gate.atomic_bytes(path, content.encode())
        return {"script": "lively-gate.py", "settings": cfg,
                "next": "After explicit user authorization, create exactly one native Cron with schedule=23m, script=lively-gate.py, continuity=true, attach_to_session=true, catch_up=false, failure_deliver=local, and a verified native delivery target. Use the installed proactive-contact Skill."}

    def schedule(self, args, **_):
        def execute():
            if not isinstance(args, dict):
                raise gate.LivelyError("Expected JSON arguments")
            action = args.get("action")
            if action == "prepare":
                return self._prepare()
            if action == "status":
                return gate.status(self.data)
            if action == "tune":
                return gate.tune(self.data, args.get("settings", {}))
            raise gate.LivelyError("Use prepare, status or tune")
        return reply(execute)

    def stickers(self, args, **_):
        def execute():
            if not isinstance(args, dict):
                raise gate.LivelyError("Expected JSON arguments")
            personal, lock_data = self.data / "gallery", self.data
            shared = getattr(self.ctx, "get_config", lambda key, default=None: default)("shared_gallery", None)
            if shared is not None:
                if not isinstance(shared, str) or not Path(shared).is_absolute():
                    raise gate.LivelyError("shared_gallery must be an absolute directory")
                target = Path(shared)
                if not target.is_dir() or any(p.is_symlink() for p in (target, *target.parents)):
                    raise gate.LivelyError("shared_gallery must name a real directory without symlinks")
                if not personal.is_symlink() or personal.resolve(strict=True) != target.resolve(strict=True):
                    raise gate.LivelyError("Gallery link must match the configured shared_gallery")
                personal, lock_data = target, target / ".lively-state"
            gallery = Gallery(self.root / "assets/stickers", personal, lock_data)
            action = args.get("action")
            if action == "status":
                return gallery.status()
            if action in ("list", "search"):
                return {"items": gallery.search(args.get("query", "") if action == "search" else "", args.get("limit", 20))}
            if action == "import":
                return {"item": gallery.import_image(args.get("path", ""), args.get("description", ""), args.get("folder", "personal"))}
            if action == "remove":
                return gallery.remove(args.get("id", ""))
            raise gate.LivelyError("Use status, list, search, import or remove")
        return reply(execute)
