"""Smoke test: quick check that all endpoints work end-to-end."""

import sys
import requests

BASE = "http://localhost:8000"


def smoke():
    ok = True

    def check(name, fn):
        nonlocal ok
        try:
            fn()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            ok = False

    print("=== PokerTrainer Smoke Test ===\n")

    # 1) Login
    token = None

    def do_login():
        nonlocal token
        r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"
        data = r.json()
        token = data["accessToken"]
        print(f"    token: {token[:20]}...")
        print(f"    user: {data['user']['username']}")

    check("Login", do_login)
    if not token:
        print("\nLogin failed, cannot continue.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # 2) Spots
    def do_spots():
        r = requests.get(f"{BASE}/api/spots", headers=headers)
        assert r.status_code == 200
        spots = r.json()
        assert len(spots) == 6, f"Expected 6 spots, got {len(spots)}"
        print(f"    count: {len(spots)}, first: {spots[0]['id']}")

    check("GET /api/spots", do_spots)

    # 3) Nodes
    def do_nodes():
        r = requests.get(f"{BASE}/api/explore/nodes?spotId=srp-btn-bb-flop", headers=headers)
        assert r.status_code == 200
        nodes = r.json()
        assert len(nodes) >= 5
        print(f"    nodes: {len(nodes)}, root: {nodes[0]['id']}")

    check("GET /api/explore/nodes", do_nodes)

    # 4) Strategy
    def do_strategy():
        r = requests.get(f"{BASE}/api/explore/strategy?nodeId=srp-btn-bb-flop__root", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 169
        print(f"    hands: {len(data)}, AA: {data.get('AA', '?')}")

    check("GET /api/explore/strategy", do_strategy)

    # 5) Drill next
    question = None

    def do_drill_next():
        nonlocal question
        r = requests.post(f"{BASE}/api/drill/next", json={"spotId": "srp-btn-bb-flop"}, headers=headers)
        assert r.status_code == 200
        question = r.json()
        print(f"    hand: {question['hand']}, board: {question['board']}")

    check("POST /api/drill/next", do_drill_next)

    # 6) Drill answer
    def do_drill_answer():
        r = requests.post(f"{BASE}/api/drill/answer", json={
            "nodeId": question["nodeId"],
            "hand": question["hand"],
            "actionId": question["actions"][0]["id"],
            "questionId": question.get("questionId"),
        }, headers=headers)
        assert r.status_code == 200
        fb = r.json()
        print(f"    correct: {fb['correctAction']}, evLoss: {fb['evLoss']}, accuracy: {fb['accuracy']:.2f}")

    check("POST /api/drill/answer", do_drill_answer)

    # 7) Jobs
    def do_jobs():
        r = requests.get(f"{BASE}/api/jobs", headers=headers)
        assert r.status_code == 200
        print(f"    jobs: {len(r.json())}")

    check("GET /api/jobs", do_jobs)

    # 8) Analytics
    def do_analytics():
        r1 = requests.get(f"{BASE}/api/analytics/summary", headers=headers)
        assert r1.status_code == 200
        s = r1.json()
        print(f"    questions: {s['totalQuestions']}, sessions: {s['totalSessions']}, evLoss: {s['avgEvLoss']}")

        r2 = requests.get(f"{BASE}/api/analytics/history", headers=headers)
        assert r2.status_code == 200
        print(f"    history days: {len(r2.json())}")

        r3 = requests.get(f"{BASE}/api/analytics/recent", headers=headers)
        assert r3.status_code == 200
        print(f"    recent: {len(r3.json())}")

    check("Analytics (summary/history/recent)", do_analytics)

    # 9) Auth guard test
    def do_auth_guard():
        r = requests.get(f"{BASE}/api/spots")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        print(f"    no-token -> 401 ✓")

    check("Auth guard (401)", do_auth_guard)

    print(f"\n{'='*40}")
    if ok:
        print("ALL CHECKS PASSED ✓")
    else:
        print("SOME CHECKS FAILED ✗")
        sys.exit(1)


if __name__ == "__main__":
    smoke()
