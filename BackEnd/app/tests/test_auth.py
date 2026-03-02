"""Auth tests: login, protected endpoints, 401."""


def test_login_ok(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "accessToken" in data
    assert data["user"]["username"] == "admin"


def test_login_bad_password(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401


def test_protected_without_token(client):
    resp = client.get("/api/spots")
    assert resp.status_code == 401


def test_me_endpoint(client, auth_header):
    resp = client.get("/api/auth/me", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"
