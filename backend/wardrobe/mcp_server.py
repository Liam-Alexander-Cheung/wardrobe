"""
The wardrobe as an MCP server, so Claude can look through your clothes and save outfits.

    .venv/bin/python -m wardrobe.mcp_server        (Claude Code starts this via .mcp.json)

It reads and writes the same SQLite file as the web app, so an outfit Claude saves shows
up in the Outfits tab with a "by Claude" marker. There is deliberately no delete tool:
the worst a confused run can do is add an outfit you don't like.

Token budget: list_items returns text only. Images cost ~1–2k tokens each, so Claude is
told to filter by tags first and only view_items the shortlist (max 6 per call).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError  # message reaches Claude; other errors are hidden
from pydantic import ValidationError

from . import config, layout
from .db import Store
from .models import Category, ItemUpdate, Season

INSTRUCTIONS = """You are helping Liam pick outfits from his own wardrobe.
Workflow: wardrobe_summary → list_items with filters (category/colour/season) → view_items
on a shortlist of at most 6 → create_outfit. Look before you recommend: base colour and
fit judgements on the images, not only on tags. If items are untagged, look at them and
tag them with update_item (category, colours, pattern, formality 1-5, seasons) first.
Explain each outfit in one or two sentences in its notes."""

COMPACT = ("id", "name", "category", "colors", "pattern", "formality", "seasons", "tags",
           "notes", "last_worn")


def build_server(store: Store, root: Path) -> MCPServer:
    mcp = MCPServer("wardrobe", instructions=INSTRUCTIONS)

    @mcp.tool()
    def wardrobe_summary() -> dict:
        """How many items per category, how many are untagged, how many outfits exist."""
        items = store.list_items()
        by_category: dict[str, int] = {}
        for i in items:
            if i["category"]:
                by_category[i["category"]] = by_category.get(i["category"], 0) + 1
        return {"items": len(items), "by_category": by_category,
                "untagged": sum(1 for i in items if not i["category"]),
                "outfits": len(store.list_outfits())}

    @mcp.tool()
    def list_items(category: Optional[Category] = None, color: Optional[str] = None,
                   season: Optional[Season] = None, query: Optional[str] = None,
                   untagged_only: bool = False) -> dict:
        """List clothes as text (no images). Filter to keep the list short."""
        rows = store.list_items(category, color, season, query, untagged_only)
        return {"items": [{k: i[k] for k in COMPACT} for i in rows]}

    @mcp.tool()
    def view_items(item_ids: list[str]) -> list:
        """See up to 6 items as small cut-out images, each preceded by its id and name."""
        if len(item_ids) > 6:
            raise ToolError("view at most 6 items per call (images are expensive)")
        out: list = []
        for item_id in item_ids:
            item = store.get_item(item_id)
            thumb = root / "thumbs" / f"{item_id}.webp"
            if not item or not thumb.is_file():
                out.append(f"{item_id}: not found")
                continue
            out.append(f"{item_id}: {item['name'] or 'untitled'} ({item['category'] or 'untagged'})")
            out.append(Image(path=thumb))
        return out

    @mcp.tool()
    def update_item(item_id: str, name: Optional[str] = None, category: Optional[Category] = None,
                    colors: Optional[list[str]] = None, pattern: Optional[str] = None,
                    formality: Optional[int] = None, seasons: Optional[list[Season]] = None,
                    tags: Optional[list[str]] = None, notes: Optional[str] = None) -> dict:
        """Tag or correct an item. Only the fields you pass change. formality: 1 gym … 5 suit."""
        given = {k: v for k, v in locals().items()
                 if k in ItemUpdate.model_fields and v is not None}
        try:
            fields = ItemUpdate(**given).model_dump(exclude_unset=True)
        except ValidationError as e:
            raise ToolError(str(e)) from None
        item = store.update_item(item_id, fields)
        if not item:
            raise ToolError(f"no item {item_id}")
        return {k: item[k] for k in COMPACT}

    @mcp.tool()
    def create_outfit(name: str, item_ids: list[str], occasion: str = "", notes: str = "") -> dict:
        """Save an outfit (shows in the app as 'by Claude'). All items must have a category."""
        if not 1 <= len(item_ids) <= 12 or len(set(item_ids)) != len(item_ids):
            raise ToolError("pass 1-12 distinct item ids")
        items = [store.get_item(i) for i in item_ids]
        missing = [i for i, it in zip(item_ids, items) if it is None]
        if missing:
            raise ToolError(f"unknown item(s): {', '.join(missing)}")
        untagged = [it["id"] for it in items if not it["category"]]
        if untagged:
            raise ToolError(f"untagged item(s) {', '.join(untagged)}: set a category with update_item first")
        outfit = store.create_outfit(name[:80], layout.place(items), occasion[:80], notes[:1000],
                                     created_by="claude")
        return {"id": outfit["id"], "name": outfit["name"], "items": len(outfit["items"])}

    @mcp.tool()
    def list_outfits(created_by: Optional[Literal["liam", "claude"]] = None) -> dict:
        """Saved outfits with their items, newest first. Avoid suggesting duplicates."""
        return {"outfits": [{"id": o["id"], "name": o["name"], "occasion": o["occasion"],
                             "created_by": o["created_by"],
                             "items": [{"id": i["item_id"], "name": i["name"], "slot": i["slot"]}
                                       for i in o["items"]]}
                            for o in store.list_outfits(created_by)]}

    return mcp


if __name__ == "__main__":
    root = config.data_dir()
    build_server(Store(root / "wardrobe.db"), root).run("stdio")
