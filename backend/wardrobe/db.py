"""
The wardrobe database: one SQLite file in the data folder.

The web API and the MCP server both go through this class, so there is exactly one
place that knows how items and outfits are stored. Lists (colours, seasons, tags) are
kept as JSON text; SQLite's json_each() lets us filter on them.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL DEFAULT '',
    category   TEXT,
    colors     TEXT NOT NULL DEFAULT '[]',
    pattern    TEXT,
    formality  INTEGER,
    seasons    TEXT NOT NULL DEFAULT '[]',
    tags       TEXT NOT NULL DEFAULT '[]',
    notes      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_worn  TEXT
);
CREATE TABLE IF NOT EXISTS outfits (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    occasion   TEXT NOT NULL DEFAULT '',
    notes      TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL DEFAULT 'liam',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outfit_items (
    outfit_id TEXT NOT NULL REFERENCES outfits(id) ON DELETE CASCADE,
    item_id   TEXT NOT NULL REFERENCES items(id)   ON DELETE CASCADE,
    slot      TEXT NOT NULL,
    x REAL NOT NULL DEFAULT 0, y REAL NOT NULL DEFAULT 0, z INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (outfit_id, item_id)
);
"""
LIST_FIELDS = ("colors", "seasons", "tags")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as c:
            c.executescript(SCHEMA)

    def connect(self) -> sqlite3.Connection:
        # A fresh connection per call: safe across FastAPI's worker threads and a
        # separate MCP process writing the same file.
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        return c

    # ---- items -------------------------------------------------------------------

    @staticmethod
    def _item(row: sqlite3.Row) -> dict:
        d = dict(row)
        for f in LIST_FIELDS:
            d[f] = json.loads(d[f])
        i = d["id"]
        d["images"] = {"original": f"/media/originals/{i}.jpg",
                       "cutout": f"/media/cutouts/{i}.png",
                       "thumb": f"/media/thumbs/{i}.webp"}
        return d

    def add_item(self, item_id: str, name: str = "") -> dict:
        with self.connect() as c:
            c.execute("INSERT INTO items (id, name, created_at) VALUES (?, ?, ?)",
                      (item_id, name, now()))
        return self.get_item(item_id)

    def get_item(self, item_id: str) -> Optional[dict]:
        with self.connect() as c:
            row = c.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return self._item(row) if row else None

    def list_items(self, category=None, color=None, season=None, q=None,
                   untagged=False) -> list[dict]:
        sql, args = ["SELECT * FROM items WHERE 1=1"], []
        if category:
            sql.append("AND category = ?"); args.append(category)
        for field, value in (("colors", color), ("seasons", season)):
            if value:
                sql.append(f"AND EXISTS (SELECT 1 FROM json_each(items.{field}) "
                           f"WHERE lower(value) = lower(?))"); args.append(value)
        if q:
            sql.append("AND (name LIKE ? OR notes LIKE ? OR tags LIKE ?)")
            args += [f"%{q}%"] * 3
        if untagged:
            sql.append("AND category IS NULL")
        sql.append("ORDER BY created_at DESC, rowid DESC")
        with self.connect() as c:
            return [self._item(r) for r in c.execute(" ".join(sql), args)]

    def update_item(self, item_id: str, fields: dict) -> Optional[dict]:
        if not self.get_item(item_id):
            return None
        if fields:
            vals = {k: json.dumps(v) if k in LIST_FIELDS else v for k, v in fields.items()}
            cols = ", ".join(f"{k} = ?" for k in vals)        # keys come from ItemUpdate only
            with self.connect() as c:
                c.execute(f"UPDATE items SET {cols} WHERE id = ?", [*vals.values(), item_id])
        return self.get_item(item_id)

    def delete_item(self, item_id: str) -> bool:
        with self.connect() as c:
            return c.execute("DELETE FROM items WHERE id = ?", (item_id,)).rowcount > 0

    def count_items(self) -> int:
        with self.connect() as c:
            return c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
