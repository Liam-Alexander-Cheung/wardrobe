"""
Turn one phone photo into the three files the app uses:

    originals/<id>.jpg   the photo, upright, max 2000 px, ALL metadata removed (incl. GPS)
    cutouts/<id>.png     just the garment on a transparent background, cropped tight
    thumbs/<id>.webp     a small cutout for grids and for Claude (fewer tokens)

Background removal runs locally with rembg (no upload anywhere). The `remover` argument
lets tests swap in a fake so they don't need the 170 MB model.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageOps, UnidentifiedImageError

try:  # iPhone photos arrive as HEIC via AirDrop unless "Most Compatible" is set
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    pass

MAX_ORIGINAL = 2000
MAX_CUTOUT = 1000
THUMB = 400
MAX_BYTES = 30 * 1024 * 1024
KINDS = ("originals", "cutouts", "thumbs")

Remover = Callable[[Image.Image], Image.Image]
_session = None


class NotAnImage(ValueError):
    pass


def rembg_remover(img: Image.Image) -> Image.Image:
    """Default remover: rembg with the general-purpose ISNet model, loaded once."""
    global _session
    from rembg import new_session, remove
    if _session is None:
        _session = new_session("isnet-general-use")
    return remove(img, session=_session, post_process_mask=True)


def _clean(img: Image.Image) -> Image.Image:
    """Copy only the pixels into a fresh image, so no EXIF/GPS/XMP can survive."""
    return Image.frombytes(img.mode, img.size, img.tobytes())


def process(data: bytes, item_id: str, root: Path, remover: Optional[Remover] = None) -> dict:
    if len(data) > MAX_BYTES:
        raise NotAnImage("photo is larger than 30 MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise NotAnImage("not a readable image") from e

    img = ImageOps.exif_transpose(img).convert("RGB")   # apply phone rotation, then forget EXIF
    img.thumbnail((MAX_ORIGINAL, MAX_ORIGINAL))
    img = _clean(img)

    cut = (remover or rembg_remover)(img.copy()).convert("RGBA")
    box = cut.getchannel("A").getbbox()                   # tight crop around the garment
    if box:
        cut = cut.crop(box)
    cut.thumbnail((MAX_CUTOUT, MAX_CUTOUT))
    cut = _clean(cut)
    thumb = cut.copy()
    thumb.thumbnail((THUMB, THUMB))

    paths = {
        "original": root / "originals" / f"{item_id}.jpg",
        "cutout": root / "cutouts" / f"{item_id}.png",
        "thumb": root / "thumbs" / f"{item_id}.webp",
    }
    for p in paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)
    img.save(paths["original"], "JPEG", quality=88)
    cut.save(paths["cutout"], "PNG", optimize=True)
    thumb.save(paths["thumb"], "WEBP", quality=85)
    return paths


def delete_files(item_id: str, root: Path) -> None:
    for kind, ext in zip(KINDS, ("jpg", "png", "webp")):
        (root / kind / f"{item_id}.{ext}").unlink(missing_ok=True)
