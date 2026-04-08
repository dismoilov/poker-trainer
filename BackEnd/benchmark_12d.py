"""
Phase 12D: Baseline benchmarks BEFORE NumPy migration.
Run from BackEnd directory.
"""
import time
import json
import sys
sys.path.insert(0, '.')

from app.solver.cfr_solver import CfrSolver, SolveRequest

SCENARIOS = [
    {
        "name": "1. Flop narrow (AA vs KK)",
        "request": dict(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ),
    },
    {
        "name": "2. Flop broad (4-hand vs 4-hand)",
        "request": dict(
            board=["Ks", "7d", "2c"], ip_range="AA,KK,QQ,AKs", oop_range="JJ,TT,99,AQs",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ),
    },
    {
        "name": "3. Turn (AA vs KK, 2 turn cards)",
        "request": dict(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ),
    },
    {
        "name": "4. River (AA vs KK, 1 turn, 1 river)",
        "request": dict(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            include_river=True, max_river_cards=1,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ),
    },
    {
        "name": "5. Flop 3-bet sizes + raise (AA,KK vs QQ,JJ)",
        "request": dict(
            board=["9s", "7d", "2c"], ip_range="AA,KK", oop_range="QQ,JJ",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.33, 0.5, 1.0], raise_sizes=[2.5],
            max_iterations=50, deterministic=True,
        ),
    },
]

results = []

for scenario in SCENARIOS:
    name = scenario["name"]
    req = SolveRequest(**scenario["request"])
    
    solver = CfrSolver()
    start = time.time()
    output = solver.solve(req)
    elapsed = time.time() - start
    
    # Check strategies sum to 1
    strat_ok = True
    for nid, combos in output.strategies.items():
        for c, freqs in combos.items():
            s = sum(freqs.values())
            if abs(s - 1.0) > 0.01:
                strat_ok = False
    
    info_sets = len(solver._info_set_map) if hasattr(solver, '_info_set_map') else 0
    
    result = {
        "name": name,
        "runtime_s": round(elapsed, 3),
        "iterations": output.iterations,
        "convergence": round(output.convergence_metric, 6),
        "exploitability_mbb": round(output.exploitability_mbb, 2),
        "tree_nodes": output.tree_nodes,
        "matchups": output.matchups,
        "info_sets": info_sets,
        "strategies_ok": strat_ok,
    }
    results.append(result)
    print(f"{name}: {elapsed:.3f}s, conv={output.convergence_metric:.6f}, "
          f"exploit={output.exploitability_mbb:.2f}, nodes={output.tree_nodes}, "
          f"matchups={output.matchups}, info_sets={info_sets}, strat_ok={strat_ok}")

print("\n=== BASELINE RESULTS (JSON) ===")
print(json.dumps(results, indent=2))
