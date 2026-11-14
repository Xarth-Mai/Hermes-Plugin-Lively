"""Regression checks for non-destructive legacy-gallery migration."""
import json

import pytest

from conftest import ROOT


def test_legacy_source_symlink_rejected(gallery, tmp_path):
    images = gallery.personal / "images"
    images.mkdir(parents=True)
    real = images / "real.png"
    real.write_bytes((ROOT / "assets/stickers/greeting/greeting.png").read_bytes())
    (images / "link.png").symlink_to(real)
    (gallery.personal / "manifest.json").write_text(json.dumps([
        {"file": "images/link.png", "description": "linked"}
    ]))
    with pytest.raises(ValueError, match="symlink"):
        gallery.entries()
    assert real.exists()
    assert not (gallery.personal / ".legacy-migrated").exists()


def test_legacy_root_symlink_does_not_write(gallery, tmp_path):
    outside = tmp_path / "outside"
    (outside / "images").mkdir(parents=True)
    (outside / "images/original.png").write_bytes(
        (ROOT / "assets/stickers/greeting/greeting.png").read_bytes()
    )
    (outside / "manifest.json").write_text(json.dumps([{"file": "images/original.png"}]))
    gallery.personal.parent.mkdir(parents=True, exist_ok=True)
    gallery.personal.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        gallery.entries()
    assert not (outside / "legacy").exists()
    assert not (outside / ".legacy-migrated").exists()
