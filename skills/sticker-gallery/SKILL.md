---
name: sticker-gallery
description: Choose images from folder-based local sticker galleries and send through Hermes native MEDIA delivery.
---
# Local sticker gallery

Use `lively_stickers(action="search", query="...")` to find a suitable real image. Every folder has its own `metadata.json` with a group description and per-file captions. You can also `list` or `status`. Read descriptions and choose for the actual scene and relationship, not only the keyword. Avoid repetitive or mismatched images; usually one per reply is enough.

Put the returned full `absolute_path` after `MEDIA:` on its own line in an ordinary message. Hermes Gateway is responsible for delivery; do not use a second sender. The gallery is channel neutral. A successful tool result does not guarantee the destination displayed the image.

For an image the user explicitly authorizes, use `lively_stickers(action="import", path="/absolute/local/image.png", folder="personal", description="...")`. `folder` is a simple lowercase folder slug; custom folders can have their own metadata. `remove` accepts only personal image IDs; built-ins cannot be deleted. Supported file types are PNG, JPEG, GIF, up to 10 MiB. Do not guess file paths or download arbitrary images.

Sticker characters are media, not your own SOUL identity. Respect text-only wishes, select for conversational meaning, and fall back to text if nothing fits.
