"""
Phase 17: Practical Scaling Validation Benchmark.

Runs 15+ realistic scenarios across flop/turn/river with varying
range widths and presets to map the real operating envelope.
"""
import json
import logging
import sys
import time
import traceback

sys.path.insert(0, '.')

from app.solver.cfr_solver import CfrSolver, SolveRequest
from app.solver.rust_bridge import RUST_AVAILABLE, RUST_VERSION
from app.solver.solve_policy import SolveDifficulty

logging.basicConfig(level=logging.WARNING, format='%(name)s: %(message)s')

# Scenarios: (id, label, board, ip_range, oop_range, include_turn, include_river,
#             max_turn_cards, max_river_cards, preset, max_iterations)
SCENARIOS = [
    # ── Flop workloads ──
    ("F1", "Flop trivial: AA vs KK",
     ["Ks", "7d", "2c"], "AA", "KK",
     False, False, 0, 0, "standard", 200),

    ("F2", "Flop light: 3 pairs vs 3 pairs",
     ["Ks", "7d", "2c"], "AA,KK,QQ", "JJ,TT,99",
     False, False, 0, 0, "standard", 200),

    ("F3", "Flop moderate: 6 hands vs 6 hands",
     ["As", "Kd", "7c"], "AA,KK,QQ,AKs,AKo,AQs", "JJ,TT,99,KQs,QJs,JTs",
     False, False, 0, 0, "standard", 200),

    ("F4", "Flop heavy: pairs+broadways wide",
     ["Qh", "Jd", "4c"], "AA,KK,QQ,JJ,TT,99,88,77,66,55", "AKs,AQs,AJs,ATs,KQs,KJs,KTs,QJs,QTs,JTs",
     False, False, 0, 0, "standard", 200),

    ("F5", "Flop extreme: full broadway+pairs",
     ["Td", "8s", "3c"], "AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKs,AQs,AJs,ATs",
     "AKo,AQo,AJo,ATo,KQs,KJs,KTs,QJs,QTs,JTs,KQo,KJo,KTo,QJo,QTo,JTo",
     False, False, 0, 0, "standard", 200),

    # ── Turn workloads ──
    ("T1", "Turn light: AA vs KK, 3tc",
     ["Ks", "7d", "2c"], "AA", "KK",
     True, False, 3, 0, "standard", 200),

    ("T2", "Turn moderate: 3 pairs vs 3 pairs, 3tc",
     ["Ks", "7d", "2c"], "AA,KK,QQ", "JJ,TT,99",
     True, False, 3, 0, "standard", 200),

    ("T3", "Turn moderate: 3×3, 5tc",
     ["As", "Kd", "7c"], "AA,KK,QQ", "JJ,TT,99",
     True, False, 5, 0, "standard", 200),

    ("T4", "Turn heavy: 6×6, 3tc",
     ["As", "Kd", "7c"], "AA,KK,QQ,AKs,AKo,AQs", "JJ,TT,99,KQs,QJs,JTs",
     True, False, 3, 0, "standard", 200),

    ("T5", "Turn heavy: pairs wide, 3tc",
     ["Qh", "Jd", "4c"], "AA,KK,QQ,JJ,TT,99,88,77", "AKs,AQs,AJs,ATs,KQs,KJs,KTs,QJs",
     True, False, 3, 0, "standard", 200),

    ("T6", "Turn extreme: 10×10, 5tc",
     ["Qh", "Jd", "4c"], "AA,KK,QQ,JJ,TT,99,88,77,66,55",
     "AKs,AQs,AJs,ATs,KQs,KJs,KTs,QJs,QTs,JTs",
     True, False, 5, 0, "standard", 200),

    # ── River workloads ──
    ("R1", "River light: AA vs KK, 2tc 2rc",
     ["Ks", "7d", "2c"], "AA", "KK",
     True, True, 2, 2, "standard", 200),

    ("R2", "River moderate: 3×3, 2tc 2rc",
     ["Ks", "7d", "2c"], "AA,KK,QQ", "JJ,TT,99",
     True, True, 2, 2, "standard", 200),

    ("R3", "River heavy: 3×3, 3tc 3rc",
     ["As", "Kd", "7c"], "AA,KK,QQ", "JJ,TT,99",
     True, True, 3, 3, "standard", 200),

    ("R4", "River extreme: 6×6, 2tc 2rc",
     ["As", "Kd", "7c"], "AA,KK,QQ,AKs,AKo,AQs", "JJ,TT,99,KQs,QJs,JTs",
     True, True, 2, 2, "standard", 200),

    # ── Preset variations ──
    ("P1", "Fast preset on moderate flop",
     ["As", "Kd", "7c"], "AA,KK,QQ,AKs,AKo,AQs", "JJ,TT,99,KQs,QJs,JTs",
     False, False, 0, 0, "fast", 200),

    ("P2", "Deep preset on moderate flop",
     ["As", "Kd", "7c"], "AA,KK,QQ,AKs,AKo,AQs", "JJ,TT,99,KQs,QJs,JTs",
     False, False, 0, 0, "deep", 500),

    ("P3", "Fast preset on turn 3×3",
     ["Ks", "7d", "2c"], "AA,KK,QQ", "JJ,TT,99",
     True, False, 3, 0, "fast", 200),

    ("P4", "Deep preset on turn 3×3",
     ["Ks", "7d", "2c"], "AA,KK,QQ", "JJ,TT,99",
     True, False, 3, 0, "deep", 500),
]

