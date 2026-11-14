"""Two small, model-facing tools; Cron lifecycle belongs to Hermes."""

SCHEDULE = {
    "name": "lively_schedule",
    "description": "Prepare the Lively wake script, inspect its limits or gently tune its timing. Use native cronjob_manage to create, pause or remove delivery. Never start delivery without explicit user consent.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["prepare", "status", "tune"]},
            "settings": {"type": "object", "properties": {
                "quiet_hours": {"anyOf": [{"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2}, {"type": "null"}]},
                "cooldown_hours": {"type": "number"},
                "wake_probability": {"type": "number"},
                "next_probability": {"type": ["number", "null"]},
                "snooze_until": {"type": ["number", "null"]}
            }, "additionalProperties": False},
        }, "required": ["action"], "additionalProperties": False,
    },
}

STICKERS = {
    "name": "lively_stickers",
    "description": "Browse, search, import or remove stickers from folder-organized galleries. Return full absolute paths for native MEDIA: delivery.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "list", "search", "import", "remove"]},
            "query": {"type": "string"},
            "limit": {"type": "integer"},
            "folder": {"type": "string"},
            "path": {"type": "string"},
            "description": {"type": "string"},
            "id": {"type": "string"},
        }, "required": ["action"], "additionalProperties": False,
    },
}
