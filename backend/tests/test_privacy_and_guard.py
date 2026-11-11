import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import BASE, fake_remover
from wardrobe import config
from wardrobe.app import create_app

REPO = Path(__file__).resolve().parents[2]


# --- privacy: the data folder can never sit inside the public repo -----------------

def test_default_data_dir_is_outside_repo(monkeypatch):
    monkeypatch.delenv("WARDROBE_DATA", raising=False)
    path = config.data_dir()
    assert path == Path.home() / "WardrobeData"
    assert REPO not in path.parents


def test_data_dir_inside_repo_is_refused(monkeypatch):
    monkeypatch.setenv("WARDROBE_DATA", str(REPO / "data"))
    with pytest.raises(config.UnsafeDataDir):
        config.data_dir()


def test_app_refuses_data_dir_inside_repo():
    with pytest.raises(config.UnsafeDataDir):
        create_app(data_dir=REPO / "backend" / "WardrobeData", remover=fake_remover)


@pytest.mark.parametrize("path", ["WardrobeData/wardrobe.db", "x/wardrobe.db", "photo.jpg",
                                  "IMG_1234.HEIC", "cutouts/a.png", "thumbs/a.webp", "uploads/a"])
def test_gitignore_blocks_private_files(path):
    r = subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO)
    assert r.returncode == 0, f"{path} would be committed"


# --- guard: only this app's own page may use the API --------------------------------

@pytest.fixture
def raw(data_dir):
    return TestClient(create_app(data_dir=data_dir, remover=fake_remover), base_url=BASE)


def test_foreign_host_is_403(raw):
    assert raw.get("/api/health", headers={"host": "evil.example"}).status_code == 403


def test_post_from_foreign_origin_is_403(raw):
    r = raw.patch("/api/items/x", json={}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_post_without_origin_is_403(raw):
    assert raw.delete("/api/items/x").status_code == 403


def test_local_get_and_own_origin_pass(raw):
    assert raw.get("/api/health").status_code == 200
    assert raw.delete("/api/items/x", headers={"origin": BASE}).status_code == 404


def test_vite_dev_origin_is_allowed(raw):
    r = raw.delete("/api/items/x", headers={"origin": "http://localhost:5173"})
    assert r.status_code == 404


def test_security_headers(raw):
    h = raw.get("/api/health").headers
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["x-frame-options"] == "DENY"


# --- caching: after an update or a photo repair the browser must not show stale files ---

def test_responses_revalidate_by_default(raw):
    assert raw.get("/api/health").headers["cache-control"] == "no-cache"


def test_media_revalidates(client, upload):
    thumb = upload()["images"]["thumb"]
    r = client.get(thumb)
    assert "no-cache" in r.headers["cache-control"]
    etag = r.headers["etag"]
    assert client.get(thumb, headers={"if-none-match": etag}).status_code == 304   # cheap recheck
