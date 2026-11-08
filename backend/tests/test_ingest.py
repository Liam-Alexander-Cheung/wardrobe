import io

import pytest
from PIL import Image

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
