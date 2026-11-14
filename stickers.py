"""Local gallery: bounded imports, immutable builtins, safe owned paths and lexical search."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import re
import stat
import struct
import uuid

from .common import LivelyError, atomic_write, read_json, write_json

MAX_BYTES = 10 * 1024 * 1024


def image_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 33 and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        if width and height and data[-8:-4] == b"IEND":
            return "png"
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 14 and data[-1:] == b";":
        if all(struct.unpack("<HH", data[6:10])):
            return "gif"
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "jpeg"
    raise LivelyError("Not a supported PNG, JPEG or GIF. Export a valid image and retry.")


def checked_file(base: Path, relative: str) -> Path:
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise LivelyError("Invalid gallery path. Repair the gallery manifest.")
    path = base / relative
    current = path
    while current != base.parent:
        if current.is_symlink():
            raise LivelyError("Gallery symlinks are not allowed.")
        if current == base:
            break
        current = current.parent
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(base.resolve()) or not resolved.is_file():
        raise LivelyError("Gallery path escaped its root or is not a file.")
    return resolved


class Gallery:
    def __init__(self, root: Path, data: Path, store):
        self.builtin = root / "assets" / "stickers"
        self.directory = data / "gallery"
        self.store = store

    @contextmanager
    def locked(self):
        # Reuse the cross-process database write lock to serialize manifest mutations/readers.
        with self.store.transaction() as db:
            if self.directory.is_symlink() or (self.directory / "images").is_symlink():
                raise LivelyError("Gallery directories must not be symlinks.")
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            (self.directory / "images").mkdir(exist_ok=True, mode=0o700)
            path = self.directory / "manifest.json"
            if path.is_symlink():
                raise LivelyError("Gallery manifest must not be a symlink.")
            items = read_json(path) if path.exists() else []
            if not isinstance(items, list):
                raise LivelyError("Invalid gallery manifest. Restore a valid JSON list.")
            yield db, path, items

    def _entry(self, item: dict, source: str, base: Path):
        path = checked_file(base, item["file"])
        if path.stat().st_size > MAX_BYTES:
            raise LivelyError("Gallery image exceeds 10 MiB.")
        kind = image_type(path.read_bytes())
        return {
            "id": item["id"],
            "description": item["description"],
            "tags": item["tags"],
            "source": source,
            "type": kind,
            "absolute_path": str(path),
        }

    def entries(self):
        builtin = read_json(self.builtin / "manifest.json")
        with self.locked() as (_, _, items):
            return [self._entry(x, "builtin", self.builtin) for x in builtin] + [
                self._entry(x, "user", self.directory) for x in items
            ]

    def search(self, query: str = "", limit: int = 10):
        if not isinstance(query, str) or len(query) > 500 or type(limit) is not int or not 1 <= limit <= 50:
            raise LivelyError("Use a query up to 500 characters and limit between 1 and 50.")
        terms = re.findall(r"\w+", query.casefold())
        entries = self.entries()
        recent = self.store.snapshot().get("last_sticker_ids", [])
        for item in entries:
            text = " ".join([item["id"], item["description"], *item["tags"]]).casefold()
            item["score"] = sum(term in text for term in terms)
            item["recently_suggested"] = item["id"] in recent
        entries = [x for x in entries if not terms or x["score"]]
        entries.sort(key=lambda x: (-x["score"], x["recently_suggested"], x["id"]))
        result = entries[:limit]
        # Track suggestions, not deliveries; never claim an image was actually sent.
        if query and result:
            self.store.update(last_sticker_ids=([result[0]["id"]] + recent)[:4])
        return result

    def import_image(self, path: str, description: str, tags: list[str]):
        if not isinstance(description, str) or not 1 <= len(description.strip()) <= 500:
            raise LivelyError("Provide a description between 1 and 500 characters.")
        if (
            not isinstance(tags, list)
            or len(tags) > 30
            or any(not isinstance(t, str) or not 1 <= len(t) <= 60 for t in tags)
        ):
            raise LivelyError("Provide at most 30 short text tags.")
        original = Path(path).expanduser()
        if not original.is_absolute():
            raise LivelyError("Import requires an absolute local image path.")
        if any(p.is_symlink() for p in (original, *original.parents)):
            raise LivelyError("Import source must not contain symlinks.")
        fd = os.open(original, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_BYTES:
                raise LivelyError("Import a regular image file no larger than 10 MiB.")
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise LivelyError("Image grew beyond 10 MiB during import.")
        kind = image_type(content)
        expected = {"png": {".png"}, "jpeg": {".jpg", ".jpeg"}, "gif": {".gif"}}[kind]
        if original.suffix.lower() not in expected:
            raise LivelyError("Image extension does not match its header. Rename/export it correctly.")
        digest = hashlib.sha256(content).hexdigest()
        with self.locked() as (_, manifest, items):
            duplicate = next((x for x in items if x.get("sha256") == digest), None)
            if duplicate:
                return self._entry(duplicate, "user", self.directory) | {"duplicate": True}
            item = {
                "id": "user-" + uuid.uuid4().hex,
                "file": f"images/{digest}.{kind}",
                "description": description.strip(),
                "tags": tags,
                "sha256": digest,
            }
            destination = self.directory / item["file"]
            if destination.exists() or destination.is_symlink():
                raise LivelyError(
                    "Unindexed gallery image already exists. Diagnose the gallery before importing."
                )
            atomic_write(destination, content)
            try:
                write_json(manifest, items + [item])
            except BaseException:
                destination.unlink(missing_ok=True)
                raise
            return self._entry(item, "user", self.directory)

    def remove(self, sticker_id: str):
        if not sticker_id.startswith("user-"):
            raise LivelyError("Only user-imported stickers can be removed.")
        with self.locked() as (_, manifest, items):
            match = next((x for x in items if x["id"] == sticker_id), None)
            if match is None:
                return {"removed": False, "id": sticker_id}
            path = checked_file(self.directory, match["file"])
            if path.parent != (self.directory / "images").resolve():
                raise LivelyError("Refusing to delete a file outside gallery/images.")
            write_json(manifest, [x for x in items if x["id"] != sticker_id])
            # A failed unlink leaves an unindexed file, never a manifest pointing outside the gallery.
            path.unlink()
            return {"removed": True, "id": sticker_id}
