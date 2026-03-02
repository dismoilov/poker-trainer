"""Explore API tests: nodes + strategy."""


def test_get_nodes(client, auth_header):
    resp = client.get("/api/explore/nodes?spotId=srp-btn-bb-flop", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    node = data[0]
    for key in ["id", "spotId", "street", "pot", "player", "actions", "lineDescription", "children"]:
        assert key in node, f"Missing key: {key}"


def test_get_single_node(client, auth_header):
    resp = client.get(
        "/api/explore/node?spotId=srp-btn-bb-flop&nodeId=srp-btn-bb-flop__root",
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "srp-btn-bb-flop__root"


def test_get_strategy(client, auth_header):
    resp = client.get(
        "/api/explore/strategy?nodeId=srp-btn-bb-flop__root",
        headers=auth_header,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 169
    assert "AA" in data
    assert "AKs" in data
    freqs = data["AA"]
    assert abs(sum(freqs.values()) - 1.0) < 0.01


def test_strategy_not_found(client, auth_header):
    resp = client.get("/api/explore/strategy?nodeId=nonexistent", headers=auth_header)
    assert resp.status_code == 404
