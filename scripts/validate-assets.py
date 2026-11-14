"""Verify the release assets and folder-local metadata without external packages."""
import json
from pathlib import Path
import struct
import zlib


def validate(directory: Path) -> int:
    total = 0
    for label in ("greeting", "happy", "confused", "comfort"):
        folder = directory / label
        meta = json.loads((folder / "metadata.json").read_text())
        assert set(meta["items"]) == {label + ".png"}
        assert isinstance(meta["name"], str) and isinstance(meta["description"], str)
        content = (folder / (label + ".png")).read_bytes()
        assert content[:8] == b"\x89PNG\r\n\x1a\n"
        offset, chunks = 8, []
        while offset < len(content):
            size = struct.unpack(">I", content[offset : offset + 4])[0]
            kind = content[offset + 4 : offset + 8]
            body = content[offset + 8 : offset + 8 + size]
            crc = struct.unpack(">I", content[offset + 8 + size : offset + 12 + size])[0]
            assert zlib.crc32(kind + body) == crc
            chunks.append(kind)
            if kind == b"IHDR":
                assert struct.unpack(">IIBBBBB", body) == (192, 192, 8, 2, 0, 0, 0)
            offset += 12 + size
        assert chunks[0] == b"IHDR" and chunks[-1] == b"IEND" and b"tRNS" not in chunks
        assert len(content) <= 40 * 1024
        total += len(content)
    return total


if __name__ == "__main__":
    print(f"Validated four folder-local PNG assets ({validate(Path(__file__).resolve().parents[1] / 'assets/stickers')} bytes)")
