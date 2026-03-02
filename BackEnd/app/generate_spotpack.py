"""Generate expanded spotpack.json with 20+ spots covering all common 6-max cash scenarios."""

import json


def make_node(spot_id, node_num, street, pot, player, actions, parent_id, line_desc, children, action_label):
    nid = f"{spot_id}__{'root' if parent_id is None else f'node-{node_num}'}"
    return {
        "id": nid,
        "spotId": spot_id,
        "street": street,
        "pot": pot,
        "player": player,
        "actions": actions,
        "parentId": parent_id,
        "lineDescription": line_desc,
        "children": children,
        "actionLabel": action_label,
    }


# Standard action sets
CHECK_BET = [
    {"id": "check", "label": "Check", "type": "check"},
    {"id": "bet33", "label": "Bet 33%", "type": "bet", "size": 33},
    {"id": "bet75", "label": "Bet 75%", "type": "bet", "size": 75},
]

FOLD_CALL_RAISE = [
    {"id": "fold", "label": "Fold", "type": "fold"},
    {"id": "call", "label": "Call", "type": "call"},
    {"id": "raise", "label": "Raise 2.5x", "type": "raise", "size": 2.5},
]

# Turn/River specific sizings
CHECK_BET_TURN = [
    {"id": "check", "label": "Check", "type": "check"},
    {"id": "bet50", "label": "Bet 50%", "type": "bet", "size": 50},
    {"id": "bet75", "label": "Bet 75%", "type": "bet", "size": 75},
]

CHECK_BET_RIVER = [
    {"id": "check", "label": "Check", "type": "check"},
    {"id": "bet50", "label": "Bet 50%", "type": "bet", "size": 50},
    {"id": "bet75", "label": "Bet 75%", "type": "bet", "size": 75},
    {"id": "bet150", "label": "Bet 150%", "type": "bet", "size": 150},
]

FOLD_CALL_RAISE_TURN = [
    {"id": "fold", "label": "Fold", "type": "fold"},
    {"id": "call", "label": "Call", "type": "call"},
    {"id": "raise", "label": "Raise 2.5x", "type": "raise", "size": 2.5},
]


def make_srp_flop_spot(pos_ip, pos_oop, spot_id, pot=6.5):
    """Create an SRP flop spot with standard game tree."""
    nodes = []
    root_id = f"{spot_id}__root"
    n2 = f"{spot_id}__node-2"
    n3 = f"{spot_id}__node-3"
    n4 = f"{spot_id}__node-4"
    n5 = f"{spot_id}__node-5"
    n6 = f"{spot_id}__node-6"

    bet33_pot = round(pot + pot * 0.33, 1)
    bet75_pot = round(pot + pot * 0.75, 1)

    # Root: OOP first to act
    nodes.append(make_node(spot_id, 0, "flop", pot, pos_oop, CHECK_BET, None,
                           f"{pos_ip} open 2.5bb → {pos_oop} call", [n2, n5, n6], "Root"))
    # Node 2: OOP checks → IP acts
    nodes.append(make_node(spot_id, 2, "flop", pot, pos_ip, CHECK_BET, root_id,
                           f"{pos_ip} open → {pos_oop} call → {pos_oop} check", [n3, n4], f"{pos_oop} Check"))
    # Node 3: OOP check → IP bet 33% → OOP responds
    nodes.append(make_node(spot_id, 3, "flop", bet33_pot, pos_oop, FOLD_CALL_RAISE, n2,
                           f"{pos_oop} check → {pos_ip} bet 33%", [], f"{pos_ip} Bet 33%"))
    # Node 4: OOP check → IP bet 75% → OOP responds
    nodes.append(make_node(spot_id, 4, "flop", bet75_pot, pos_oop, FOLD_CALL_RAISE, n2,
                           f"{pos_oop} check → {pos_ip} bet 75%", [], f"{pos_ip} Bet 75%"))
    # Node 5: OOP bet 33% → IP responds
    nodes.append(make_node(spot_id, 5, "flop", bet33_pot, pos_ip, FOLD_CALL_RAISE, root_id,
                           f"{pos_oop} bet 33%", [], f"{pos_oop} Bet 33%"))
    # Node 6: OOP bet 75% → IP responds
    nodes.append(make_node(spot_id, 6, "flop", bet75_pot, pos_ip, FOLD_CALL_RAISE, root_id,
                           f"{pos_oop} bet 75%", [], f"{pos_oop} Bet 75%"))

    return nodes


