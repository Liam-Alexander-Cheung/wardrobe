def tagged(client, upload, category):
    item = upload()
    client.patch(f"/api/items/{item['id']}", json={"category": category})
    return item["id"]


def outfit_body(*pairs, name="School, cold"):
    return {"name": name, "occasion": "school", "notes": "",
            "items": [{"item_id": i, "slot": s, "x": 0.5, "y": 0.3, "z": n}
                      for n, (i, s) in enumerate(pairs)]}


def test_create_list_get_delete(client, upload):
    top, bottom = tagged(client, upload, "top"), tagged(client, upload, "bottom")
    r = client.post("/api/outfits", json=outfit_body((top, "top"), (bottom, "bottom")))
    assert r.status_code == 201, r.text
    outfit = r.json()
    assert outfit["created_by"] == "liam"
    assert [i["item_id"] for i in outfit["items"]] == [top, bottom]
    assert outfit["items"][0]["images"]["cutout"].endswith(f"{top}.png")

    assert [o["id"] for o in client.get("/api/outfits").json()] == [outfit["id"]]
    assert client.get(f"/api/outfits/{outfit['id']}").json()["name"] == "School, cold"
    assert client.delete(f"/api/outfits/{outfit['id']}").status_code == 204
    assert client.get(f"/api/outfits/{outfit['id']}").status_code == 404
    assert client.get(f"/api/items/{top}").status_code == 200        # items survive


def test_update_replaces_items(client, upload):
    a, b, c = (tagged(client, upload, k) for k in ("top", "bottom", "shoes"))
    oid = client.post("/api/outfits", json=outfit_body((a, "top"), (b, "bottom"))).json()["id"]
    r = client.put(f"/api/outfits/{oid}", json=outfit_body((a, "top"), (c, "shoes"), name="v2"))
    assert r.status_code == 200
    assert r.json()["name"] == "v2"
    assert {i["item_id"] for i in r.json()["items"]} == {a, c}


def test_slot_and_position_validation(client, upload):
    a = tagged(client, upload, "top")
    assert client.post("/api/outfits", json=outfit_body((a, "hat"))).status_code == 422
    bad = outfit_body((a, "top")); bad["items"][0]["x"] = 3
    assert client.post("/api/outfits", json=bad).status_code == 422
    assert client.post("/api/outfits", json=outfit_body()).status_code == 422      # empty


def test_unknown_item_is_400(client):
    r = client.post("/api/outfits", json=outfit_body(("000000000000", "top")))
    assert r.status_code == 400


def test_duplicate_item_is_422(client, upload):
    a = tagged(client, upload, "top")
    assert client.post("/api/outfits", json=outfit_body((a, "top"), (a, "top"))).status_code == 422


def test_deleting_an_item_removes_it_from_outfits(client, upload):
    a, b = tagged(client, upload, "top"), tagged(client, upload, "bottom")
    oid = client.post("/api/outfits", json=outfit_body((a, "top"), (b, "bottom"))).json()["id"]
    client.delete(f"/api/items/{a}")
    assert [i["item_id"] for i in client.get(f"/api/outfits/{oid}").json()["items"]] == [b]


def test_missing_outfit(client, upload):
    a = tagged(client, upload, "top")
    assert client.put("/api/outfits/nope", json=outfit_body((a, "top"))).status_code == 404
    assert client.get("/api/outfits/nope").status_code == 404
    assert client.delete("/api/outfits/nope").status_code == 404
