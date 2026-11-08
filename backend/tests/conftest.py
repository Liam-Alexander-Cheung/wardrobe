"""Shared test fixtures. No real clothes and no network: photos are generated here."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageChops

from wardrobe.app import create_app

BASE = "http://127.0.0.1:8766"


def make_photo(size=(1200, 900), color=(200, 40, 40), gps=True, fmt="JPEG") -> bytes:
    """A fake phone photo: a coloured 'shirt' on a grey floor, with GPS EXIF like an iPhone."""
    img = Image.new("RGB", size, (128, 128, 128))
    w, h = size
    img.paste(color, (w // 4, h // 4, 3 * w // 4, 3 * h // 4))
    exif = Image.Exif()
    exif[0x010F] = "Apple"                       # Make
    exif[0x0110] = "iPhone 15"                   # Model
    if gps:
        exif[0x8825] = {1: "N", 2: (51.0, 13.0, 30.0), 3: "E", 4: (6.0, 46.0, 0.0)}  # Düsseldorf
    buf = io.BytesIO()
    img.save(buf, fmt, exif=exif.tobytes())
    return buf.getvalue()


def fake_remover(img: Image.Image) -> Image.Image:
    """Stands in for rembg: makes grey pixels transparent, keeps the rest."""
    rgb = img.convert("RGB")
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (128, 128, 128))).convert("L")
    rgba = rgb.convert("RGBA")
    rgba.putalpha(diff.point(lambda v: 255 if v else 0))
    return rgba


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "WardrobeData"


@pytest.fixture
def client(data_dir):
    app = create_app(data_dir=data_dir, remover=fake_remover)
    with TestClient(app, base_url=BASE, headers={"origin": BASE}) as c:
        yield c


@pytest.fixture
def upload(client):
    """Upload one generated photo and return the created item."""
    def _upload(**photo_kwargs):
        files = {"file": ("IMG_0001.jpg", make_photo(**photo_kwargs), "image/jpeg")}
        r = client.post("/api/items", files=files)
        assert r.status_code == 201, r.text
        return r.json()
    return _upload
