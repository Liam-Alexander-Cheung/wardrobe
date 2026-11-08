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
        d["images"] = Store._item_images(d["id"])
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

    # ---- outfits -----------------------------------------------------------------

    class UnknownItem(ValueError):
        pass

    def _write_outfit_items(self, c: sqlite3.Connection, outfit_id: str, items: list[dict]) -> None:
        ids = [i["item_id"] for i in items]
        found = {r[0] for r in c.execute(
            f"SELECT id FROM items WHERE id IN ({','.join('?' * len(ids))})", ids)}
        missing = [i for i in ids if i not in found]
        if missing:
            raise Store.UnknownItem(f"unknown item(s): {', '.join(missing)}")
        c.execute("DELETE FROM outfit_items WHERE outfit_id = ?", (outfit_id,))
        c.executemany(
            "INSERT INTO outfit_items (outfit_id, item_id, slot, x, y, z) VALUES (?, ?, ?, ?, ?, ?)",
            [(outfit_id, i["item_id"], i["slot"], i["x"], i["y"], i["z"]) for i in items])

    def create_outfit(self, name: str, items: list[dict], occasion: str = "", notes: str = "",
                      created_by: str = "liam") -> dict:
        outfit_id = new_id()
        with self.connect() as c:   # one transaction: no half-saved outfit if an item is missing
            c.execute("INSERT INTO outfits (id, name, occasion, notes, created_by, created_at) "
                      "VALUES (?, ?, ?, ?, ?, ?)", (outfit_id, name, occasion, notes, created_by, now()))
            self._write_outfit_items(c, outfit_id, items)
        return self.get_outfit(outfit_id)

    def update_outfit(self, outfit_id: str, name: str, items: list[dict], occasion: str = "",
                      notes: str = "") -> Optional[dict]:
        with self.connect() as c:
            if not c.execute("UPDATE outfits SET name = ?, occasion = ?, notes = ? WHERE id = ?",
                             (name, occasion, notes, outfit_id)).rowcount:
                return None
            self._write_outfit_items(c, outfit_id, items)
        return self.get_outfit(outfit_id)

    def _outfit(self, c: sqlite3.Connection, row: sqlite3.Row) -> dict:
        d = dict(row)
        rows = c.execute("SELECT oi.*, i.name FROM outfit_items oi JOIN items i ON i.id = oi.item_id "
                         "WHERE oi.outfit_id = ? ORDER BY oi.z, oi.rowid", (d["id"],))
        d["items"] = [{k: r[k] for k in ("item_id", "slot", "x", "y", "z", "name")}
                      | {"images": self._item_images(r["item_id"])} for r in rows]
        return d

    @staticmethod
    def _item_images(i: str) -> dict:
        return {"original": f"/media/originals/{i}.jpg", "cutout": f"/media/cutouts/{i}.png",
                "thumb": f"/media/thumbs/{i}.webp"}

    def get_outfit(self, outfit_id: str) -> Optional[dict]:
        with self.connect() as c:
            row = c.execute("SELECT * FROM outfits WHERE id = ?", (outfit_id,)).fetchone()
            return self._outfit(c, row) if row else None

    def list_outfits(self, created_by: Optional[str] = None) -> list[dict]:
        sql, args = "SELECT * FROM outfits", []
        if created_by:
            sql, args = sql + " WHERE created_by = ?", [created_by]
        with self.connect() as c:
            return [self._outfit(c, r) for r in c.execute(sql + " ORDER BY created_at DESC, rowid DESC", args)]

    def delete_outfit(self, outfit_id: str) -> bool:
        with self.connect() as c:
            return c.execute("DELETE FROM outfits WHERE id = ?", (outfit_id,)).rowcount > 0
