"""
Phase 15A: Serial Rust Scaling Audit — Practical Range Expansion Benchmarks.

Tests range combos from toy (AA vs KK) up to realistic bounded ranges
(pairs + broadways), measuring runtime, node counts, convergence, and
exploitability to classify each workload as safe/borderline/too-heavy.
"""
import time
import json
import sys
import os
import logging

logging.disable(logging.INFO)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from app.solver.cfr_solver import CfrSolver, SolveRequest, expand_range_to_combos, Card

def count_combos(range_str, board_strs):
    """Count combos for a range on a board."""
    board = [Card.parse(c) for c in board_strs]
    return len(expand_range_to_combos(range_str, board))

BOARD = ['Ks', '7d', '2c']
BOARD2 = ['Ts', '8h', '3c']

# Common realistic preflop range fragments
RANGES = {
    'tiny_pair': 'AA',                          # 6 combos (minus blockers)
    'two_pairs': 'AA,KK',                       # ~9 combos
    'three_pairs': 'AA,KK,QQ',                  # ~18 combos
    'six_pairs': 'AA,KK,QQ,JJ,TT,99',           # ~36 combos
    'broadway_suited': 'AKs,AQs,AJs,KQs',       # ~12 combos
    'broadway_mixed': 'AKs,AKo,AQs,KQs',        # ~22 combos
    'realistic_ip': 'AA,KK,QQ,AKs,AKo,AQs',    # ~40 combos
    'realistic_oop': 'JJ,TT,99,AJs,KQs,QJs',   # ~42 combos  
    'wide_ip': 'AA,KK,QQ,JJ,TT,AKs,AKo,AQs,AQo,AJs', # ~60 combos
    'wide_oop': '99,88,77,ATs,KQs,KQo,QJs,JTs',        # ~50 combos
    'very_wide': 'AA,KK,QQ,JJ,TT,99,88,AKs,AKo,AQs,AQo,AJs,AJo,ATs,KQs,KQo,KJs,QJs,JTs', # ~100+ combos
}

def print_range_sizes():
    """Print combo counts for reference."""
    print("Range combo counts on board Ks 7d 2c:")
    for name, rng in RANGES.items():
        n = count_combos(rng, BOARD)
        print(f"  {name}: {rng} → {n} combos")
    print()

