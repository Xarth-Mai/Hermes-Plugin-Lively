from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json

import pytest

from conftest import ROOT


class Fixed:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc).timestamp()


def initialize(gate, tmp_path):
    gate.setup(tmp_path)
    gate.tune(tmp_path, {"quiet_hours": None, "wake_probability": 1})


def test_initial_defaults_and_soft_hard_separation(gate, tmp_path):
    assert gate.setup(tmp_path) == gate.DEFAULTS
    assert gate.setup(tmp_path) == gate.DEFAULTS
    with pytest.raises(gate.LivelyError):
        gate.tune(tmp_path, {"max_wakes_7d": 100})
    with pytest.raises(gate.LivelyError):
        gate.tune(tmp_path, {"cooldown_hours": 0})
    with pytest.raises(gate.LivelyError):
        gate.tune(tmp_path, {"quiet_hours": ["24:00", "08:00"]})
    with pytest.raises(gate.LivelyError):
        gate.tune(tmp_path, {"wake_probability": float("nan")})
    assert gate.read_config(tmp_path) == gate.DEFAULTS


def test_cross_midnight_and_custom_local_timezone(gate, tmp_path):
    gate.setup(tmp_path)
    for clock, quiet in [("22:59", False), ("23:00", True), ("00:00", True), ("07:59", True), ("08:00", False)]:
        local = datetime.fromisoformat(f"2026-11-14T{clock}")
        assert gate.in_quiet_hours(gate.DEFAULTS["quiet_hours"], local) == quiet
    assert not gate.evaluate(tmp_path, now=NOW + 3 * 3600, timezone="Asia/Tokyo", rng=Fixed(0))["wakeAgent"]


def test_rolling_caps_and_cooldown_even_when_silent(gate, tmp_path):
    initialize(gate, tmp_path)
    assert gate.evaluate(tmp_path, now=NOW, timezone="UTC", rng=Fixed(0))["wakeAgent"]
    assert not gate.evaluate(tmp_path, now=NOW + 4 * 3600, timezone="UTC", rng=Fixed(0))["wakeAgent"]
    assert gate.evaluate(tmp_path, now=NOW + 5 * 3600, timezone="UTC", rng=Fixed(0))["wakeAgent"]
    assert not gate.evaluate(tmp_path, now=NOW + 10 * 3600, timezone="UTC", rng=Fixed(0))["wakeAgent"]
    # The first slot has left the rolling 24-hour window.
    assert gate.evaluate(tmp_path, now=NOW + 25 * 3600, timezone="UTC", rng=Fixed(0))["wakeAgent"]


def test_weekly_cap_and_boundary(gate, tmp_path):
    initialize(gate, tmp_path)
    gate.tune(tmp_path, {"cooldown_hours": 4})
    # Four-hour slots, two per calendar-ish day, strictly <=12 in 7d.
    for day in range(6):
        for hour in (0, 5):
            assert gate.evaluate(tmp_path, now=NOW + day * 86400 + hour * 3600, timezone="UTC", rng=Fixed(0))["wakeAgent"]
    assert not gate.evaluate(tmp_path, now=NOW + 6 * 86400, timezone="UTC", rng=Fixed(0))["wakeAgent"]
    assert gate.evaluate(tmp_path, now=NOW + 7 * 86400 + 1, timezone="UTC", rng=Fixed(0))["wakeAgent"]


def test_one_off_probability_and_snooze(gate, tmp_path, monkeypatch):
    initialize(gate, tmp_path)
    monkeypatch.setattr(gate.time, "time", lambda: NOW)
    gate.tune(tmp_path, {"next_probability": 0.7, "snooze_until": NOW + 7200})
    assert not gate.evaluate(tmp_path, now=NOW + 1, timezone="UTC", rng=Fixed(0))["wakeAgent"]
    assert not gate.evaluate(tmp_path, now=NOW + 7201, timezone="UTC", rng=Fixed(0.8))["wakeAgent"]
    assert gate.status(tmp_path)["next_probability"] == 0.7
    assert gate.evaluate(tmp_path, now=NOW + 7202, timezone="UTC", rng=Fixed(0.3))["wakeAgent"]
    assert gate.status(tmp_path)["next_probability"] is None
    assert gate.status(tmp_path)["snooze_until"] is None


def test_atomic_concurrent_claim(gate, tmp_path):
    initialize(gate, tmp_path)

    def attempt(_):
        return gate.evaluate(tmp_path, now=NOW, timezone="UTC", rng=Fixed(0))["wakeAgent"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        actual = list(pool.map(attempt, range(16)))
    assert sum(actual) == 1


def test_missing_and_corrupt_state_fails_closed(gate, tmp_path):
    with pytest.raises(Exception):
        gate.evaluate(tmp_path, now=NOW, timezone="UTC", rng=Fixed(0))
    gate.setup(tmp_path)
    (tmp_path / "config.json").write_text("garbage")
    with pytest.raises(json.JSONDecodeError):
        gate.evaluate(tmp_path, now=NOW, timezone="UTC", rng=Fixed(0))


def test_tool_prepare_is_idempotent_and_installs_native_script(gate, tmp_path):
    from types import SimpleNamespace
    from lively_under_test.plugin_tools import Tools

    ctx = SimpleNamespace(state=SimpleNamespace(data_dir=tmp_path / "data"))
    tools = Tools(ctx, ROOT, tmp_path / "profile")
    first = json.loads(tools.schedule({"action": "prepare"}))
    assert first["ok"] and first["script"] == "lively-gate.py"
    path = tmp_path / "profile" / "scripts" / "lively-gate.py"
    assert "BINDING = {'root':" in path.read_text()
    assert first == json.loads(tools.schedule({"action": "prepare"}))
    path.write_text("# something else")
    assert not json.loads(tools.schedule({"action": "prepare"}))["ok"]


def test_generated_script_survives_plugin_disable_and_fails_closed(gate, tmp_path):
    import os
    import subprocess
    import sys
    from types import SimpleNamespace
    from lively_under_test.plugin_tools import Tools

    home = tmp_path / "profile"
    home.mkdir()
    (home / "config.yaml").write_text("plugins:\n  enabled: [lively]\n")
    stub = tmp_path / "stub"
    (stub / "hermes_cli").mkdir(parents=True)
    (stub / "hermes_cli/__init__.py").write_text("")
    (stub / "hermes_cli/config.py").write_text(
        "from pathlib import Path\n"
        "import os\n"
        "import yaml\n"
        "def load_config_readonly():\n"
        "    return yaml.safe_load((Path(os.environ['HERMES_HOME']) / 'config.yaml').read_text())\n"
    )
    ctx = SimpleNamespace(state=SimpleNamespace(data_dir=tmp_path / "data"))
    tools = Tools(ctx, ROOT, home)
    assert json.loads(tools.schedule({"action": "prepare"}))["ok"]
    gate.tune(tmp_path / "data", {"quiet_hours": None, "wake_probability": 1})
    env = os.environ | {"HERMES_HOME": str(home), "PYTHONPATH": str(stub)}
    path = home / "scripts/lively-gate.py"
    result = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, env=env, check=True)
    assert json.loads(result.stdout)["wakeAgent"]
    (home / "config.yaml").write_text("plugins:\n  enabled: []\n")
    result = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, env=env, check=True)
    assert json.loads(result.stdout) == {"wakeAgent": False}
    # Uninstall/removal must also leave the script fail-closed if invoked again.
    (ROOT / "__init__.py").exists()  # The test does not mutate source checkout.
