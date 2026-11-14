"""Lively native Hermes plugin. Installing it does not schedule contact."""
from pathlib import Path


def register(ctx):
    from .plugin_tools import Tools
    from .schemas import SCHEDULE, STICKERS

    tools = Tools(ctx, Path(__file__).resolve().parent)
    ctx.register_tool(name="lively_schedule", toolset="lively", schema=SCHEDULE,
                      handler=tools.schedule, description=SCHEDULE["description"])
    ctx.register_tool(name="lively_stickers", toolset="lively", schema=STICKERS,
                      handler=tools.stickers, description=STICKERS["description"])
    root = Path(__file__).resolve().parent
    ctx.register_skill("proactive-contact", root / "skills/proactive-contact/SKILL.md")
    ctx.register_skill("sticker-gallery", root / "skills/sticker-gallery/SKILL.md")
    ctx.register_system_prompt_section("lively.behavior", (root / "prompts/behavior.md").read_text(), max_chars=500)
