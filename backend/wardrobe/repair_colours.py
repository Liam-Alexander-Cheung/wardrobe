"""
One-off repair for photos added before the colour fix (2026-11-08).

Those files hold iPhone Display P3 pixel values but no colour label, so browsers showed
them washed out. This converts them P3 -> sRGB and labels them. Files that already carry
a colour label (anything ingested after the fix) are skipped, so running it twice is safe.

    .venv/bin/python -m wardrobe.repair_colours --dry-run
    .venv/bin/python -m wardrobe.repair_colours
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

from . import config, ingest

DISPLAY_P3 = Path("/System/Library/ColorSync/Profiles/Display P3.icc")
FILES = (("originals", "jpg", "JPEG", {"quality": 88}),
         ("cutouts", "png", "PNG", {"optimize": True}),
         ("thumbs", "webp", "WEBP", {"quality": 85}))


def repair(root: Path, source_icc: bytes, dry_run: bool = False) -> int:
    """Convert every unlabelled image under root from source_icc to sRGB. Returns the count."""
    fixed = 0
    for kind, ext, fmt, opts in FILES:
        for path in sorted((root / kind).glob(f"*.{ext}")):
            img = Image.open(path)
            if img.info.get("icc_profile"):
                continue                                   # already labelled: new or repaired
            fixed += 1
            if dry_run:
                continue
            img.load()
            alpha = img.getchannel("A") if img.mode == "RGBA" else None
            out = ingest.to_srgb(img.convert("RGB"), source_icc)
            if alpha is not None:
                out.putalpha(alpha)
            out.save(path, fmt, icc_profile=ingest.SRGB_ICC, **opts)
    return fixed


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv[1:]
    root = config.data_dir()
    n = repair(root, DISPLAY_P3.read_bytes(), dry_run=dry)
    print(f"{'Would fix' if dry else 'Fixed'} {n} image files in {root}")
