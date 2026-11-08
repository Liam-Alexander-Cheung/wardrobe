import io

import pytest
from pathlib import Path

from PIL import Image, ImageCms

from conftest import fake_remover, make_photo
from wardrobe import ingest


def test_original_has_no_exif_or_gps(tmp_path):
    out = ingest.process(make_photo(gps=True), "abc", tmp_path, remover=fake_remover)
    img = Image.open(out["original"])
    assert not img.getexif(), "EXIF (incl. GPS) must be stripped"
    assert "exif" not in img.info


def test_original_is_resized_to_max_edge(tmp_path):
    out = ingest.process(make_photo(size=(4000, 3000)), "abc", tmp_path, remover=fake_remover)
    assert max(Image.open(out["original"]).size) == ingest.MAX_ORIGINAL


def test_cutout_is_transparent_png(tmp_path):
    out = ingest.process(make_photo(), "abc", tmp_path, remover=fake_remover)
    cut = Image.open(out["cutout"])
    assert cut.format == "PNG" and cut.mode == "RGBA"
    assert cut.getpixel((0, 0))[3] == 0                      # corner = background, gone
    assert not cut.getexif()


def test_cutout_is_cropped_to_the_garment(tmp_path):
    out = ingest.process(make_photo(size=(1200, 900)), "abc", tmp_path, remover=fake_remover)
    w, h = Image.open(out["cutout"]).size
    assert w < 1200 * 0.6 and h < 900 * 0.6                  # grey border trimmed away


def test_thumbnail_size(tmp_path):
    out = ingest.process(make_photo(), "abc", tmp_path, remover=fake_remover)
    assert max(Image.open(out["thumb"]).size) <= ingest.THUMB


def test_rejects_non_images(tmp_path):
    with pytest.raises(ingest.NotAnImage):
        ingest.process(b"definitely not a photo", "abc", tmp_path, remover=fake_remover)


def test_png_input_works(tmp_path):
    out = ingest.process(make_photo(fmt="PNG", gps=False), "abc", tmp_path, remover=fake_remover)
    assert out["cutout"].exists()


@pytest.mark.slow
def test_real_rembg_cutout(tmp_path):
    out = ingest.process(make_photo(), "abc", tmp_path)       # default remover = rembg
    assert Image.open(out["cutout"]).mode == "RGBA"


# --- colour: iPhone photos are Display P3; browsers assume sRGB for untagged images ---

P3 = Path("/System/Library/ColorSync/Profiles/Display P3.icc")
needs_p3 = pytest.mark.skipif(not P3.exists(), reason="needs the macOS Display P3 profile")
SHIRT = (180, 60, 60)


def p3_photo() -> bytes:
    img = Image.new("RGB", (800, 600), (128, 128, 128))
    img.paste(SHIRT, (200, 150, 600, 450))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=98, icc_profile=P3.read_bytes())
    return buf.getvalue()


def p3_to_srgb(rgb):
    src = ImageCms.ImageCmsProfile(io.BytesIO(P3.read_bytes()))
    return ImageCms.profileToProfile(Image.new("RGB", (1, 1), rgb), src,
                                     ImageCms.createProfile("sRGB")).getpixel((0, 0))


def close(a, b, tol=4):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


@needs_p3
def test_display_p3_photo_is_converted_to_srgb(tmp_path):
    out = ingest.process(p3_photo(), "abc", tmp_path, remover=fake_remover)
    expected = p3_to_srgb(SHIRT)
    assert not close(expected, SHIRT)                       # the test colour really shifts
    original = Image.open(out["original"])
    assert close(original.getpixel((400, 300)), expected)
    cut = Image.open(out["cutout"])
    assert close(cut.getpixel((cut.width // 2, cut.height // 2))[:3], expected)


@needs_p3
def test_saved_images_are_labelled_srgb(tmp_path):
    out = ingest.process(p3_photo(), "abc", tmp_path, remover=fake_remover)
    for kind in ("original", "cutout"):
        icc = Image.open(out[kind]).info.get("icc_profile")
        assert icc, kind
        assert "sRGB" in ImageCms.getProfileDescription(ImageCms.ImageCmsProfile(io.BytesIO(icc))), kind


def test_untagged_photo_keeps_its_colours(tmp_path):
    out = ingest.process(make_photo(color=SHIRT, gps=False), "abc", tmp_path, remover=fake_remover)
    assert close(Image.open(out["original"]).getpixel((600, 450)), SHIRT)


def test_srgb_reinterpretation_for_old_items(tmp_path):
    """Repair helper: pixels that were P3 but stored without a label get converted."""
    if not P3.exists():
        pytest.skip("needs the macOS Display P3 profile")
    img = Image.new("RGB", (4, 4), SHIRT)
    assert close(ingest.to_srgb(img, P3.read_bytes()).getpixel((0, 0)), p3_to_srgb(SHIRT))
