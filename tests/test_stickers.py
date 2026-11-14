from pathlib import Path
import json

import pytest

from lively_under_test.common import LivelyError
from lively_under_test.stickers import Gallery, MAX_BYTES
from lively_under_test.plugin_tools import Tools
from conftest import ROOT


@pytest.fixture
def gallery(contact):
    return Gallery(ROOT, contact.data, contact.store)


def test_builtins_search_recent_and_import_dedup(gallery, tmp_path):
    assert len(gallery.search()) == 4
    assert gallery.search("开心")[0]["id"] == "sample-happy"
    assert gallery.search("happy")[0]["recently_suggested"]
    first = gallery.import_image(str(ROOT / "assets/stickers/happy.png"), "personal image", ["happy"])
    second = gallery.import_image(str(ROOT / "assets/stickers/happy.png"), "another description", [])
    assert first["id"] == second["id"] and second["duplicate"]
    assert Path(first["absolute_path"]).is_relative_to(gallery.directory)
    assert len(gallery.entries()) == 5
    assert gallery.remove(first["id"])["removed"]
    assert not gallery.remove(first["id"])["removed"]
    assert len(gallery.entries()) == 4
    with pytest.raises(LivelyError):
        gallery.remove("sample-happy")


def test_forged_oversize_and_symlink(gallery, tmp_path):
    invalid = tmp_path / "fake.png"
    invalid.write_text("not an image")
    with pytest.raises(LivelyError):
        gallery.import_image(str(invalid), "test", [])
    invalid.write_bytes(b"x" * (MAX_BYTES + 1))
    with pytest.raises(LivelyError):
        gallery.import_image(str(invalid), "test", [])
    link = tmp_path / "linked.png"
    link.symlink_to(ROOT / "assets/stickers/happy.png")
    with pytest.raises(LivelyError):
        gallery.import_image(str(link), "test", [])


def test_manifest_escape_and_remove_protection(gallery, tmp_path):
    item = gallery.import_image(str(ROOT / "assets/stickers/happy.png"), "test", [])
    manifest = gallery.directory / "manifest.json"
    data = json.loads(manifest.read_text())
    data[0]["file"] = "../../config.yaml"
    manifest.write_text(json.dumps(data))
    with pytest.raises(LivelyError):
        gallery.entries()
    with pytest.raises(LivelyError):
        gallery.remove(item["id"])


def test_off_allows_explicit_view_and_management(contact, gallery):
    tools = Tools(contact, gallery)
    contact.configure({"stickers_enabled": False})
    assert not json.loads(tools.sticker_handler({"action": "search", "query": "happy"}))["ok"]
    assert json.loads(tools.sticker_handler({"action": "list", "explicit": True}))["ok"]
    assert json.loads(tools.sticker_handler({"action": "status"}))["builtin_count"] == 4


def test_concurrent_imports_are_deduplicated(gallery):
    from concurrent.futures import ThreadPoolExecutor

    def do_import(_):
        return gallery.import_image(str(ROOT / "assets/stickers/happy.png"), "happy", ["happy"])["id"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(do_import, range(8)))
    assert len(set(ids)) == 1
    assert len(gallery.entries()) == 5
