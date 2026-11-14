"""Offline integration with a pinned Hermes checkout. No live model or messaging sends."""
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
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "bfe20f5586b3a26259f71669ad49ac85bd173f10"


def check(source: Path):
    assert source != ROOT and not source.is_relative_to(ROOT)
    sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    assert sha == BASELINE, f"Expected Hermes {BASELINE}, got {sha}"
    sys.path.insert(0, str(source))
    from hermes_cli.plugin_dev import doctor_plugin
    from hermes_cli.plugin_validate import validate_plugin_dir

    doctor = doctor_plugin(ROOT)
    assert not doctor.findings, doctor.findings
    validation = validate_plugin_dir(ROOT)
    assert all(ok for _, ok, _ in validation.checks), validation.checks
    assert not validation.warnings, validation.warnings

    with tempfile.TemporaryDirectory(prefix="lively-contract-") as temp:
        home = Path(temp)
        os.environ["HERMES_HOME"] = str(home)
        os.environ["HERMES_BUNDLED_PLUGINS"] = str(home / "no-bundled")
        from hermes_cli.config import yaml
        from hermes_cli.plugins import PluginManager
        from cron.jobs import create_job, get_job, pause_job, resume_job
        from cron.scheduler_prompt import _parse_wake_gate
        from cron.scheduler_script import _run_job_script

        target = home / "plugins/lively"
        target.parent.mkdir(parents=True)
        shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".ruff_cache"))
        cfg = {"plugins": {"enabled": ["lively"], "isolation": "in_process"},
               "timezone": "UTC", "cron": {"wrap_response": False}}
        (home / "config.yaml").write_text(yaml.safe_dump(cfg))
        manager = PluginManager()
        manifests = manager._scan_directory(target.parent, source="user")
        assert len(manifests) == 1
        manager._load_plugin(manifests[0])
        loaded = manager._plugins["lively"]
        assert loaded.enabled and not loaded.error, loaded.error
        assert len(manager.render_system_prompt_sections({"session_id": "contract"})) == 1
        assert "lively:proactive-contact" in manager._plugin_skills
        assert "lively:sticker-gallery" in manager._plugin_skills
        tools_mod = importlib.import_module(loaded.module.__name__ + ".plugin_tools")
        data = home / "plugin-data/lively"
        tools = tools_mod.Tools(SimpleNamespace(state=SimpleNamespace(data_dir=data)), target, home)
        result = json.loads(tools.schedule({"action": "prepare"}))
        assert result["ok"] and result["script"] == "lively-gate.py"
        assert json.loads(tools.stickers({"action": "status"}))["builtin_count"] == 4
        script = home / "scripts/lively-gate.py"
        assert script.is_file()
        # Native Cron's relative script path is required by the model-facing tool.
        job = create_job(
            name="lively-proactive", schedule="23m", prompt="Load lively:proactive-contact or stay [SILENT].",
            skills=["lively:proactive-contact"], script="lively-gate.py", deliver="local", failure_deliver="local",
            attach_to_session=True, context_from=["self"], catch_up=False, paused=True,
        )
        assert not get_job(job["id"])["enabled"]
        resume_job(job["id"])
        assert get_job(job["id"])["enabled"]
        # Never allow the test to make an actual model call. Script-only gate output.
        cfg["plugins"]["enabled"] = []
        (home / "config.yaml").write_text(yaml.safe_dump(cfg))
        ok, result = _run_job_script("lively-gate.py")
        assert ok and not _parse_wake_gate(result), (ok, result)
        pause_job(job["id"])
        assert not get_job(job["id"])["enabled"]

    print(json.dumps({"hermes": sha, "doctor": "passed", "plugin_validation": "passed",
                      "native_cron": "passed", "live_delivery": "not tested"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    check(parser.parse_args().source.resolve())
