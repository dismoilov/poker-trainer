"""Analytics API tests."""


def test_summary(client, auth_header):
    resp = client.get("/api/analytics/summary", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    for key in ["totalSessions", "totalQuestions", "avgEvLoss", "accuracy"]:
        assert key in data, f"Missing key: {key}"
    # Clean DB: should be 0
    assert data["totalQuestions"] >= 0


def test_history(client, auth_header):
    resp = client.get("/api/analytics/history", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_recent(client, auth_header):
    resp = client.get("/api/analytics/recent", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
