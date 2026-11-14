import importlib.util
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "lively_under_test", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
)
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)


@pytest.fixture
def plugin():
    return package


@pytest.fixture
def contact(tmp_path, monkeypatch):
    from lively_under_test.contact import Contact
    from lively_under_test import host

    root = tmp_path / "plugin"
    root.mkdir()
    for name in ["plugin.yaml", "scripts"]:
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, root / name)
        else:
            shutil.copy2(source, root / name)
    home = tmp_path / "profile"
    home.mkdir()

    class Context:
        plugin_id = "lively"
        state = SimpleNamespace(data_dir=home / "plugin-data" / "host-selected-namespace")
        surface, chat = "cli", ""
        execution = None
        values = {}

        def get_config(self, key, default=None):
            return self.values.get(key, default)

        def set_config(self, key, value):
            self.values[key] = value

        def session_surface(self):
            return self.surface

        def current_cron_execution(self):
            return self.execution

    ctx = Context()
    instance = Contact(ctx, root, home)
    config = {
        "plugins": {"enabled": ["lively"], "entries": {"lively": {"settings": ctx.values}}},
        "platforms": {"weixin": {"enabled": True}},
        "cron": {"wrap_response": False},
    }
    (home / "config.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.setattr(host, "load_config", lambda _: config)
    monkeypatch.setattr(host, "weixin_account", lambda cfg: "test-account")
    monkeypatch.setattr(host, "platform_ready", lambda cfg: cfg["platforms"]["weixin"]["enabled"])
    monkeypatch.setattr(host, "session_identity", lambda c: (c.surface, c.chat))
    instance.test_config = config
    return instance


@pytest.fixture
def prepared(contact):
    from lively_under_test.hooks import Hooks

    Hooks(contact).admitted(
        platform="weixin",
        source={"chat_type": "dm", "chat_id": "peer", "user_id": "owner"},
        message_id="msg1",
        text="This is never stored",
    )
    params = contact.prepare("weixin:peer", True)["cron_parameters"]
    job = {k: v for k, v in params.items() if k not in {"action", "paused", "paused_reason"}}
    job.update(
        id="real-job",
        schedule={"kind": "interval", "minutes": 30},
        enabled=False,
        repeat={"times": None, "completed": 0},
    )
    path = contact.home / "cron" / "jobs.json"
    path.parent.mkdir()
    import json

    path.write_text(json.dumps({"jobs": [job]}))
    contact.activate("real-job")
    job["enabled"] = True
    path.write_text(json.dumps({"jobs": [job]}))
    return contact, job
