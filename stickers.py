"""Folder-organized sticker gallery. Each folder owns one metadata.json."""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .gate import LivelyError, atomic_bytes, atomic_json, transaction

MAX_BYTES = 10 * 1024 * 1024
FOLDER = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")


def image_kind(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 33 and data[12:16] == b"IHDR" and data[-8:-4] == b"IEND":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 14 and data[-1:] == b";":
        return "gif"
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "jpg"
    raise LivelyError("Unsupported or invalid image; use PNG, JPEG or GIF")


def image_path(folder: Path, filename: str) -> Path:
    if not isinstance(filename, str) or Path(filename).name != filename or filename in (".", ".."):
        raise LivelyError("Invalid sticker filename")
    if folder.is_symlink():
        raise LivelyError("Gallery folder is a symlink")
    path = folder / filename
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(folder.resolve()):
        raise LivelyError("Invalid gallery image path")
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise LivelyError("Invalid gallery image size")
    with path.open("rb") as stream:
        header = stream.read(64)
        stream.seek(-8, os.SEEK_END)
        footer = stream.read(8)
    kind = image_kind(header + footer)
    if path.suffix.lower() not in ({"png": {".png"}, "jpg": {".jpg", ".jpeg"}, "gif": {".gif"}}[kind]):
        raise LivelyError("Image extension does not match its data")
    return path.resolve()


def read_group(folder: Path):
    meta = folder / "metadata.json"
    if meta.is_symlink():
        raise LivelyError("Gallery metadata symlinks are not allowed")
    obj = json.loads(meta.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or not isinstance(obj.get("name"), str) or not isinstance(obj.get("description"), str) or not isinstance(obj.get("items"), dict):
        raise LivelyError("Invalid folder metadata")
    if any(not isinstance(k, str) or Path(k).name != k or k in (".", "..") or not isinstance(v, str) or len(v) > 1000 for k, v in obj["items"].items()):
        raise LivelyError("Invalid sticker description")
    return obj


class Gallery:
    def __init__(self, builtin: Path, personal: Path, data: Path):
        self.builtin, self.personal, self.data = map(Path, (builtin, personal, data))

    def _migrate_legacy(self):
        """Copy old gallery/manifest.json content non-destructively into a legacy group."""
        if any(part.is_symlink() for part in (self.personal, *self.personal.parents)):
            raise LivelyError("Refusing legacy gallery root symlink")
        manifest = self.personal / "manifest.json"
        marker = self.personal / ".legacy-migrated"
        if marker.is_file() or not manifest.exists():
            return
        if manifest.is_symlink():
            raise LivelyError("Refusing legacy manifest symlink")
        if (self.personal / "images").is_symlink():
            raise LivelyError("Refusing legacy images symlink")
        with transaction(self.data, create=True):
            items = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(items, list):
                raise LivelyError("Invalid legacy gallery manifest")
            dest = self.personal / "legacy"
            if dest.is_symlink():
                raise LivelyError("Refusing legacy folder symlink")
            dest.mkdir(parents=True, exist_ok=True)
            info_path = dest / "metadata.json"
            info = read_group(dest) if info_path.exists() else {
                "name": "Earlier imports", "description": "Images imported before folder galleries", "items": {}
            }
            changed = False
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("file"), str):
                    raise LivelyError("Invalid legacy gallery entry")
                source = self.personal / item["file"]
                if any(part.is_symlink() for part in (source, *source.parents)):
                    raise LivelyError("Refusing legacy image symlink")
                source = source.resolve()
                if not source.is_relative_to((self.personal / "images").resolve()) or not source.is_file():
                    raise LivelyError("Invalid legacy gallery path")
                if not 0 < source.stat().st_size <= MAX_BYTES:
                    raise LivelyError("Invalid legacy gallery image size")
                content = source.read_bytes()
                kind = image_kind(content)
                name = hashlib.sha256(content).hexdigest()[:32] + "." + kind
                if name in info["items"]:
                    continue
                target = dest / name
                if target.exists() and target.read_bytes() != content:
                    raise LivelyError("Legacy image collision")
                if not target.exists():
                    atomic_bytes(target, content)
                info["items"][name] = str(item.get("description", "Imported sticker"))[:1000]
                changed = True
            if changed or not info_path.exists():
                atomic_json(info_path, info)
            atomic_bytes(marker, b"legacy-imported\n")
            # Original manifest/assets remain for rollback; later access skips migration.

    def entries(self):
        self._migrate_legacy()
        results = []
        for source, root in (("builtin", self.builtin), ("user", self.personal)):
            if not root.exists():
                continue
            if root.is_symlink():
                raise LivelyError("Invalid gallery root symlink")
            for folder in sorted(root.iterdir()):
                if not folder.is_dir() or folder.is_symlink() or not (folder / "metadata.json").is_file():
                    continue
                meta = read_group(folder)
                for filename, description in meta["items"].items():
                    path = image_path(folder, filename)
                    results.append({
                        "id": f"{source}:{folder.name}/{filename}", "folder": folder.name,
                        "name": meta["name"], "group_description": meta["description"],
                        "description": description, "source": source, "absolute_path": str(path),
                    })
        return results

    def search(self, query: str = "", limit: int = 20):
        if not isinstance(query, str) or len(query) > 500 or type(limit) is not int or not 1 <= limit <= 50:
            raise LivelyError("Use a query <=500 chars and limit 1..50")
        terms = re.findall(r"\w+", query.casefold())
        items = self.entries()
        if terms:
            for item in items:
                content = " ".join((item["name"], item["group_description"], item["description"], item["folder"])).casefold()
                item["score"] = sum(x in content for x in terms)
            items = [x for x in items if x["score"]]
            items.sort(key=lambda x: (-x["score"], x["source"] != "user", x["id"]))
        return items[:limit]

    def status(self):
        items = self.entries()
        return {"builtin_count": sum(x["source"] == "builtin" for x in items),
                "user_count": sum(x["source"] == "user" for x in items),
                "folders": sorted({x["folder"] for x in items})}

    def import_image(self, src: str, description: str, folder_name: str = "personal"):
        if not isinstance(folder_name, str) or not FOLDER.fullmatch(folder_name):
            raise LivelyError("Use a simple lowercase folder name")
        if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1000:
            raise LivelyError("Provide a short sticker description")
        path = Path(src).expanduser()
        if not path.is_absolute() or any(part.is_symlink() for part in (path, *path.parents)):
            raise LivelyError("Use a regular local image file without symlinks")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            st = os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode) or not 0 < st.st_size <= MAX_BYTES:
                raise LivelyError("File must be a regular image under 10 MiB")
            payload = stream.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise LivelyError("File is too large")
        kind = image_kind(payload)
        if path.suffix.lower() not in {"png": {".png"}, "jpg": {".jpg", ".jpeg"}, "gif": {".gif"}}[kind]:
            raise LivelyError("Image extension mismatch")
        name = hashlib.sha256(payload).hexdigest()[:32] + "." + kind
        with transaction(self.data, create=True):
            folder = self.personal / folder_name
            if folder.is_symlink() or self.personal.is_symlink():
                raise LivelyError("Invalid gallery symlink")
            folder.mkdir(parents=True, exist_ok=True)
            info_path = folder / "metadata.json"
            info = read_group(folder) if info_path.exists() else {
                "name": folder_name.replace("-", " ").title(), "description": "Personal stickers", "items": {}
            }
            if name in info["items"]:
                return {"id": f"user:{folder_name}/{name}", "duplicate": True,
                        "absolute_path": str(image_path(folder, name))}
            dest = folder / name
            if dest.exists() or dest.is_symlink():
                raise LivelyError("Unindexed gallery image already exists")
            atomic_bytes(dest, payload)
            try:
                info["items"][name] = description.strip()
                atomic_json(info_path, info)
            except BaseException:
                dest.unlink(missing_ok=True)
                raise
        return {"id": f"user:{folder_name}/{name}", "absolute_path": str(dest.resolve())}

    def remove(self, identifier: str):
        if not isinstance(identifier, str) or not identifier.startswith("user:"):
            raise LivelyError("Only personal stickers can be removed")
        try:
            folder_name, filename = identifier[5:].split("/", 1)
        except ValueError as exc:
            raise LivelyError("Invalid sticker ID") from exc
        if not FOLDER.fullmatch(folder_name):
            raise LivelyError("Invalid folder")
        with transaction(self.data, create=True):
            folder = self.personal / folder_name
            if folder.is_symlink():
                raise LivelyError("Refusing gallery folder symlink")
            if not (folder / "metadata.json").is_file():
                return {"removed": False}
            info = read_group(folder)
            if filename not in info["items"]:
                return {"removed": False}
            path = image_path(folder, filename)
            del info["items"][filename]
            atomic_json(folder / "metadata.json", info)
            path.unlink()
            return {"removed": True, "id": identifier}
