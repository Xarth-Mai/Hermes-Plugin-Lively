# Managed by Hermes Lively v1
"""Installed by prepare, not executable from the plugin's read-only resource directory.

The tiny bootstrap survives uninstall. Every ordinary failure emits an explicit false gate;
logs never include tokens, message contents, paths or raw exception text.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

BINDING = None


def main():
    outcome = {"wakeAgent": False}
    try:
        if not isinstance(BINDING, dict):
            return outcome
        root = Path(BINDING["root"])
        identity = root / ".lively-install-id"
        if identity.is_symlink() or identity.read_text().strip() != BINDING["install_id"]:
            return outcome
        if not (root / "plugin.yaml").is_file():
            return outcome
        name = "lively_gate_" + hashlib.sha256(str(root).encode()).hexdigest()[:12]
        spec = importlib.util.spec_from_file_location(
            name, root / "__init__.py", submodule_search_locations=[str(root)]
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        from importlib import import_module

        gate = import_module(name + ".preflight")
        outcome = gate.evaluate(BINDING, Path(__file__).resolve())
    except Exception as exc:
        print("Lively preflight skipped: " + type(exc).__name__, file=sys.stderr)
    return outcome


if __name__ == "__main__":
    print(json.dumps(main(), separators=(",", ":")))
