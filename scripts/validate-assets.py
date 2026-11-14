"""Validate shipped PNGs with stdlib only; runs in CI and does not edit assets."""

import json
from pathlib import Path
import struct
import zlib


def validate(directory: Path):
    items = json.loads((directory / "manifest.json").read_text())
    assert {x["file"] for x in items} == {"greeting.png", "happy.png", "confused.png", "comfort.png"}
    assert len({x["id"] for x in items}) == len(items) == 4
    total = 0
    for item in items:
        content = (directory / item["file"]).read_bytes()
        assert content[:8] == b"\x89PNG\r\n\x1a\n"
        offset, chunks = 8, []
        while offset < len(content):
            size = struct.unpack(">I", content[offset : offset + 4])[0]
            kind = content[offset + 4 : offset + 8]
            body = content[offset + 8 : offset + 8 + size]
            crc = struct.unpack(">I", content[offset + 8 + size : offset + 12 + size])[0]
            assert zlib.crc32(kind + body) == crc, item["file"]
            chunks.append(kind)
            if kind == b"IHDR":
                assert struct.unpack(">IIBBBBB", body) == (192, 192, 8, 2, 0, 0, 0), item["file"]
            offset += 12 + size
        assert chunks[0] == b"IHDR" and chunks[-1] == b"IEND" and b"tRNS" not in chunks
        assert len(content) <= 40 * 1024
        total += len(content)
    assert total <= 160 * 1024
    return total


if __name__ == "__main__":
    total = validate(Path(__file__).resolve().parents[1] / "assets" / "stickers")
    print(f"4 RGB opaque 192x192 PNGs validated ({total} bytes total)")
