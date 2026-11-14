"""Hermes Native Plugin entrypoint. Importing this package does not authorize contact."""

from pathlib import Path


def register(ctx):
    from .contact import Contact
    from .hooks import Hooks
    from .schemas import CONTACT, STICKERS
    from .stickers import Gallery
    from .plugin_tools import Tools

    root = Path(__file__).resolve().parent
    contact = Contact(ctx, root)
    gallery = Gallery(root, contact.data, contact.store)
    tools, hooks = Tools(contact, gallery), Hooks(contact)
    ctx.register_tool(
        name="lively_contact",
        toolset="lively",
        schema=CONTACT,
        handler=tools.contact_handler,
        description=CONTACT["description"],
    )
    ctx.register_tool(
        name="lively_stickers",
        toolset="lively",
        schema=STICKERS,
        handler=tools.sticker_handler,
        description=STICKERS["description"],
    )
    ctx.register_hook("post_gateway_admission", hooks.admitted)
    ctx.register_hook("pre_llm_call", hooks.before_llm)
    ctx.register_skill("proactive-contact", root / "skills" / "proactive-contact" / "SKILL.md")
    ctx.register_skill("sticker-gallery", root / "skills" / "sticker-gallery" / "SKILL.md")
    ctx.register_system_prompt_section(
        "lively.behavior", (root / "prompts" / "behavior.md").read_text(), max_chars=600
    )
