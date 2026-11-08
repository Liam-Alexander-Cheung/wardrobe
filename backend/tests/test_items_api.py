from conftest import make_photo


def test_upload_creates_untagged_item(upload):
    item = upload()
    assert item["id"] and item["category"] is None
    assert item["colors"] == [] and item["tags"] == []
    assert item["images"]["thumb"].startswith("/media/thumbs/")


def test_uploaded_images_are_served(client, upload):
    item = upload()
    for kind in ("original", "cutout", "thumb"):
        assert client.get(item["images"][kind]).status_code == 200


def test_reject_non_image_upload(client):
    r = client.post("/api/items", files={"file": ("x.jpg", b"nope", "image/jpeg")})
    assert r.status_code == 400


def test_get_update_delete(client, upload):
    item = upload()
    url = f"/api/items/{item['id']}"
    assert client.get(url).json()["id"] == item["id"]

    r = client.patch(url, json={"name": "Red tee", "category": "top", "colors": ["red"],
                                "seasons": ["summer"], "formality": 1})
    assert r.status_code == 200 and r.json()["name"] == "Red tee"
    assert client.get(url).json()["colors"] == ["red"]

    thumb = item["images"]["thumb"]
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    assert client.get(thumb).status_code == 404               # files removed too


def test_patch_validates_category_and_formality(client, upload):
    url = f"/api/items/{upload()['id']}"
    assert client.patch(url, json={"category": "hat-ish"}).status_code == 422
    assert client.patch(url, json={"formality": 9}).status_code == 422


def test_missing_item_is_404(client):
    assert client.get("/api/items/nope").status_code == 404
    assert client.patch("/api/items/nope", json={"name": "x"}).status_code == 404
    assert client.delete("/api/items/nope").status_code == 404


def test_filters(client, upload):
    a, b, c = upload(), upload(), upload()
    client.patch(f"/api/items/{a['id']}", json={"category": "top", "colors": ["red"], "seasons": ["summer"]})
    client.patch(f"/api/items/{b['id']}", json={"category": "top", "colors": ["navy"], "seasons": ["winter"]})
    client.patch(f"/api/items/{c['id']}", json={"category": "bottom", "colors": ["navy"], "name": "Navy chinos"})

    ids = lambda r: {i["id"] for i in r.json()}
    assert ids(client.get("/api/items")) == {a["id"], b["id"], c["id"]}
    assert ids(client.get("/api/items?category=top")) == {a["id"], b["id"]}
    assert ids(client.get("/api/items?color=navy")) == {b["id"], c["id"]}
    assert ids(client.get("/api/items?season=winter")) == {b["id"]}
    assert ids(client.get("/api/items?q=chino")) == {c["id"]}
    assert ids(client.get("/api/items?untagged=true")) == set()


def test_health_reports_count(client, upload):
    upload()
    assert client.get("/api/health").json() == {"ok": True, "items": 1, "demo": False}
