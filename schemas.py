"""The complete public tool interface: two tools, finite actions, structured results."""


def schema(name, description, actions, properties):
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": {"action": {"type": "string", "enum": actions}, **properties},
            "required": ["action"],
            "additionalProperties": False,
        },
    }


CONTACT = schema(
    "lively_contact",
    "Manage explicitly authorized proactive contact and Lively settings. "
    "Never enable without the user's request. Installation agents must remind the user "
    "to set cron.wrap_response=false themselves; it affects all Profile Cron jobs.",
    ["status", "configure", "prepare", "activate", "disable", "diagnose"],
    {
        "settings": {
            "type": "object",
            "properties": {
                "proactive_frequency": {"type": "string", "enum": ["occasional", "regular", "clingy"]},
                "quiet_hours_enabled": {"type": "boolean"},
                "quiet_start": {"type": "string"},
                "quiet_end": {"type": "string"},
                "stickers_enabled": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "destination": {"type": "string", "description": "An observed weixin:<chat_id> DM from status."},
        "authorized": {"type": "boolean", "description": "True only after explicit user authorization."},
        "job_id": {"type": "string", "description": "Actual ID returned by native cronjob_manage."},
    },
)

STICKERS = schema(
    "lively_stickers",
    "Search or manage a local sticker gallery. Use returned paths "
    "with MEDIA: in a normal reply; do not send messages from the tool. Respect current work.",
    ["status", "list", "search", "import", "remove"],
    {
        "query": {"type": "string", "maxLength": 500},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        "path": {"type": "string", "description": "Absolute path to a user-authorized local image."},
        "description": {"type": "string", "maxLength": 500},
        "tags": {"type": "array", "maxItems": 30, "items": {"type": "string", "maxLength": 60}},
        "id": {"type": "string"},
        "explicit": {
            "type": "boolean",
            "description": "True for an explicit user request while stickers are off.",
        },
    },
)
