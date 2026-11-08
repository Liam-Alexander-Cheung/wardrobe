import io
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from wardrobe import ingest, repair_colours

P3 = Path("/System/Library/ColorSync/Profiles/Display P3.icc")
pytestmark = pytest.mark.skipif(not P3.exists(), reason="needs the macOS Display P3 profile")
SHIRT = (180, 60, 60)


def old_style_item(root: Path, item_id="aaaaaaaaaaaa"):
    """Files as the first version stored them: P3 pixel values, no colour label."""
    for kind, ext, fmt in (("originals", "jpg", "JPEG"), ("cutouts", "png", "PNG"), ("thumbs", "webp", "WEBP")):
        (root / kind).mkdir(parents=True, exist_ok=True)
        mode = "RGB" if fmt == "JPEG" else "RGBA"
        Image.new(mode, (40, 40), SHIRT + ((255,) if mode == "RGBA" else ())).save(
            root / kind / f"{item_id}.{ext}", fmt, **({"lossless": True} if fmt == "WEBP" else {"quality": 100} if fmt == "JPEG" else {}))
    return item_id


def expected():
    src = ImageCms.ImageCmsProfile(io.BytesIO(P3.read_bytes()))
    return ImageCms.profileToProfile(Image.new("RGB", (1, 1), SHIRT), src, ingest.SRGB).getpixel((0, 0))


def close(a, b, tol=3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_repair_converts_and_labels(tmp_path):
    item = old_style_item(tmp_path)
    assert repair_colours.repair(tmp_path, P3.read_bytes()) == 3
    for kind, ext in (("originals", "jpg"), ("cutouts", "png"), ("thumbs", "webp")):
        img = Image.open(tmp_path / kind / f"{item}.{ext}")
        assert img.info.get("icc_profile"), kind
        assert close(img.getpixel((20, 20))[:3], expected()), kind
    assert Image.open(tmp_path / "cutouts" / f"{item}.png").mode == "RGBA"   # transparency kept


def test_repair_is_idempotent(tmp_path):
    item = old_style_item(tmp_path)
    repair_colours.repair(tmp_path, P3.read_bytes())
    assert repair_colours.repair(tmp_path, P3.read_bytes()) == 0
    px = Image.open(tmp_path / "originals" / f"{item}.jpg").getpixel((20, 20))
    assert close(px, expected())                                           # not converted twice


def test_dry_run_changes_nothing(tmp_path):
    item = old_style_item(tmp_path)
    before = (tmp_path / "originals" / f"{item}.jpg").read_bytes()
    assert repair_colours.repair(tmp_path, P3.read_bytes(), dry_run=True) == 3
    assert (tmp_path / "originals" / f"{item}.jpg").read_bytes() == before
