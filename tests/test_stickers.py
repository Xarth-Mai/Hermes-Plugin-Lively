from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from conftest import ROOT


def sample_image():
    return ROOT / "assets/stickers/greeting/greeting.png"


def test_folder_metadata_and_search(gallery):
    entries = gallery.entries()
    assert len(entries) == 4
    assert gallery.search("庆祝")[0]["folder"] == "happy"
    assert gallery.status()["builtin_count"] == 4
    assert gallery.status()["user_count"] == 0


def test_import_remove_and_deduplicate(gallery):
    first = gallery.import_image(str(sample_image()), "笑着挥手", "my-pack")
    second = gallery.import_image(str(sample_image()), "different", "my-pack")
    assert first["id"] == second["id"] and second["duplicate"]
    assert gallery.search("挥手")[0]["source"] == "user"
    assert gallery.remove(first["id"])["removed"]
    assert not gallery.remove(first["id"])["removed"]
    with pytest.raises(Exception):
        gallery.remove("builtin:greeting/greeting.png")


def test_input_safety_and_manifest_escape(gallery, tmp_path):
    fake = tmp_path / "fake.png"
    fake.write_text("not image")
    with pytest.raises(Exception):
        gallery.import_image(str(fake), "test")
    link = tmp_path / "link.png"
    link.symlink_to(sample_image())
    with pytest.raises(Exception):
        gallery.import_image(str(link), "test")
    with pytest.raises(Exception):
        gallery.import_image(str(sample_image()), "test", "../escape")
    item = gallery.import_image(str(sample_image()), "test", "custom")
    meta = gallery.personal / "custom" / "metadata.json"
    info = json.loads(meta.read_text())
    info["items"]["../../bad.png"] = "malicious"
    meta.write_text(json.dumps(info))
    with pytest.raises(Exception):
        gallery.entries()
    with pytest.raises(Exception):
        gallery.remove(item["id"])


def test_legacy_gallery_migration_preserves_old_files(gallery):
    old = gallery.personal / "images"
    old.mkdir(parents=True)
    legacy = old / "original.png"
    legacy.write_bytes(sample_image().read_bytes())
    manifest = gallery.personal / "manifest.json"
    manifest.write_text(json.dumps([{"id": "old", "file": "images/original.png", "description": "旧图库"}]))
    results = gallery.search("旧图库")
    assert len(results) == 1 and results[0]["folder"] == "legacy"
    assert legacy.exists() and manifest.exists()
    assert len(gallery.search("旧图库")) == 1


def test_concurrent_import(gallery):
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: gallery.import_image(str(sample_image()), "hello")["id"], range(8)))
    assert len(set(ids)) == 1
