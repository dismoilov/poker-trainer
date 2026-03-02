"""Jobs API tests."""


def test_get_jobs_empty(client, auth_header):
    """Clean DB should have no jobs."""
    resp = client.get("/api/jobs", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_create_job(client, auth_header):
    resp = client.post(
        "/api/jobs/solve",
        json={"spotId": "srp-btn-bb-flop"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] in ("pending", "running")
    assert job["spotId"] == "srp-btn-bb-flop"
    for key in ["id", "type", "spotName", "progress", "createdAt", "log"]:
        assert key in job, f"Missing key: {key}"
