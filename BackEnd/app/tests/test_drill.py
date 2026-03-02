"""Drill API tests: next question, submit answer."""


def test_drill_next(client, auth_header):
    resp = client.post(
        "/api/drill/next",
        json={"spotId": "srp-btn-bb-flop"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ["questionId", "spotId", "nodeId", "board", "hand", "handCards",
                 "position", "potSize", "stackSize", "actions", "lineDescription", "street"]:
        assert key in data, f"Missing key: {key}"
    assert len(data["board"]) >= 3
    assert len(data["handCards"]) == 2
    assert len(data["actions"]) >= 2


def test_drill_next_with_node(client, auth_header):
    resp = client.post(
        "/api/drill/next",
        json={"spotId": "srp-btn-bb-flop", "nodeId": "srp-btn-bb-flop__root"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert resp.json()["nodeId"] == "srp-btn-bb-flop__root"


def test_drill_answer(client, auth_header):
    # Get a question first
    q_resp = client.post(
        "/api/drill/next",
        json={"spotId": "srp-btn-bb-flop"},
        headers=auth_header,
    )
    q = q_resp.json()

    # Submit answer
    resp = client.post(
        "/api/drill/answer",
        json={
            "nodeId": q["nodeId"],
            "hand": q["hand"],
            "actionId": q["actions"][0]["id"],
            "questionId": q["questionId"],
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    fb = resp.json()
    for key in ["frequencies", "chosenAction", "correctAction", "evLoss", "accuracy", "explanation"]:
        assert key in fb, f"Missing key: {key}"
    assert fb["evLoss"] >= 0
    assert 0 <= fb["accuracy"] <= 1
    assert len(fb["explanation"]) >= 3
