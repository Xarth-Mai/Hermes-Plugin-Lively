import json
from pathlib import Path
from types import SimpleNamespace

from lively_under_test.plugin_tools import Tools

ROOT = Path(__file__).resolve().parents[1]


def tools(tmp_path, name, shared):
    data = tmp_path / name
    data.mkdir()
    ctx = SimpleNamespace(state=SimpleNamespace(data_dir=data), get_config=lambda key, default=None: shared if key == 'shared_gallery' else default)
    return Tools(ctx, ROOT, tmp_path), data


def test_explicit_shared_root_link_works_across_profiles(tmp_path):
    shared = tmp_path / 'shared'
    shared.mkdir()
    a, ad = tools(tmp_path, 'a', str(shared))
    b, bd = tools(tmp_path, 'b', str(shared))
    for data in (ad, bd):
        (data / 'gallery').symlink_to(shared, target_is_directory=True)
    result = json.loads(a.stickers({'action': 'import', 'path': str(ROOT / 'assets/stickers/happy/happy.png'), 'description': 'shared happy'}))
    assert result['ok'], result
    found = json.loads(b.stickers({'action': 'search', 'query': 'shared happy'}))
    assert any(x['id'] == result['item']['id'] for x in found['items'])
    assert not (ad / 'state.sqlite').exists() and not (bd / 'state.sqlite').exists()
    assert (shared / '.lively-state/state.sqlite').exists()


def test_unconfigured_root_link_is_still_rejected(tmp_path):
    shared = tmp_path / 'shared'
    shared.mkdir()
    obj, data = tools(tmp_path, 'a', None)
    (data / 'gallery').symlink_to(shared, target_is_directory=True)
    assert not json.loads(obj.stickers({'action': 'status'}))['ok']


def test_shared_root_mismatch_fails_closed(tmp_path):
    shared, wrong = tmp_path / 'shared', tmp_path / 'wrong'
    shared.mkdir()
    wrong.mkdir()
    obj, data = tools(tmp_path, 'a', str(shared))
    (data / 'gallery').symlink_to(wrong, target_is_directory=True)
    assert not json.loads(obj.stickers({'action': 'status'}))['ok']


def test_shared_gallery_still_rejects_image_links(tmp_path):
    shared = tmp_path / 'shared'
    group = shared / 'personal'
    group.mkdir(parents=True)
    (group / 'image.png').symlink_to(ROOT / 'assets/stickers/happy/happy.png')
    (group / 'metadata.json').write_text(json.dumps({'name': 'shared', 'description': 'shared', 'items': {'image.png': 'happy'}}))
    obj, data = tools(tmp_path, 'a', str(shared))
    (data / 'gallery').symlink_to(shared, target_is_directory=True)
    assert not json.loads(obj.stickers({'action': 'status'}))['ok']
