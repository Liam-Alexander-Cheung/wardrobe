"""
Where a garment lands on the flat-lay board when nobody dragged it there (outfits Claude
makes). Mirrors HOME in frontend/src/Board.tsx: keep the two in sync.
"""

HOME = {
    "outerwear": (0.30, 0.30), "top": (0.55, 0.27), "fullbody": (0.50, 0.42),
    "bottom": (0.52, 0.64), "shoes": (0.50, 0.90), "accessory": (0.85, 0.16),
}
STACK = ["outerwear", "top", "fullbody", "bottom", "shoes", "accessory"]   # back to front


def place(items: list[dict]) -> list[dict]:
    """items: [{"id", "category"}] -> outfit placements with x/y/z filled in."""
    seen: dict[str, int] = {}
    out = []
    for item in items:
        slot = item["category"]
        n = seen[slot] = seen.get(slot, -1) + 1          # 2nd accessory goes below the 1st
        x, y = HOME[slot]
        out.append({"item_id": item["id"], "slot": slot, "x": x, "y": min(1.0, y + 0.14 * n),
                    "z": STACK.index(slot) * 2 + n})
    return out
