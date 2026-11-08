"""The MCP server, driven through a real in-memory MCP client (same protocol Claude uses)."""

import asyncio
import json

import pytest
from mcp.client import Client

from conftest import fake_remover, make_photo
from wardrobe import ingest
from wardrobe.db import Store, new_id
from wardrobe.mcp_server import build_server


@pytest.fixture
def store(data_dir):
    return Store(data_dir / "wardrobe.db")


def add(store, data_dir, **fields):
    item_id = new_id()
    ingest.process(make_photo(), item_id, data_dir, remover=fake_remover)
    store.add_item(item_id)
    return store.update_item(item_id, fields)


def call(data_dir, store, tool, **args):
    async def go():
        async with Client(build_server(store, data_dir)) as c:
            return await c.call_tool(tool, args)
    return asyncio.run(go())


def payload(result):
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


def test_tools_are_exactly_these(store, data_dir):
    async def go():
        async with Client(build_server(store, data_dir)) as c:
            return {t.name for t in (await c.list_tools()).tools}
    names = asyncio.run(go())
    assert names == {"wardrobe_summary", "list_items", "view_items", "update_item",
                     "create_outfit", "list_outfits"}                # deliberately no delete


def test_summary(store, data_dir):
    add(store, data_dir, category="top"); add(store, data_dir, category="top"); add(store, data_dir)
    s = payload(call(data_dir, store, "wardrobe_summary"))
    assert s["items"] == 3 and s["by_category"] == {"top": 2} and s["untagged"] == 1


def test_list_items_is_compact_and_filters(store, data_dir):
    a = add(store, data_dir, name="Navy chinos", category="bottom", colors=["navy"])
    add(store, data_dir, name="Red tee", category="top", colors=["red"])
    rows = payload(call(data_dir, store, "list_items", color="navy"))["items"]
    assert [r["id"] for r in rows] == [a["id"]]
    assert "images" not in rows[0] and "created_at" not in rows[0]       # fewer tokens


def test_view_items_returns_thumbnails(store, data_dir):
    a, b = add(store, data_dir, name="A"), add(store, data_dir, name="B")
    r = call(data_dir, store, "view_items", item_ids=[a["id"], b["id"], "000000000000"])
    images = [c for c in r.content if c.type == "image"]
    texts = " ".join(c.text for c in r.content if c.type == "text")
    assert len(images) == 2 and images[0].mime_type == "image/webp"
    assert "000000000000" in texts and "not found" in texts


def test_view_items_caps_at_six(store, data_dir):
    ids = [add(store, data_dir)["id"] for _ in range(7)]
    assert call(data_dir, store, "view_items", item_ids=ids).is_error


def test_update_item_tags_and_validates(store, data_dir):
    a = add(store, data_dir)
    out = payload(call(data_dir, store, "update_item", item_id=a["id"], category="top",
                       colors=["white"], formality=2, seasons=["winter"]))
    assert out["category"] == "top" and store.get_item(a["id"])["seasons"] == ["winter"]
    assert call(data_dir, store, "update_item", item_id=a["id"], category="hat").is_error
    assert call(data_dir, store, "update_item", item_id="nope", name="x").is_error


def test_create_outfit_as_claude(store, data_dir):
    top = add(store, data_dir, category="top")
    bottom = add(store, data_dir, category="bottom")
    shoes = add(store, data_dir, category="shoes")
    out = payload(call(data_dir, store, "create_outfit", name="School, cold", occasion="school",
                       item_ids=[shoes["id"], top["id"], bottom["id"]], notes="Layers for 4°C"))
    saved = store.get_outfit(out["id"])
    assert saved["created_by"] == "claude" and saved["notes"] == "Layers for 4°C"
    pos = {i["slot"]: i["y"] for i in saved["items"]}
    assert pos["top"] < pos["bottom"] < pos["shoes"]                     # laid out sensibly


def test_create_outfit_refuses_untagged_or_unknown(store, data_dir):
    top, raw = add(store, data_dir, category="top"), add(store, data_dir)
    r = call(data_dir, store, "create_outfit", name="x", item_ids=[top["id"], raw["id"]])
    assert r.is_error and "untagged" in r.content[0].text
    assert call(data_dir, store, "create_outfit", name="x", item_ids=["000000000000"]).is_error
    assert store.list_outfits() == []


def test_list_outfits(store, data_dir):
    top = add(store, data_dir, category="top", name="Tee")
    store.create_outfit("Mine", [{"item_id": top["id"], "slot": "top", "x": .5, "y": .3, "z": 0}])
    call(data_dir, store, "create_outfit", name="Claude's", item_ids=[top["id"]])
    all_ = payload(call(data_dir, store, "list_outfits"))["outfits"]
    assert {o["name"] for o in all_} == {"Mine", "Claude's"}
    assert all_[0]["items"] == [{"id": top["id"], "name": "Tee", "slot": "top"}]
    mine = payload(call(data_dir, store, "list_outfits", created_by="claude"))["outfits"]
    assert [o["name"] for o in mine] == ["Claude's"]