def run_scenario(sid, label, board, ip, oop, inc_turn, inc_river,
                 mtc, mrc, preset, max_iter):
    """Run a single benchmark scenario. Returns result dict."""
    try:
        req = SolveRequest(
            board=board, ip_range=ip, oop_range=oop,
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.33, 0.5, 0.75, 1.0] if not inc_turn else [0.5, 1.0],
            raise_sizes=[2.5] if not inc_turn else [],
            max_iterations=max_iter,
            max_raises=1 if not inc_turn else 0,
            deterministic=True,
            include_turn=inc_turn,
            max_turn_cards=mtc,
            turn_bet_sizes=[0.5, 1.0],
            turn_raise_sizes=[],
            turn_max_raises=0,
            include_river=inc_river,
            max_river_cards=mrc,
            river_bet_sizes=[0.5, 1.0],
            river_raise_sizes=[],
            river_max_raises=0,
        )
        req._preset = preset

        solver = CfrSolver()
        t0 = time.time()
        result = solver.solve(req, progress_callback=lambda info: None)
        runtime = time.time() - t0

        meta = result.metadata or {}
        sq = meta.get('solve_quality', {})

        return {
            "id": sid, "label": label,
            "street": "river" if inc_river else ("turn" if inc_turn else "flop"),
            "preset": preset,
            "ip_combos": result.ip_combos,
            "oop_combos": result.oop_combos,
            "matchups": result.matchups,
            "tree_nodes": result.tree_nodes,
            "iterations": result.iterations,
            "runtime_s": round(runtime, 2),
            "convergence": round(result.convergence_metric, 4),
            "exploitability_mbb": round(result.exploitability_mbb, 1),
            "stop_reason": result.stop_reason,
            "quality_class": sq.get("quality_class", "unknown"),
            "quality_label": sq.get("quality_label_ru", ""),
            "difficulty_grade": meta.get("difficulty_grade", ""),
            "error": None,
        }
    except Exception as e:
        return {
            "id": sid, "label": label,
            "street": "river" if inc_river else ("turn" if inc_turn else "flop"),
            "preset": preset,
            "runtime_s": 0, "error": str(e),
            "ip_combos": 0, "oop_combos": 0, "matchups": 0, "tree_nodes": 0,
            "iterations": 0, "convergence": 0, "exploitability_mbb": 0,
            "stop_reason": "error", "quality_class": "error",
            "quality_label": "", "difficulty_grade": "",
        }


def main():
    print(f"Rust available: {RUST_AVAILABLE}, version: {RUST_VERSION}")
    print(f"Running {len(SCENARIOS)} scenarios...\n")

    results = []
    for args in SCENARIOS:
        sid, label = args[0], args[1]
        print(f"  [{sid}] {label}...", end=" ", flush=True)
        r = run_scenario(*args)
        if r["error"]:
            print(f"ERROR: {r['error'][:80]}")
        else:
            print(f"{r['runtime_s']}s, i={r['iterations']}, "
                  f"conv={r['convergence']}, stop={r['stop_reason']}, "
                  f"q={r['quality_class']}, "
                  f"m={r['matchups']}, nodes={r['tree_nodes']}")
        results.append(r)

    # Save results
    with open("benchmark_phase17_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary
    print("\n" + "="*100)
    print(f"{'ID':4s} {'Street':6s} {'Preset':8s} {'IP':4s} {'OOP':4s} {'Match':5s} "
          f"{'Nodes':6s} {'Iter':5s} {'Time':6s} {'Conv':8s} {'Stop':15s} "
          f"{'Quality':15s} {'Grade':10s}")
    print("-"*100)
    for r in results:
        if r["error"]:
            print(f"{r['id']:4s} {r['street']:6s} {r['preset']:8s} "
                  f"{'ERROR':<60s} {r['error'][:40]}")
        else:
            print(f"{r['id']:4s} {r['street']:6s} {r['preset']:8s} "
                  f"{r['ip_combos']:<4d} {r['oop_combos']:<4d} {r['matchups']:<5d} "
                  f"{r['tree_nodes']:<6d} {r['iterations']:<5d} {r['runtime_s']:<6.2f} "
                  f"{r['convergence']:<8.4f} {r['stop_reason']:<15s} "
                  f"{r['quality_class']:<15s} {r['difficulty_grade']:<10s}")

    print("\nBenchmark complete. Results saved to benchmark_phase17_results.json")


if __name__ == "__main__":
    main()
