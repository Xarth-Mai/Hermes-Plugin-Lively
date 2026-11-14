# Managed by Hermes Lively. Installed by lively_schedule(action="prepare").
"""No external modules or model calls until the wake gate chooses to wake."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import sys

BINDING = None


def main():
    try:
        if not isinstance(BINDING, dict):
            return {"wakeAgent": False}
        root, data, home = (Path(BINDING[k]) for k in ("root", "data", "home"))
        if not (root / "plugin.yaml").is_file() or not (home / "config.yaml").is_file():
            return {"wakeAgent": False}
        from hermes_cli.config import load_config_readonly
        cfg = load_config_readonly()
        plugins = cfg.get("plugins", {})
        if "lively" not in plugins.get("enabled", []) or "lively" in plugins.get("disabled", []):
            return {"wakeAgent": False}
        name = "lively_preflight_runtime"
        spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
        if spec is None or spec.loader is None:
            return {"wakeAgent": False}
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        from importlib import import_module
        gate = import_module(name + ".gate")
        zone = cfg.get("timezone") or None
        return gate.evaluate(data, timezone=zone)
    except Exception:
        return {"wakeAgent": False}


if __name__ == "__main__":
    print(json.dumps(main(), separators=(",", ":")))