def make_3bet_flop_spot(pos_ip, pos_oop, spot_id, pot=13.5):
    """Create a 3bet pot flop spot."""
    nodes = []
    root_id = f"{spot_id}__root"
    n2 = f"{spot_id}__node-2"
    n3 = f"{spot_id}__node-3"
    n4 = f"{spot_id}__node-4"
    n5 = f"{spot_id}__node-5"
    n6 = f"{spot_id}__node-6"

    bet33_pot = round(pot + pot * 0.33, 1)
    bet75_pot = round(pot + pot * 0.75, 1)

    nodes.append(make_node(spot_id, 0, "flop", pot, pos_oop, CHECK_BET, None,
                           f"{pos_ip} open → {pos_oop} 3bet → {pos_ip} call", [n2, n5, n6], "Root"))
    nodes.append(make_node(spot_id, 2, "flop", pot, pos_ip, CHECK_BET, root_id,
                           f"{pos_oop} 3bet → {pos_ip} call → {pos_oop} check", [n3, n4], f"{pos_oop} Check"))
    nodes.append(make_node(spot_id, 3, "flop", bet33_pot, pos_oop, FOLD_CALL_RAISE, n2,
                           f"{pos_oop} check → {pos_ip} bet 33%", [], f"{pos_ip} Bet 33%"))
    nodes.append(make_node(spot_id, 4, "flop", bet75_pot, pos_oop, FOLD_CALL_RAISE, n2,
                           f"{pos_oop} check → {pos_ip} bet 75%", [], f"{pos_ip} Bet 75%"))
    nodes.append(make_node(spot_id, 5, "flop", bet33_pot, pos_ip, FOLD_CALL_RAISE, root_id,
                           f"{pos_oop} bet 33%", [], f"{pos_oop} Bet 33%"))
    nodes.append(make_node(spot_id, 6, "flop", bet75_pot, pos_ip, FOLD_CALL_RAISE, root_id,
                           f"{pos_oop} bet 75%", [], f"{pos_oop} Bet 75%"))

    return nodes


def make_squeeze_flop_spot(pos_squeezer, pos_opener, spot_id, pot=20.0):
    """Create a squeeze pot flop spot.
    Squeeze = 3bet after open + cold call, caller folds, heads-up postflop.
    Squeezer is OOP (typically BB/SB), opener is IP.
    """
    nodes = []
    root_id = f"{spot_id}__root"
    n2 = f"{spot_id}__node-2"
    n3 = f"{spot_id}__node-3"
    n4 = f"{spot_id}__node-4"
    n5 = f"{spot_id}__node-5"
    n6 = f"{spot_id}__node-6"

    bet33_pot = round(pot + pot * 0.33, 1)
    bet75_pot = round(pot + pot * 0.75, 1)

    nodes.append(make_node(spot_id, 0, "flop", pot, pos_squeezer, CHECK_BET, None,
                           f"{pos_opener} open → cold call → {pos_squeezer} squeeze → {pos_opener} call",
                           [n2, n5, n6], "Root"))
    nodes.append(make_node(spot_id, 2, "flop", pot, pos_opener, CHECK_BET, root_id,
                           f"Squeeze pot → {pos_squeezer} check",
                           [n3, n4], f"{pos_squeezer} Check"))
    nodes.append(make_node(spot_id, 3, "flop", bet33_pot, pos_squeezer, FOLD_CALL_RAISE, n2,
                           f"{pos_squeezer} check → {pos_opener} bet 33%", [], f"{pos_opener} Bet 33%"))
    nodes.append(make_node(spot_id, 4, "flop", bet75_pot, pos_squeezer, FOLD_CALL_RAISE, n2,
                           f"{pos_squeezer} check → {pos_opener} bet 75%", [], f"{pos_opener} Bet 75%"))
    nodes.append(make_node(spot_id, 5, "flop", bet33_pot, pos_opener, FOLD_CALL_RAISE, root_id,
                           f"{pos_squeezer} bet 33%", [], f"{pos_squeezer} Bet 33%"))
    nodes.append(make_node(spot_id, 6, "flop", bet75_pot, pos_opener, FOLD_CALL_RAISE, root_id,
                           f"{pos_squeezer} bet 75%", [], f"{pos_squeezer} Bet 75%"))

    return nodes