SCENARIOS = [
    # ── FLOP SCENARIOS ──
    {"name": "F1_toy_pair_vs_pair", "board": BOARD,
     "ip": "AA", "oop": "KK", "street": "flop",
     "bet_sizes": [0.5, 1.0], "raise_sizes": [2.5], "max_raises": 2,
     "iters": 200, "turn_cfg": {}},
    
    {"name": "F2_three_pairs_vs_three", "board": BOARD,
     "ip": "AA,KK,QQ", "oop": "JJ,TT,99", "street": "flop",
     "bet_sizes": [0.5, 1.0], "raise_sizes": [2.5], "max_raises": 2,
     "iters": 200, "turn_cfg": {}},
    
    {"name": "F3_broadway_suited_vs_pairs", "board": BOARD2,
     "ip": "AKs,AQs,AJs,KQs", "oop": "JJ,TT,99", "street": "flop",
     "bet_sizes": [0.5, 1.0], "raise_sizes": [2.5], "max_raises": 1,
     "iters": 200, "turn_cfg": {}},
    
    {"name": "F4_realistic_IP_vs_OOP", "board": BOARD,
     "ip": "AA,KK,QQ,AKs,AKo,AQs", "oop": "JJ,TT,99,AJs,KQs,QJs", "street": "flop",
     "bet_sizes": [0.5, 1.0], "raise_sizes": [2.5], "max_raises": 1,
     "iters": 200, "turn_cfg": {}},
    
    {"name": "F5_wide_IP_vs_wide_OOP", "board": BOARD2,
     "ip": "AA,KK,QQ,JJ,TT,AKs,AKo,AQs,AQo,AJs",
     "oop": "99,88,77,ATs,KQs,KQo,QJs,JTs", "street": "flop",
     "bet_sizes": [0.5, 1.0], "raise_sizes": [], "max_raises": 0,
     "iters": 100, "turn_cfg": {}},
    
    # ── TURN SCENARIOS ──
    {"name": "T1_toy_pair_turn_3tc", "board": BOARD,
     "ip": "AA", "oop": "KK", "street": "turn",
     "bet_sizes": [0.5], "raise_sizes": [], "max_raises": 0,
     "iters": 200,
     "turn_cfg": {"max_turn_cards": 3, "turn_bet_sizes": [0.5],
                  "turn_raise_sizes": [], "turn_max_raises": 0}},

    {"name": "T2_realistic_3pairs_turn_3tc", "board": BOARD,
     "ip": "AA,KK,QQ", "oop": "JJ,TT,99", "street": "turn",
     "bet_sizes": [0.5], "raise_sizes": [], "max_raises": 0,
     "iters": 100,
     "turn_cfg": {"max_turn_cards": 3, "turn_bet_sizes": [0.5],
                  "turn_raise_sizes": [], "turn_max_raises": 0}},
    
    {"name": "T3_broadway_vs_pairs_turn_3tc", "board": BOARD2,
     "ip": "AKs,AQs,AJs,KQs", "oop": "JJ,TT,99", "street": "turn",
     "bet_sizes": [0.5], "raise_sizes": [], "max_raises": 0,
     "iters": 100,
     "turn_cfg": {"max_turn_cards": 3, "turn_bet_sizes": [0.5],
                  "turn_raise_sizes": [], "turn_max_raises": 0}},
    
    {"name": "T4_realistic_IP_OOP_turn_3tc", "board": BOARD,
     "ip": "AA,KK,QQ,AKs,AKo,AQs", "oop": "JJ,TT,99,AJs,KQs,QJs", "street": "turn",
     "bet_sizes": [0.5], "raise_sizes": [], "max_raises": 0,
     "iters": 50,
     "turn_cfg": {"max_turn_cards": 3, "turn_bet_sizes": [0.5],
                  "turn_raise_sizes": [], "turn_max_raises": 0}},
    
    {"name": "T5_wide_ranges_turn_2tc", "board": BOARD2,
     "ip": "AA,KK,QQ,JJ,TT,AKs,AKo,AQs",
     "oop": "99,88,77,ATs,KQs,KQo,QJs", "street": "turn",
     "bet_sizes": [0.5], "raise_sizes": [], "max_raises": 0,
     "iters": 50,
     "turn_cfg": {"max_turn_cards": 2, "turn_bet_sizes": [0.5],
                  "turn_raise_sizes": [], "turn_max_raises": 0}},

    # ── RIVER SCENARIOS ──
    {"name": "R1_toy_pair_river_2tc2rc", "board": BOARD,
     "ip": "AA", "oop": "KK", "street": "river",
     "bet_sizes": [0.5], "raise_sizes": [], "max_raises": 0,
     "iters": 200,
     "turn_cfg": {"max_turn_cards": 2, "turn_bet_sizes": [0.5],
                  "turn_raise_sizes": [], "turn_max_raises": 0,
                  "max_river_cards": 2, "river_bet_sizes": [0.5],
                  "river_raise_sizes": [], "river_max_raises": 0}},
    
    {"name": "R2_3pairs_river_2tc2rc", "board": BOARD,
     "ip": "AA,KK,QQ", "oop": "JJ,TT,99", "street": "river",
     "bet_sizes": [0.5], "raise_sizes": [], "max_raises": 0,
     "iters": 50,
     "turn_cfg": {"max_turn_cards": 2, "turn_bet_sizes": [0.5],
                  "turn_raise_sizes": [], "turn_max_raises": 0,
                  "max_river_cards": 2, "river_bet_sizes": [0.5],
                  "river_raise_sizes": [], "river_max_raises": 0}},
    
    {"name": "R3_broadway_vs_pairs_river_2tc1rc", "board": BOARD2,
     "ip": "AKs,AQs,AJs", "oop": "JJ,TT,99", "street": "river",
     "bet_sizes": [0.5], "raise_sizes": [], "max_raises": 0,
     "iters": 50,
     "turn_cfg": {"max_turn_cards": 2, "turn_bet_sizes": [0.5],
                  "turn_raise_sizes": [], "turn_max_raises": 0,
                  "max_river_cards": 1, "river_bet_sizes": [0.5],
                  "river_raise_sizes": [], "river_max_raises": 0}},
    
    {"name": "R4_realistic_IP_OOP_river_2tc1rc", "board": BOARD,
     "ip": "AA,KK,QQ,AKs", "oop": "JJ,TT,AJs,KQs", "street": "river",
     "bet_sizes": [0.5], "raise_sizes": [], "max_raises": 0,
     "iters": 50,
     "turn_cfg": {"max_turn_cards": 2, "turn_bet_sizes": [0.5],
                  "turn_raise_sizes": [], "turn_max_raises": 0,
                  "max_river_cards": 1, "river_bet_sizes": [0.5],
                  "river_raise_sizes": [], "river_max_raises": 0}},
]


