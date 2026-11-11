"""
The web server: a small JSON API over the Store, plus the built React app.

    GET    /api/health              {"ok", "items", "demo"}
    GET    /api/items               list, filters: category, color, season, q, untagged
    POST   /api/items               upload ONE photo (multipart "file") -> new item
    GET    /api/items/{id}
    PATCH  /api/items/{id}          change fields (see models.ItemUpdate)
    DELETE /api/items/{id}          removes the item and its three image files
    GET    /api/outfits             saved outfits, newest first (POST to create)
    GET/PUT/DELETE /api/outfits/{id}
    POST   /api/ask                 {"message", "session_id"?} -> Claude's answer as SSE
    GET    /media/{kind}/{file}     the images, straight from the private data folder

One photo per request on purpose: the browser uploads an AirDrop batch one by one and
shows progress, instead of one request that hangs for a minute while rembg works.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import ask, config, ingest
from .db import Store, new_id
from .guard import LocalOnly
from .models import AskIn, Category, Item, ItemUpdate, Outfit, OutfitIn, Season

FRONTEND_DIST = config.REPO_ROOT / "frontend" / "dist"
MEDIA_NAME = re.compile(r"^[0-9a-f]{12}\.(jpg|png|webp)$")


def create_app(data_dir: Optional[Path] = None, remover=None, demo: bool = False,
               claude_bin: str = "claude") -> FastAPI:
    root = config.check_outside_repo(data_dir or config.data_dir())
    store = Store(root / "wardrobe.db")
    app = FastAPI(title="GuardTheRobes", docs_url=None, redoc_url=None)
    app.state.store, app.state.root = store, root

    def item_or_404(item_id: str) -> dict:
        item = store.get_item(item_id)
        if not item:
            raise HTTPException(404, "no such item")
        return item

    @app.get("/api/health")
    def health():
        return {"ok": True, "items": store.count_items(), "demo": demo}

    @app.get("/api/items", response_model=list[Item])
    def list_items(category: Optional[Category] = None, color: Optional[str] = None,
                   season: Optional[Season] = None, q: Optional[str] = None,
                   untagged: bool = False):
        return store.list_items(category, color, season, q, untagged)

    @app.post("/api/items", response_model=Item, status_code=201)
    def upload(file: UploadFile = File(...)):
        # A plain `def`: FastAPI runs it in a worker thread, so rembg doesn't block others.
        item_id = new_id()
        try:
            ingest.process(file.file.read(), item_id, root, remover=remover)
        except ingest.NotAnImage as e:
            raise HTTPException(400, str(e))
        return store.add_item(item_id)

    @app.get("/api/items/{item_id}", response_model=Item)
    def get_item(item_id: str):
        return item_or_404(item_id)

    @app.patch("/api/items/{item_id}", response_model=Item)
    def update_item(item_id: str, body: ItemUpdate):
        item = store.update_item(item_id, body.model_dump(exclude_unset=True))
        if not item:
            raise HTTPException(404, "no such item")
        return item

    @app.delete("/api/items/{item_id}", status_code=204)
    def delete_item(item_id: str):
        if not store.delete_item(item_id):
            raise HTTPException(404, "no such item")
        ingest.delete_files(item_id, root)
        return Response(status_code=204)

    # ---- outfits ------------------------------------------------------------------

    def save_outfit(body: OutfitIn, outfit_id: Optional[str] = None) -> dict:
        items = [i.model_dump() for i in body.items]
        try:
            if outfit_id is None:
                return store.create_outfit(body.name, items, body.occasion, body.notes)
            outfit = store.update_outfit(outfit_id, body.name, items, body.occasion, body.notes)
        except Store.UnknownItem as e:
            raise HTTPException(400, str(e))
        if not outfit:
            raise HTTPException(404, "no such outfit")
        return outfit

    @app.get("/api/outfits", response_model=list[Outfit])
    def list_outfits():
        return store.list_outfits()

    @app.post("/api/outfits", response_model=Outfit, status_code=201)
    def create_outfit(body: OutfitIn):
        return save_outfit(body)

    @app.get("/api/outfits/{outfit_id}", response_model=Outfit)
    def get_outfit(outfit_id: str):
        outfit = store.get_outfit(outfit_id)
        if not outfit:
            raise HTTPException(404, "no such outfit")
        return outfit

    @app.put("/api/outfits/{outfit_id}", response_model=Outfit)
    def update_outfit(outfit_id: str, body: OutfitIn):
        return save_outfit(body, outfit_id)

    @app.delete("/api/outfits/{outfit_id}", status_code=204)
    def delete_outfit(outfit_id: str):
        if not store.delete_outfit(outfit_id):
            raise HTTPException(404, "no such outfit")
        return Response(status_code=204)

    # ---- ask Claude ---------------------------------------------------------------

    busy = asyncio.Lock()   # one Claude run at a time: it's one person's wardrobe and quota

    @app.post("/api/ask")
    async def ask_claude(body: AskIn):
        if busy.locked():
            raise HTTPException(409, "Claude is still answering the last message")

        async def stream():
            async with busy:
                async for event in ask.run(body.message, body.session_id, root, claude_bin):
                    yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"cache-control": "no-cache"})

    @app.get("/media/{kind}/{name}")
    def media(kind: str, name: str, request: Request):
        path = root / kind / name
        if kind not in ingest.KINDS or not MEDIA_NAME.match(name) or not path.is_file():
            raise HTTPException(404)
        # Revalidate every time: photos can change in place (colour repair). The ETag makes
        # that cheap: an unchanged photo costs a 304 with no body.
        cache = {"cache-control": "private, no-cache"}
        response = FileResponse(path, headers=cache, stat_result=path.stat())
        if request.headers.get("if-none-match") == response.headers["etag"]:
            return Response(status_code=304, headers={"etag": response.headers["etag"], **cache})
        return response

    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    return LocalOnly(app)
