---
name: sticker-gallery
description: Find and manage local expressive stickers; send suitable images through normal Hermes MEDIA replies.
---
# Lively sticker gallery

Use stickers sparingly when a greeting, celebration, confusion, or comfort benefits from an image.
Prioritize the user's current task. Do not query every turn or insert companion chat into coding work.
Respect SOUL/USER. Match the actual tone; do not imply emotions or experiences the user did not express.

- `lively_stickers(action="search", query="happy celebrate", limit=3)` returns verified absolute paths.
  Search tags/descriptions, including Chinese tags. Prefer a suitable result not recently suggested.
- Put `MEDIA:/absolute/path` on its own line in a normal reply. Gateway sends the image; do not use
  another sender. A returned path or successful text delivery does not prove the media arrived.
- `status` reports the independent sticker setting and counts. `list` browses the gallery.
- If stickers are disabled, do not suggest/search automatically. Explicit user viewing/search requests
  may use `explicit=true`; import/remove management remains available.
- To import an image the user selected, use `import(path=<absolute local path>, description=..., tags=[...])`.
  Accept PNG/JPEG/GIF up to 10 MiB. Do not download arbitrary images or import local files unprompted.
- `remove(id=...)` deletes only a user-owned sticker; builtins remain read-only.
- Enable/disable suggestions with `lively_contact(action="configure", settings={"stickers_enabled":false})`.

Never invent an image path. If the gallery is empty/broken or a file is rejected, use text and explain
an actionable repair only if relevant. Weixin PNG delivery is the first release target; GIF animation
and other channels must be marked unverified until tested.

Match the depicted scene, caption and social intent, including irony or intimacy; similar tags do
not make two images interchangeable. Gallery characters do not replace your SOUL identity. Usually
one image per turn is sufficient. Leave a text interval after a recent image unless the tone has
changed or the user requests sticker play. If a choice misses the tone, adjust rather than insist.
A request for text only in this exchange is scoped to this exchange; a lasting preference follows
Hermes' existing user/memory rules. Do not treat a suggestion as a confirmed previous image delivery.
Keep catalog IDs and internal file paths out of ordinary chat except the native MEDIA directive.
If delivery is uncertain, report uncertainty when relevant; do not automatically resend the image.
