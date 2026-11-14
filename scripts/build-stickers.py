"""Reproducible original 'Lumi' mascot illustrations. Build-time Pillow only; no downloaded art."""

from pathlib import Path
import json
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "stickers"
PALETTE = {"background": "#fff3db", "body": "#80b9ac", "ink": "#344e54", "cheek": "#ebad9b"}


def make(name):
    # Draw at 3x and downsample, yielding RGB with a fully opaque background.
    scale = 3
    image = Image.new("RGB", (192 * scale, 192 * scale), PALETTE["background"])
    d = ImageDraw.Draw(image)

    def oval(box, fill, outline=None, width=1):
        d.ellipse(tuple(int(x * scale) for x in box), fill=fill, outline=outline, width=width * scale)

    def line(points, fill=PALETTE["ink"], width=3):
        d.line([(int(x * scale), int(y * scale)) for x, y in points], fill=fill, width=width * scale)

    oval((44, 147, 150, 166), "#e6ddc5")
    oval((49, 55, 144, 155), PALETTE["body"], PALETTE["ink"], 3)
    oval((62, 31, 88, 78), PALETTE["body"], PALETTE["ink"], 3)
    oval((106, 31, 132, 78), PALETTE["body"], PALETTE["ink"], 3)
    oval((58, 62, 137, 139), PALETTE["body"])
    oval((65, 104, 80, 114), PALETTE["cheek"])
    oval((116, 104, 131, 114), PALETTE["cheek"])
    if name == "happy":
        line([(75, 96), (81, 90), (87, 96)])
        line([(106, 96), (112, 90), (118, 96)])
        line([(86, 111), (96, 120), (107, 111)])
        for x, y in ((29, 43), (156, 47), (158, 121)):
            line([(x - 6, y), (x + 6, y)], "#d29d52", 2)
            line([(x, y - 6), (x, y + 6)], "#d29d52", 2)
    else:
        oval((77, 91, 83, 99), PALETTE["ink"])
        oval((109, 91, 115, 99), PALETTE["ink"])
        if name == "confused":
            line([(74, 84), (86, 81)])
            oval((91, 110, 101, 120), PALETTE["ink"])
            # Hand-drawn question mark.
            line(
                [(151, 55), (150, 49), (155, 44), (163, 44), (168, 49), (167, 56), (158, 62), (158, 68)],
                width=3,
            )
            oval((156, 73, 160, 77), PALETTE["ink"])
        else:
            line([(88, 111), (96, 115), (104, 111)], width=2)
    if name == "greeting":
        line([(136, 123), (152, 107), (157, 88)], PALETTE["ink"], 8)
        line([(136, 122), (151, 106), (156, 89)], PALETTE["body"], 5)
        line([(167, 83), (174, 76)], "#d29d52", 2)
        line([(170, 96), (180, 95)], "#d29d52", 2)
    if name == "comfort":
        oval((77, 129, 96, 147), "#df8e88")
        oval((94, 129, 113, 147), "#df8e88")
        d.polygon([(x * scale, y * scale) for x, y in [(78, 139), (112, 139), (95, 158)]], fill="#df8e88")
        line([(59, 124), (77, 140)], PALETTE["ink"], 6)
        line([(134, 124), (114, 140)], PALETTE["ink"], 6)
    image.resize((192, 192), Image.Resampling.LANCZOS).save(ASSETS / f"{name}.png", optimize=True)


if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    descriptions = {
        "greeting": ("Lumi waves hello", ["hello", "greeting", "你好", "打招呼"]),
        "happy": ("Lumi celebrates with sparkles", ["happy", "celebrate", "开心", "庆祝"]),
        "confused": ("Lumi wonders about a question", ["confused", "curious", "疑惑", "好奇"]),
        "comfort": ("Lumi offers a little heart", ["comfort", "care", "安慰", "关心"]),
    }
    items = []
    for name, (description, tags) in descriptions.items():
        make(name)
        items.append(
            {
                "id": f"sample-{name}",
                "file": f"{name}.png",
                "description": description,
                "tags": tags,
                "source": "builtin",
                "license": "CC0-1.0; see assets/LICENSE.md",
            }
        )
    (ASSETS / "manifest.json").write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n")
