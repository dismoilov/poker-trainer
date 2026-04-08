"""
Phase 16A Benchmark: Compare fixed vs adaptive iteration behavior.
Runs 7 representative scenarios and reports results.
"""
import time
import sys
sys.path.insert(0, '.')

from app.solver.cfr_solver import CfrSolver, SolveRequest
from app.solver.solve_policy import SolveDifficulty, compute_iteration_budget, StopReason

SCENARIOS = [
    {
        "name": "1. Trivial flop (AA vs KK)",
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AA",
        "oop_range": "KK",
        "bet_sizes": [0.5],
        "raise_sizes": [],
        "max_raises": 0,
        "fixed_iters": 100,
        "preset": "standard",
    },
    {
        "name": "2. Light flop (3 hands each)",
        "board": ["Ts", "8h", "3c"],
        "ip_range": "AA,KK,QQ",
        "oop_range": "JJ,TT,99",
        "bet_sizes": [0.5, 1.0],
        "raise_sizes": [],
        "max_raises": 0,
        "fixed_iters": 100,
        "preset": "standard",
    },
    {
        "name": "3. Moderate flop (6 hands, raise)",
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AA,KK,QQ,AKs,AKo,AQs",
        "oop_range": "JJ,TT,99,AJs,KQs,QJs",
        "bet_sizes": [0.5, 1.0],
        "raise_sizes": [2.5],
        "max_raises": 1,
        "fixed_iters": 200,
        "preset": "standard",
    },
    {
        "name": "4. Turn (3 cards, standard)",
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AA,KK,QQ,AKs",
        "oop_range": "JJ,TT,99,AJs",
        "bet_sizes": [0.5, 1.0],
        "raise_sizes": [2.5],
        "max_raises": 1,
        "fixed_iters": 200,
        "preset": "standard",
        "include_turn": True,
        "max_turn_cards": 3,
    },
    {
        "name": "5. Heavy flop (15 hands each)",
        "board": ["Ah", "8d", "3c"],
        "ip_range": "AA,KK,QQ,JJ,TT,99,88,AKs,AQs,AJs,ATs,KQs,KJs,QJs,JTs",
        "oop_range": "77,66,55,44,33,22,A9s,A8s,A7s,A6s,A5s,KTs,K9s,Q9s,T9s",
        "bet_sizes": [0.5, 1.0],
        "raise_sizes": [],
        "max_raises": 0,
        "fixed_iters": 200,
        "preset": "standard",
    },
    {
        "name": "6. Deep (turn+river, 2tc 2rc)",
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AA,KK,QQ",
        "oop_range": "JJ,TT,99",
        "bet_sizes": [0.33, 0.5, 0.75, 1.0],
        "raise_sizes": [2.5],
        "max_raises": 2,
        "fixed_iters": 150,
        "preset": "deep",
        "include_turn": True,
        "max_turn_cards": 2,
        "include_river": True,
        "max_river_cards": 2,
    },
    {
        "name": "7. Fast preset (light)",
        "board": ["Ts", "8h", "3c"],
        "ip_range": "AA,KK",
        "oop_range": "QQ,JJ",
        "bet_sizes": [0.5, 1.0],
        "raise_sizes": [],
        "max_raises": 2,
        "fixed_iters": 100,
        "preset": "fast",
    },
]


def run_scenario(s):
    """Run one scenario and return metrics."""
    req = SolveRequest(
        board=s["board"],
        ip_range=s["ip_range"],
        oop_range=s["oop_range"],
        pot=10.0, effective_stack=50.0,
        bet_sizes=s["bet_sizes"],
        raise_sizes=s["raise_sizes"],
        max_iterations=s["fixed_iters"],
        max_raises=s["max_raises"],
        deterministic=True,
        include_turn=s.get("include_turn", False),
        max_turn_cards=s.get("max_turn_cards", 0),
        turn_bet_sizes=s.get("turn_bet_sizes", [0.5, 1.0]),
        turn_raise_sizes=s.get("turn_raise_sizes", []),
        turn_max_raises=s.get("turn_max_raises", 0),
        include_river=s.get("include_river", False),
        max_river_cards=s.get("max_river_cards", 0),
        river_bet_sizes=s.get("river_bet_sizes", [0.5, 1.0]),
        river_raise_sizes=s.get("river_raise_sizes", []),
        river_max_raises=s.get("river_max_raises", 0),
    )
    req._preset = s["preset"]

    solver = CfrSolver()
    progress_count = [0]
    def on_progress(info):
        progress_count[0] += 1

    start = time.time()
    result = solver.solve(req, progress_callback=on_progress)
    elapsed = time.time() - start

    return {
        "name": s["name"],
        "preset": s["preset"],
        "fixed_iters": s["fixed_iters"],
        "actual_iters": result.iterations,
        "convergence": result.convergence_metric,
        "exploit_mbb": result.exploitability_mbb,
        "elapsed": round(elapsed, 2),
        "stop_reason": result.stop_reason,
        "quality": result.metadata.get("solve_quality", {}).get("quality_class", "?"),
        "difficulty": result.metadata.get("difficulty_grade", "?"),
        "matchups": result.matchups,
        "tree_nodes": result.tree_nodes,
    }


if __name__ == "__main__":
    print("=" * 100)
    print("Phase 16A Benchmark: Fixed vs Adaptive Iteration Behavior")
    print("=" * 100)
    print()

    results = []
    for i, s in enumerate(SCENARIOS):
        print(f"Running {s['name']}...", flush=True)
        r = run_scenario(s)
        results.append(r)
        print(f"  → {r['actual_iters']}/{r['fixed_iters']} iters, "
              f"conv={r['convergence']:.6f}, exploit={r['exploit_mbb']:.1f} mbb/hand, "
              f"stop={r['stop_reason']}, quality={r['quality']}, "
              f"elapsed={r['elapsed']}s")
        print()

    print()
    print("=" * 100)
    print(f"{'Scenario':<40} {'Preset':<10} {'Fixed':>6} {'Actual':>7} {'Conv':>10} {'Exploit':>10} {'Time':>7} {'Stop':>15} {'Quality':>12} {'Grade':>10}")
    print("-" * 100)
    for r in results:
        print(f"{r['name']:<40} {r['preset']:<10} {r['fixed_iters']:>6} {r['actual_iters']:>7} "
              f"{r['convergence']:>10.6f} {r['exploit_mbb']:>10.1f} {r['elapsed']:>7.2f} "
              f"{r['stop_reason']:>15} {r['quality']:>12} {r['difficulty']:>10}")
    print("=" * 100)
