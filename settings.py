"""Manifest defaults are the single source of configuration defaults."""

from __future__ import annotations

import re
from pathlib import Path
from .common import LivelyError


def manifest(root: Path) -> dict:
    # Hermes supplies a YAML parser; PyYAML is sufficient for standalone tests.
    try:
        from hermes_cli.config import yaml

        fast_safe_load = yaml.safe_load
    except ImportError:
        from yaml import safe_load as fast_safe_load
    return fast_safe_load((root / "plugin.yaml").read_text(encoding="utf-8"))


def defaults(root: Path) -> dict:
    return {name: spec["default"] for name, spec in manifest(root)["config_schema"].items()}


def validate(values: dict, root: Path) -> dict:
    schema = manifest(root)["config_schema"]
    if set(values) - set(schema):
        raise LivelyError("Unknown setting. Use the keys reported by status.")
    for key, value in values.items():
        expected = bool if schema[key]["type"] == "bool" else str
        if type(value) is not expected:
            raise LivelyError(f"{key} must be {expected.__name__}.")
        if "choices" in schema[key] and value not in schema[key]["choices"]:
            raise LivelyError(f"Invalid {key}; choose occasional, regular or clingy.")
    for key in ("quiet_start", "quiet_end"):
        if key in values and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", values[key]):
            raise LivelyError(f"{key} must be local HH:MM, e.g. 23:00.")
    if values.get("quiet_start") == values.get("quiet_end") and "quiet_start" in values:
        raise LivelyError("Quiet-hour endpoints must differ; use quiet_hours_enabled=false to disable.")
    return values
