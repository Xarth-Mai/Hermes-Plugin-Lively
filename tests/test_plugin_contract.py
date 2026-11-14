import importlib.util
from types import SimpleNamespace
import yaml

from conftest import ROOT
from lively_under_test.settings import defaults


def test_assets_and_example_defaults():
    spec = importlib.util.spec_from_file_location("asset_validator", ROOT / "scripts/validate-assets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.validate(ROOT / "assets/stickers") < 160 * 1024
    example = yaml.safe_load((ROOT / "config.example.yaml").read_text())
    assert example["plugins"]["entries"]["lively"]["settings"] == defaults(ROOT)
    prompt = (ROOT / "prompts/behavior.md").read_text()
    assert prompt.isascii() and 300 <= len(prompt) <= 600


def test_registration_exact_tools_skills_and_hooks(plugin, tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "hermes_constants", SimpleNamespace(get_hermes_home=lambda: tmp_path))
    registered = {"tool": [], "skill": [], "hook": [], "prompt": []}

    class Context:
        plugin_id = "lively"
        state = SimpleNamespace(data_dir=tmp_path / "plugin-data" / "chosen-by-host")

        def register_tool(self, **kw):
            registered["tool"].append(kw)

        def register_skill(self, name, path):
            assert path.is_file()
            registered["skill"].append(name)

        def register_hook(self, name, callback):
            registered["hook"].append(name)

        def register_system_prompt_section(self, name, content, **kw):
            assert len(content) <= kw["max_chars"]
            registered["prompt"].append(name)

    plugin.register(Context())
    assert {t["name"] for t in registered["tool"]} == {"lively_contact", "lively_stickers"}
    assert registered["skill"] == ["proactive-contact", "sticker-gallery"]
    assert registered["hook"] == ["post_gateway_admission", "pre_llm_call"]
    assert registered["prompt"] == ["lively.behavior"]
    assert not (tmp_path / "scripts").exists()
    assert not (tmp_path / "cron").exists()