def make_turn_spot(pos_ip, pos_oop, spot_id, pot=12.0, line_prefix=""):
    """Create a turn spot (after flop action)."""
    nodes = []
    root_id = f"{spot_id}__root"
    n2 = f"{spot_id}__node-2"
    n3 = f"{spot_id}__node-3"
    n4 = f"{spot_id}__node-4"
    n5 = f"{spot_id}__node-5"
    n6 = f"{spot_id}__node-6"

    bet50_pot = round(pot + pot * 0.50, 1)
    bet75_pot = round(pot + pot * 0.75, 1)

    line = f"{line_prefix} → turn" if line_prefix else f"{pos_ip} open → {pos_oop} call → flop check-check → turn"

    nodes.append(make_node(spot_id, 0, "turn", pot, pos_oop, CHECK_BET_TURN, None,
                           line, [n2, n5, n6], "Root"))
    nodes.append(make_node(spot_id, 2, "turn", pot, pos_ip, CHECK_BET_TURN, root_id,
                           f"Turn → {pos_oop} check", [n3, n4], f"{pos_oop} Check"))
    nodes.append(make_node(spot_id, 3, "turn", bet50_pot, pos_oop, FOLD_CALL_RAISE_TURN, n2,
                           f"{pos_oop} check → {pos_ip} bet 50%", [], f"{pos_ip} Bet 50%"))
    nodes.append(make_node(spot_id, 4, "turn", bet75_pot, pos_oop, FOLD_CALL_RAISE_TURN, n2,
                           f"{pos_oop} check → {pos_ip} bet 75%", [], f"{pos_ip} Bet 75%"))
    nodes.append(make_node(spot_id, 5, "turn", bet50_pot, pos_ip, FOLD_CALL_RAISE_TURN, root_id,
                           f"{pos_oop} bet 50%", [], f"{pos_oop} Bet 50%"))
    nodes.append(make_node(spot_id, 6, "turn", bet75_pot, pos_ip, FOLD_CALL_RAISE_TURN, root_id,
                           f"{pos_oop} bet 75%", [], f"{pos_oop} Bet 75%"))

    return nodes


def make_river_spot(pos_ip, pos_oop, spot_id, pot=24.0, line_prefix=""):
    """Create a river spot."""
    nodes = []
    root_id = f"{spot_id}__root"
    n2 = f"{spot_id}__node-2"
    n3 = f"{spot_id}__node-3"
    n4 = f"{spot_id}__node-4"
    n5 = f"{spot_id}__node-5"

    bet75_pot = round(pot + pot * 0.75, 1)
    bet150_pot = round(pot + pot * 1.50, 1)

    line = f"{line_prefix} → river" if line_prefix else f"River after bet-call on earlier streets"

    nodes.append(make_node(spot_id, 0, "river", pot, pos_oop,
                           [{"id": "check", "label": "Check", "type": "check"},
                            {"id": "bet75", "label": "Bet 75%", "type": "bet", "size": 75},
                            {"id": "bet150", "label": "Bet 150%", "type": "bet", "size": 150}],
                           None, line, [n2, n3, n4], "Root"))
    nodes.append(make_node(spot_id, 2, "river", pot, pos_ip,
                           [{"id": "check", "label": "Check", "type": "check"},
                            {"id": "bet75", "label": "Bet 75%", "type": "bet", "size": 75},
                            {"id": "bet150", "label": "Bet 150%", "type": "bet", "size": 150}],
                           root_id, f"River → {pos_oop} check", [n5], f"{pos_oop} Check"))
    nodes.append(make_node(spot_id, 3, "river", bet75_pot, pos_ip,
                           FOLD_CALL_RAISE_TURN,
                           root_id, f"{pos_oop} bet 75%", [], f"{pos_oop} Bet 75%"))
    nodes.append(make_node(spot_id, 4, "river", bet150_pot, pos_ip,
                           FOLD_CALL_RAISE_TURN,
                           root_id, f"{pos_oop} bet 150% (overbet)", [], f"{pos_oop} Bet 150%"))
    nodes.append(make_node(spot_id, 5, "river", bet75_pot, pos_oop,
                           FOLD_CALL_RAISE_TURN,
                           n2, f"{pos_oop} check → {pos_ip} bet 75%", [], f"{pos_ip} Bet 75%"))

    return nodes


