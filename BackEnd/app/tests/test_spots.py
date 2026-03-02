"""Spots API tests."""


def test_get_spots(client, auth_header):
    resp = client.get("/api/spots", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 43
    spot = data[0]
    for key in ["id", "name", "format", "positions", "stack", "rakeProfile", "streets", "tags", "solved", "nodeCount", "isCustom"]:
        assert key in spot, f"Missing key: {key}"


def test_get_spot_by_id(client, auth_header):
    resp = client.get("/api/spots/srp-btn-bb-flop", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["id"] == "srp-btn-bb-flop"


def test_get_spot_not_found(client, auth_header):
    resp = client.get("/api/spots/nonexistent", headers=auth_header)
    assert resp.status_code == 404


def test_create_custom_spot(client, auth_header):
    resp = client.post(
        "/api/spots",
        json={"format": "SRP", "positions": ["BTN", "BB"], "street": "flop", "stack": 100},
        headers=auth_header,
    )
    assert resp.status_code == 200
    spot = resp.json()
    assert spot["isCustom"] is True
    assert spot["solved"] is False
    assert spot["format"] == "SRP"
    assert spot["nodeCount"] == 6
    assert "BTN" in spot["positions"]
    assert "BB" in spot["positions"]
    # Verify the spot exists
    resp2 = client.get(f"/api/spots/{spot['id']}", headers=auth_header)
    assert resp2.status_code == 200


def test_create_squeeze_spot(client, auth_header):
    resp = client.post(
        "/api/spots",
        json={"format": "squeeze", "positions": ["BB", "CO"], "street": "flop", "stack": 100},
        headers=auth_header,
    )
    assert resp.status_code == 200
    spot = resp.json()
    assert spot["format"] == "squeeze"
    assert spot["isCustom"] is True


def test_create_spot_invalid_format(client, auth_header):
    resp = client.post(
        "/api/spots",
        json={"format": "invalid", "positions": ["BTN", "BB"], "street": "flop"},
        headers=auth_header,
    )
    assert resp.status_code == 400


def test_create_spot_invalid_position(client, auth_header):
    resp = client.post(
        "/api/spots",
        json={"format": "SRP", "positions": ["INVALID", "BB"], "street": "flop"},
        headers=auth_header,
    )
    assert resp.status_code == 400


def test_delete_custom_spot(client, auth_header):
    # Create a spot first
    resp = client.post(
        "/api/spots",
        json={"format": "SRP", "positions": ["CO", "BB"], "street": "turn", "stack": 50},
        headers=auth_header,
    )
    assert resp.status_code == 200
    spot_id = resp.json()["id"]

    # Delete it
    resp2 = client.delete(f"/api/spots/{spot_id}", headers=auth_header)
    assert resp2.status_code == 200

    # Verify it's gone
    resp3 = client.get(f"/api/spots/{spot_id}", headers=auth_header)
    assert resp3.status_code == 404


def test_delete_builtin_spot_forbidden(client, auth_header):
    resp = client.delete("/api/spots/srp-btn-bb-flop", headers=auth_header)
    assert resp.status_code == 400
    assert "built-in" in resp.json()["detail"].lower()
