"""
Demo wardrobe: 12 garments drawn in code, so anyone who clones the public repo can try
the app without photographing anything, and no real clothes ever enter git.

    .venv/bin/python -m wardrobe --demo     (data goes to a temp folder, gone on reboot)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import layout
from .db import Store

S = 1000  # drawing canvas; drawn at 2x and scaled down for smooth edges


def _shirt(d, c, long=True, collar=False, hood=False):
    sleeve = [(150, 520), (60, 760), (170, 800), (300, 560)] if long else [(200, 300), (90, 470), (200, 540), (300, 420)]
    d.polygon([(320, 180), (430, 150), (570, 150), (680, 180), (800, 300), (700, 420), (700, 860), (300, 860), (300, 420), (200, 300)], fill=c)
    d.polygon(sleeve, fill=c)
    d.polygon([(S - x, y) for x, y in sleeve], fill=c)
    if long:
        d.polygon([(200, 300), (150, 520), (300, 560), (300, 420)], fill=c)
        d.polygon([(800, 300), (850, 520), (700, 560), (700, 420)], fill=c)
    if collar:
        d.polygon([(430, 150), (500, 260), (390, 230)], fill=_shade(c, 0.9))
        d.polygon([(570, 150), (500, 260), (610, 230)], fill=_shade(c, 0.9))
        d.line([(500, 260), (500, 860)], fill=_shade(c, 0.8), width=6)
    elif hood:
        d.ellipse((370, 40, 630, 260), fill=_shade(c, 0.85))
        d.rectangle((420, 520, 580, 680), fill=_shade(c, 0.9))
    else:
        d.ellipse((420, 120, 580, 210), fill=(0, 0, 0, 0))


def _coat(d, c, long=True):
    bottom = 960 if long else 800
    _shirt(d, c)
    d.polygon([(300, 420), (700, 420), (720, bottom), (280, bottom)], fill=c)
    d.polygon([(430, 150), (500, 420), (380, 330)], fill=_shade(c, 0.85))
    d.polygon([(570, 150), (500, 420), (620, 330)], fill=_shade(c, 0.85))
    d.line([(500, 420), (500, bottom)], fill=_shade(c, 0.75), width=6)
    for y in (500, 620, 740):
        d.ellipse((520, y, 545, y + 25), fill=_shade(c, 0.6))


def _trousers(d, c, flare=False):
    hem = 140 if flare else 60
    d.polygon([(300, 80), (700, 80), (720 + hem // 2, 940), (530, 940), (500, 330), (470, 940), (280 - hem // 2, 940)], fill=c)
    d.rectangle((300, 80, 700, 130), fill=_shade(c, 0.85))


def _shoe(d, c, boot=False):
    for dx in (0, 360):
        top = 300 if boot else 470
        d.polygon([(120 + dx, top), (290 + dx, top), (300 + dx, 560), (470 + dx, 640), (470 + dx, 720), (110 + dx, 720)], fill=c)
        d.rectangle((105 + dx, 700, 475 + dx, 740), fill=_shade(c, 0.6 if boot else 1.1))


def _beanie(d, c):
    d.chord((200, 220, 800, 900), 180, 360, fill=c)
    d.rectangle((190, 540, 810, 680), fill=_shade(c, 0.85))
    d.ellipse((440, 140, 560, 260), fill=c)


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3]) + (255,)


# name, category, colours, formality, seasons, drawing
WARDROBE = [
    ("White oxford shirt", "top", ["white"], 3, ["spring", "summer", "autumn"], lambda d: _shirt(d, (236, 236, 230, 255), collar=True)),
    ("Navy crewneck jumper", "top", ["navy"], 2, ["autumn", "winter"], lambda d: _shirt(d, (38, 52, 92, 255))),
    ("Red tee", "top", ["red"], 1, ["summer"], lambda d: _shirt(d, (178, 40, 44, 255), long=False)),
    ("Grey hoodie", "top", ["grey"], 1, ["autumn", "winter", "spring"], lambda d: _shirt(d, (138, 138, 140, 255), hood=True)),
    ("Camel coat", "outerwear", ["camel"], 4, ["autumn", "winter"], lambda d: _coat(d, (186, 140, 92, 255))),
    ("Denim jacket", "outerwear", ["blue"], 2, ["spring", "autumn"], lambda d: _coat(d, (74, 104, 150, 255), long=False)),
    ("Kick flare jeans", "bottom", ["blue"], 2, ["spring", "autumn", "winter"], lambda d: _trousers(d, (62, 90, 140, 255), flare=True)),
    ("Beige chinos", "bottom", ["beige"], 3, ["spring", "summer"], lambda d: _trousers(d, (204, 184, 148, 255))),
    ("Black trousers", "bottom", ["black"], 4, ["autumn", "winter", "spring"], lambda d: _trousers(d, (34, 34, 36, 255))),
    ("White sneakers", "shoes", ["white"], 1, ["spring", "summer", "autumn"], lambda d: _shoe(d, (240, 240, 236, 255))),
    ("Brown boots", "shoes", ["brown"], 3, ["autumn", "winter"], lambda d: _shoe(d, (110, 70, 42, 255), boot=True)),
    ("Grey beanie", "accessory", ["grey"], 1, ["winter"], lambda d: _beanie(d, (120, 120, 124, 255))),
]
OUTFITS = [  # (name, occasion, item names, author, notes)
    ("Weekend layers", "town", ["Grey hoodie", "Denim jacket", "Kick flare jeans", "White sneakers"], "liam", ""),
    ("Cold school day", "school", ["Navy crewneck jumper", "Camel coat", "Black trousers", "Brown boots", "Grey beanie"], "claude",
     "Navy under camel is a classic pair; boots and beanie for 4°C."),
    ("Summer lunch", "family", ["White oxford shirt", "Beige chinos", "White sneakers"], "claude",
     "Light colours, smart enough for a restaurant."),
]


def _render(draw_fn) -> Image.Image:
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    big = layer.resize((S * 2, S * 2), Image.NEAREST).filter(ImageFilter.SMOOTH)   # soften edges
    img = big.resize((S, S), Image.LANCZOS)
    return img.crop(img.getchannel("A").getbbox())


def seed(root: Path) -> Store:
    store = Store(root / "wardrobe.db")
    if store.count_items():
        return store
    for kind in ("originals", "cutouts", "thumbs"):
        (root / kind).mkdir(parents=True, exist_ok=True)
    ids = {}
    for n, (name, category, colors, formality, seasons, draw) in enumerate(WARDROBE):
        item_id = f"{n + 1:012x}"
        cut = _render(draw)
        cut.save(root / "cutouts" / f"{item_id}.png")
        thumb = cut.copy(); thumb.thumbnail((400, 400)); thumb.save(root / "thumbs" / f"{item_id}.webp")
        photo = Image.new("RGB", (cut.width + 200, cut.height + 200), (176, 168, 156))
        photo.paste(cut, (100, 100), cut); photo.save(root / "originals" / f"{item_id}.jpg")
        store.add_item(item_id, name)
        store.update_item(item_id, {"category": category, "colors": colors, "formality": formality, "seasons": seasons})
        ids[name] = {"id": item_id, "category": category}
    for name, occasion, names, author, notes in OUTFITS:
        store.create_outfit(name, layout.place([ids[n] for n in names]), occasion, notes, author)
    return store


def temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="wardrobe-demo-"))
