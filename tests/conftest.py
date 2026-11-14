import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lively_under_test", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


@pytest.fixture
def gate():
    from lively_under_test import gate
    return gate


@pytest.fixture
def gallery(tmp_path):
    from lively_under_test.stickers import Gallery
    return Gallery(ROOT / "assets/stickers", tmp_path / "gallery", tmp_path)
