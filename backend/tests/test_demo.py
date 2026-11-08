from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from conftest import BASE
from wardrobe import config, demo
from wardrobe.app import create_app
from wardrobe.db import Store


def test_seed_creates_tagged_items_with_images(tmp_path):
    demo.seed(tmp_path)
    store = Store(tmp_path / "wardrobe.db")
    items = store.list_items()
    assert len(items) == len(demo.WARDROBE) >= 10
    assert all(i["category"] and i["colors"] and i["name"] for i in items)
    for i in items:
        cut = Image.open(tmp_path / "cutouts" / f"{i['id']}.png")
        assert cut.mode == "RGBA" and cut.getpixel((0, 0))[3] == 0      # transparent corner
        assert (tmp_path / "thumbs" / f"{i['id']}.webp").is_file()
        assert (tmp_path / "originals" / f"{i['id']}.jpg").is_file()


def test_seed_adds_outfits_from_both_authors(tmp_path):
    demo.seed(tmp_path)
    outfits = Store(tmp_path / "wardrobe.db").list_outfits()
    assert {o["created_by"] for o in outfits} == {"liam", "claude"}
    assert all(len(o["items"]) >= 3 for o in outfits)


def test_seed_is_idempotent(tmp_path):
    demo.seed(tmp_path)
    demo.seed(tmp_path)
    assert Store(tmp_path / "wardrobe.db").count_items() == len(demo.WARDROBE)


def test_demo_dir_is_temporary_and_outside_repo():
    path = demo.temp_dir()
    assert config.REPO_ROOT not in path.parents
    assert path != config.data_dir()


def test_app_reports_demo_mode(tmp_path):
    demo.seed(tmp_path)
    app = create_app(data_dir=tmp_path, demo=True)
    with TestClient(app, base_url=BASE) as c:
        assert c.get("/api/health").json() == {"ok": True, "items": len(demo.WARDROBE), "demo": True}
