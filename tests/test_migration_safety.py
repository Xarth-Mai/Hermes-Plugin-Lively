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


def test_remove_through_gallery_root_symlink_rejected(gallery, tmp_path):
    import shutil

    item = gallery.import_image(str(ROOT / "assets/stickers/greeting/greeting.png"), "keep")
    outside = tmp_path / "outside"
    shutil.move(str(gallery.personal), outside)
    gallery.personal.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        gallery.remove(item["id"])
    assert len(list(outside.rglob("*.png"))) == 1


def test_interrupted_migration_retries_without_losing_originals(gallery, monkeypatch):
    from importlib import import_module

    stickers = import_module("lively_under_test.stickers")

    images = gallery.personal / "images"
    images.mkdir(parents=True)
    source = images / "original.png"
    source.write_bytes((ROOT / "assets/stickers/greeting/greeting.png").read_bytes())
    manifest = gallery.personal / "manifest.json"
    manifest.write_text(json.dumps([{"file": "images/original.png", "description": "retained"}]))
    original_json = manifest.read_bytes()
    writer = stickers.atomic_json

    def interrupted(*args, **kwargs):
        raise OSError("simulated interrupted metadata write")

    monkeypatch.setattr(stickers, "atomic_json", interrupted)
    with pytest.raises(OSError):
        gallery.entries()
    assert source.exists() and manifest.read_bytes() == original_json
    assert not (gallery.personal / ".legacy-migrated").exists()
    monkeypatch.setattr(stickers, "atomic_json", writer)
    assert len(gallery.search("retained")) == 1
    assert source.exists() and manifest.read_bytes() == original_json


def test_legacy_oversized_source_rejected(gallery):
    images = gallery.personal / "images"
    images.mkdir(parents=True)
    source = images / "large.png"
    source.write_bytes((ROOT / "assets/stickers/greeting/greeting.png").read_bytes())
    with source.open("r+b") as stream:
        stream.truncate(10 * 1024 * 1024 + 1)
        stream.seek(-8, 2)
        stream.write(b"IEND\xaeB`\x82")
    (gallery.personal / "manifest.json").write_text(json.dumps([{"file": "images/large.png"}]))
    with pytest.raises(ValueError, match="size"):
        gallery.entries()
    assert source.exists()
    assert not (gallery.personal / ".legacy-migrated").exists()
