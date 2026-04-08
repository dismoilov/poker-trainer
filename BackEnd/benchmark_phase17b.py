"""
Phase 17B: Convergence curve measurement for turn/river.
Measures actual convergence metric at various iteration counts to calibrate targets.
"""
import sys, time, json
sys.path.insert(0, '.')

import logging
logging.basicConfig(level=logging.WARNING)

from app.solver.cfr_solver import CfrSolver, SolveRequest

def solve_at_iters(board, ip, oop, inc_turn, inc_river, mtc, mrc, max_i, preset='standard'):
    """Run a solve with forced max_iterations (set user override to force full run)."""
    req = SolveRequest(
        board=board, ip_range=ip, oop_range=oop,
        pot=10.0, effective_stack=50.0,
        bet_sizes=[0.5, 1.0], raise_sizes=[], max_iterations=max_i,
        max_raises=0, deterministic=True,
        include_turn=inc_turn, max_turn_cards=mtc,
        turn_bet_sizes=[0.5,1.0], turn_raise_sizes=[], turn_max_raises=0,
        include_river=inc_river, max_river_cards=mrc,
        river_bet_sizes=[0.5,1.0], river_raise_sizes=[], river_max_raises=0,
    )
    req._preset = preset
    solver = CfrSolver()
    t0 = time.time()
    result = solver.solve(req, progress_callback=lambda info: None)
    return result.iterations, result.convergence_metric, result.stop_reason, time.time() - t0

# KEY SCENARIOS: measure convergence at 50, 75, 100, 150, 200, 300 iterations
scenarios = [
    ("Turn 3x3/3tc", ["Ks","7d","2c"], "AA,KK,QQ", "JJ,TT,99", True, False, 3, 0),
    ("Turn 6x6/3tc", ["As","Kd","7c"], "AA,KK,QQ,AKs,AKo,AQs", "JJ,TT,99,KQs,QJs,JTs", True, False, 3, 0),
    ("Turn 8x8/3tc", ["Qh","Jd","4c"], "AA,KK,QQ,JJ,TT,99,88,77", "AKs,AQs,AJs,ATs,KQs,KJs,KTs,QJs", True, False, 3, 0),
    ("River 2x2/2tc2rc", ["Ks","7d","2c"], "AA", "KK", True, True, 2, 2),
    ("River 3x3/2tc2rc", ["Ks","7d","2c"], "AA,KK,QQ", "JJ,TT,99", True, True, 2, 2),
    ("River 6x6/2tc2rc", ["As","Kd","7c"], "AA,KK,QQ,AKs,AKo,AQs", "JJ,TT,99,KQs,QJs,JTs", True, True, 2, 2),
]

iter_counts = [50, 75, 100, 150, 200, 300]

print("CONVERGENCE CURVE MEASUREMENT FOR TURN/RIVER")
print("=" * 100)

all_results = {}
for label, board, ip, oop, it, ir, mtc, mrc in scenarios:
    print(f"\n{label}:")
    curves = {}
    for max_i in iter_counts:
        iters, conv, stop, runtime = solve_at_iters(board, ip, oop, it, ir, mtc, mrc, max_i)
        curves[max_i] = {"iters": iters, "conv": conv, "stop": stop, "runtime": runtime}
        print(f"  {max_i:4d}i → actual={iters:4d}i, conv={conv:.4f}, stop={stop:15s}, {runtime:.2f}s")
    all_results[label] = curves

# Save for reference
with open("convergence_curves_17b.json", "w") as f:
    json.dump(all_results, f, indent=2)

print("\n\nSUMMARY: What convergence targets would differentiate presets?")
print("=" * 100)
for label, curves in all_results.items():
    vals = {k: v["conv"] for k, v in curves.items()}
    print(f"\n{label}:")
    print(f"  Conv at 50i: {vals.get(50, 'N/A'):.4f}")
    print(f"  Conv at 100i: {vals.get(100, 'N/A'):.4f}")
    print(f"  Conv at 200i: {vals.get(200, 'N/A'):.4f}")
    print(f"  Conv at 300i: {vals.get(300, 'N/A'):.4f}")
    # Suggest targets: fast should converge ~100i, standard ~200i, deep ~300i target
    if vals.get(50) and vals.get(100) and vals.get(200):
        print(f"  → FAST target should be ABOVE {vals[50]:.3f} (so it stops ~50-75i)")
        print(f"  → STANDARD target should be between {vals[200]:.3f} and {vals[100]:.3f} (so it stops ~100-150i)")
        print(f"  → DEEP target should be BELOW {vals[200]:.3f} (so it runs 200+ iterations)")

print("\nDone.")