def generate():
    spots = []
    all_nodes = []

    # ═════════════════════════════════════════════════
    # SRP FLOP SPOTS (8 spots × 6 nodes = 48 nodes)
    # ═════════════════════════════════════════════════

    srp_flop_configs = [
        ("BTN", "BB", "srp-btn-bb-flop", "SRP BTN vs BB Flop", 6.5),
        ("CO", "BB", "srp-co-bb-flop", "SRP CO vs BB Flop", 6.0),
        ("MP", "BB", "srp-mp-bb-flop", "SRP MP vs BB Flop", 6.0),
        ("SB", "BB", "srp-sb-bb-flop", "SRP SB vs BB Flop", 6.0),
        ("BTN", "SB", "srp-btn-sb-flop", "SRP BTN vs SB Flop", 6.0),
        ("CO", "SB", "srp-co-sb-flop", "SRP CO vs SB Flop", 6.0),
        ("UTG", "BB", "srp-utg-bb-flop", "SRP UTG vs BB Flop", 6.0),
        ("BTN", "CO", "srp-btn-co-flop", "SRP BTN vs CO Flop", 6.5),
        # New spots
        ("HJ", "BB", "srp-hj-bb-flop", "SRP HJ vs BB Flop", 6.0),
        ("UTG", "SB", "srp-utg-sb-flop", "SRP UTG vs SB Flop", 6.0),
        ("MP", "SB", "srp-mp-sb-flop", "SRP MP vs SB Flop", 6.0),
        ("HJ", "CO", "srp-hj-co-flop", "SRP HJ vs CO Flop", 6.0),
        ("CO", "BTN", "srp-co-btn-flop", "SRP CO vs BTN Flop", 6.5),
    ]

    for ip, oop, sid, name, pot in srp_flop_configs:
        nodes = make_srp_flop_spot(ip, oop, sid, pot)
        spots.append({
            "id": sid, "name": name, "format": "SRP",
            "positions": [ip, oop], "stack": 100, "rakeProfile": "low",
            "streets": ["flop"],
            "tags": ["SRP", "flop", "IP" if ip in ("BTN", "CO") else "OOP"],
            "solved": True, "nodeCount": len(nodes),
        })
        all_nodes.extend(nodes)

    # ═════════════════════════════════════════════════
    # 3BET FLOP SPOTS (10 spots)
    # ═════════════════════════════════════════════════

    threebet_configs = [
        ("BTN", "BB", "3bet-btn-bb-flop", "3Bet BTN vs BB Flop", 13.5),
        ("CO", "BB", "3bet-co-bb-flop", "3Bet CO vs BB Flop", 13.5),
        ("BTN", "SB", "3bet-btn-sb-flop", "3Bet BTN vs SB Flop", 14.0),
        ("SB", "BTN", "3bet-sb-btn-flop", "3Bet SB vs BTN Flop", 13.0),
        ("BB", "CO", "3bet-bb-co-flop", "3Bet BB vs CO Flop", 13.5),
        # New spots
        ("UTG", "BB", "3bet-utg-bb-flop", "3Bet UTG vs BB Flop", 14.0),
        ("HJ", "BB", "3bet-hj-bb-flop", "3Bet HJ vs BB Flop", 13.5),
        ("CO", "BTN", "3bet-co-btn-flop", "3Bet CO vs BTN Flop", 13.5),
        ("MP", "BB", "3bet-mp-bb-flop", "3Bet MP vs BB Flop", 14.0),
        ("SB", "CO", "3bet-sb-co-flop", "3Bet SB vs CO Flop", 13.0),
    ]

    for ip, oop, sid, name, pot in threebet_configs:
        nodes = make_3bet_flop_spot(ip, oop, sid, pot)
        spots.append({
            "id": sid, "name": name, "format": "3bet",
            "positions": [ip, oop], "stack": 100, "rakeProfile": "low",
            "streets": ["flop"],
            "tags": ["3bet", "flop"],
            "solved": True, "nodeCount": len(nodes),
        })
        all_nodes.extend(nodes)

    # ═════════════════════════════════════════════════
    # 4BET FLOP SPOTS (4 spots)
    # ═════════════════════════════════════════════════

    fourbet_configs = [
        ("BTN", "BB", "4bet-btn-bb-flop", "4Bet BTN vs BB Flop", 25.0),
        ("CO", "BB", "4bet-co-bb-flop", "4Bet CO vs BB Flop", 25.0),
        ("SB", "BTN", "4bet-sb-btn-flop", "4Bet SB vs BTN Flop", 24.0),
        ("UTG", "BB", "4bet-utg-bb-flop", "4Bet UTG vs BB Flop", 26.0),
    ]

    for ip, oop, sid, name, pot in fourbet_configs:
        nodes = make_srp_flop_spot(ip, oop, sid, pot)
        spots.append({
            "id": sid, "name": name, "format": "4bet",
            "positions": [ip, oop], "stack": 100, "rakeProfile": "low",
            "streets": ["flop"],
            "tags": ["4bet", "flop"],
            "solved": True, "nodeCount": len(nodes),
        })
        all_nodes.extend(nodes)

    # ═════════════════════════════════════════════════
    # SQUEEZE FLOP SPOTS (3 spots)
    # ═════════════════════════════════════════════════

    squeeze_configs = [
        ("BB", "CO", "sqz-bb-co-flop", "Squeeze BB vs CO Flop", 20.0),
        ("SB", "BTN", "sqz-sb-btn-flop", "Squeeze SB vs BTN Flop", 19.0),
        ("BB", "BTN", "sqz-bb-btn-flop", "Squeeze BB vs BTN Flop", 20.0),
    ]

    for squeezer, opener, sid, name, pot in squeeze_configs:
        nodes = make_squeeze_flop_spot(squeezer, opener, sid, pot)
        spots.append({
            "id": sid, "name": name, "format": "squeeze",
            "positions": [squeezer, opener], "stack": 100, "rakeProfile": "low",
            "streets": ["flop"],
            "tags": ["squeeze", "flop"],
            "solved": True, "nodeCount": len(nodes),
        })
        all_nodes.extend(nodes)

    # ═════════════════════════════════════════════════
    # TURN SPOTS (8 spots)
    # ═════════════════════════════════════════════════

    turn_configs = [
        ("BTN", "BB", "srp-btn-bb-turn-cc", "SRP BTN vs BB Turn (check-check)", 6.5,
         "BTN open → BB call → flop check-check"),
        ("BTN", "BB", "srp-btn-bb-turn-bc", "SRP BTN vs BB Turn (bet-call)", 12.0,
         "BTN open → BB call → BTN bet → BB call"),
        ("CO", "BB", "srp-co-bb-turn", "SRP CO vs BB Turn", 12.0,
         "CO open → BB call → flop bet-call"),
        ("BTN", "BB", "3bet-btn-bb-turn", "3Bet BTN vs BB Turn", 24.0,
         "BTN open → BB 3bet → BTN call → flop bet-call"),
        # New spots
        ("SB", "BB", "srp-sb-bb-turn-cc", "SRP SB vs BB Turn (check-check)", 6.0,
         "SB open → BB call → flop check-check"),
        ("CO", "BB", "3bet-co-bb-turn", "3Bet CO vs BB Turn", 24.0,
         "CO open → BB 3bet → CO call → flop bet-call"),
        ("HJ", "BB", "srp-hj-bb-turn-bc", "SRP HJ vs BB Turn (bet-call)", 12.0,
         "HJ open → BB call → HJ bet → BB call"),
        ("BTN", "SB", "srp-btn-sb-turn-bc", "SRP BTN vs SB Turn (bet-call)", 12.0,
         "BTN open → SB call → BTN bet → SB call"),
    ]

    for ip, oop, sid, name, pot, line in turn_configs:
        nodes = make_turn_spot(ip, oop, sid, pot, line)
        street_list = ["flop", "turn"]
        fmt = "3bet" if "3bet" in sid else "SRP"
        spots.append({
            "id": sid, "name": name, "format": fmt,
            "positions": [ip, oop], "stack": 100, "rakeProfile": "low",
            "streets": street_list,
            "tags": [fmt, "turn"],
            "solved": True, "nodeCount": len(nodes),
        })
        all_nodes.extend(nodes)

    # ═════════════════════════════════════════════════
    # RIVER SPOTS (5 spots)
    # ═════════════════════════════════════════════════

    river_configs = [
        ("BTN", "BB", "srp-btn-bb-river", "SRP BTN vs BB River", 24.0,
         "BTN open → Multiple streets → bet-call"),
        ("BTN", "BB", "3bet-btn-bb-river", "3Bet BTN vs BB River", 40.0,
         "3bet pot → Multiple streets → bet-call"),
        # New spots
        ("CO", "BB", "srp-co-bb-river", "SRP CO vs BB River", 24.0,
         "CO open → Multiple streets → bet-call"),
        ("SB", "BB", "3bet-sb-bb-river", "3Bet SB vs BB River", 38.0,
         "SB 3bet → Multiple streets → bet-call"),
        ("BTN", "SB", "srp-btn-sb-river", "SRP BTN vs SB River", 22.0,
         "BTN open → SB call → Multiple streets → bet-call"),
    ]

    for ip, oop, sid, name, pot, line in river_configs:
        nodes = make_river_spot(ip, oop, sid, pot, line)
        fmt = "3bet" if "3bet" in sid else "SRP"
        spots.append({
            "id": sid, "name": name, "format": fmt,
            "positions": [ip, oop], "stack": 100, "rakeProfile": "low",
            "streets": ["flop", "turn", "river"],
            "tags": [fmt, "river"],
            "solved": True, "nodeCount": len(nodes),
        })
        all_nodes.extend(nodes)

    data = {"spots": spots, "nodes": all_nodes}
    return data


if __name__ == "__main__":
    import os
    data = generate()
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "spotpack.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Generated {len(data['spots'])} spots and {len(data['nodes'])} nodes")