def run_scenario(s):
    """Run a single scenario and return metrics."""
    solver = CfrSolver()
    kw = dict(
        board=s["board"], ip_range=s["ip"], oop_range=s["oop"],
        pot=10.0, effective_stack=50.0,
        bet_sizes=s["bet_sizes"], raise_sizes=s["raise_sizes"],
        max_iterations=s["iters"], max_raises=s["max_raises"],
        deterministic=True,
    )
    tc = s["turn_cfg"]
    if s["street"] in ("turn", "river"):
        kw["include_turn"] = True
        kw.update({k: tc[k] for k in ["max_turn_cards", "turn_bet_sizes",
                                        "turn_raise_sizes", "turn_max_raises"]})
    if s["street"] == "river":
        kw["include_river"] = True
        kw.update({k: tc[k] for k in ["max_river_cards", "river_bet_sizes",
                                        "river_raise_sizes", "river_max_raises"]})
    
    ip_n = count_combos(s["ip"], s["board"])
    oop_n = count_combos(s["oop"], s["board"])
    
    t0 = time.time()
    try:
        output = solver.solve(SolveRequest(**kw))
        elapsed = time.time() - t0
        return {
            "name": s["name"],
            "ip_combos": ip_n, "oop_combos": oop_n,
            "matchups": ip_n * oop_n,
            "street": s["street"], "iters": s["iters"],
            "time": elapsed,
            "nodes": output.tree_nodes,
            "convergence": output.convergence_metric,
            "exploitability": output.exploitability_mbb,
            "ok": True,
            "error": None,
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "name": s["name"],
            "ip_combos": ip_n, "oop_combos": oop_n,
            "matchups": ip_n * oop_n,
            "street": s["street"], "iters": s["iters"],
            "time": elapsed, "nodes": 0,
            "convergence": 0, "exploitability": 0,
            "ok": False, "error": str(e),
        }


def classify(result):
    """Classify a result as safe/borderline/too-heavy."""
    if not result["ok"]:
        return "REJECTED"
    t = result["time"]
    if t < 5.0:
        return "SAFE"
    elif t < 30.0:
        return "BORDERLINE"
    else:
        return "TOO HEAVY"


if __name__ == "__main__":
    print("Phase 15A: Serial Rust Scaling Audit")
    print(f"CPU cores: {os.cpu_count()}")
    print()
    print_range_sizes()
    
    results = []
    for i, s in enumerate(SCENARIOS):
        ip_n = count_combos(s["ip"], s["board"])
        oop_n = count_combos(s["oop"], s["board"])
        print(f"[{i+1}/{len(SCENARIOS)}] {s['name']} ({s['street']}, {ip_n}×{oop_n}={ip_n*oop_n} matchups, {s['iters']}i)", end="", flush=True)
        r = run_scenario(s)
        cl = classify(r)
        results.append({**r, "class": cl})
        
        if r["ok"]:
            print(f" → {r['time']:.3f}s, {r['nodes']} nodes, conv={r['convergence']:.4f}, expl={r['exploitability']:.0f}mbb → [{cl}]")
        else:
            print(f" → FAILED: {r['error'][:80]}")
    
    # Print table
    print("\n" + "="*180)
    print("SCALING AUDIT RESULTS")
    print("="*180)
    hdr = f"{'Scenario':<38} {'Street':<8} {'IP':<5} {'OOP':<5} {'Match':<6} {'Iter':<5} {'Time(s)':<9} {'Nodes':<7} {'Conv':<9} {'Expl(mbb)':<10} {'Class':<12}"
    print(hdr)
    print("-"*180)
    for r in results:
        if r["ok"]:
            print(f"{r['name']:<38} {r['street']:<8} {r['ip_combos']:<5} {r['oop_combos']:<5} {r['matchups']:<6} {r['iters']:<5} {r['time']:<9.3f} {r['nodes']:<7} {r['convergence']:<9.4f} {r['exploitability']:<10.0f} {r['class']:<12}")
        else:
            print(f"{r['name']:<38} {r['street']:<8} {r['ip_combos']:<5} {r['oop_combos']:<5} {r['matchups']:<6} {r['iters']:<5} {'FAIL':<9} {'-':<7} {'-':<9} {'-':<10} {'REJECTED':<12}")
    print("="*180)
    
    out_path = os.path.join(os.path.dirname(__file__), "scaling_phase15a_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults → {out_path}")
