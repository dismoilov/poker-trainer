"""
Phase 16B: Fast Fixed vs Adaptive benchmark.

Measures iteration count, convergence, stop reason, elapsed time.
Skips exploitability (too slow for wide ranges in benchmark).
Uses a minimal solver wrapper that only runs the iteration loop.
"""
import time, sys, json
sys.path.insert(0, '.')

from app.solver.cfr_solver import CfrSolver, SolveRequest, SolveProgressInfo

SCENARIOS = [
    {"id":"S1", "name":"Trivial flop (AA vs KK)", "board":["Ks","7d","2c"],
     "ip_range":"AA","oop_range":"KK","bet_sizes":[0.5],"raise_sizes":[],"max_raises":0,
     "preset":"standard","fixed_iters":100},
    {"id":"S2", "name":"Light flop (3×3)", "board":["Ts","8h","3c"],
     "ip_range":"AA,KK,QQ","oop_range":"JJ,TT,99","bet_sizes":[0.5,1.0],"raise_sizes":[],"max_raises":0,
     "preset":"standard","fixed_iters":150},
    {"id":"S3", "name":"Light+ flop (4×4, raise)", "board":["Ah","9d","4c"],
     "ip_range":"AA,KK,AKs,AQs","oop_range":"QQ,JJ,AJs,KQs","bet_sizes":[0.5,1.0],"raise_sizes":[2.5],"max_raises":1,
     "preset":"standard","fixed_iters":200},
    {"id":"S4", "name":"Moderate flop (6×6, raise)", "board":["Ks","7d","2c"],
     "ip_range":"AA,KK,QQ,AKs,AKo,AQs","oop_range":"JJ,TT,99,AJs,KQs,QJs",
     "bet_sizes":[0.5,1.0],"raise_sizes":[2.5],"max_raises":1,"preset":"standard","fixed_iters":200},
    {"id":"S5", "name":"Heavy flop (10×10)", "board":["Ah","8d","3c"],
     "ip_range":"AA,KK,QQ,JJ,TT,99,AKs,AQs,AJs,ATs","oop_range":"88,77,66,55,44,A9s,A8s,A7s,KQs,KJs",
     "bet_sizes":[0.5,1.0],"raise_sizes":[],"max_raises":0,"preset":"standard","fixed_iters":200},
    {"id":"S6", "name":"Moderate turn (4×4, 2tc)", "board":["Ks","7d","2c"],
     "ip_range":"AA,KK,AKs,AQs","oop_range":"QQ,JJ,AJs,KQs","bet_sizes":[0.5,1.0],"raise_sizes":[],"max_raises":0,
     "preset":"standard","fixed_iters":200,"include_turn":True,"max_turn_cards":2,
     "turn_bet_sizes":[0.5],"turn_raise_sizes":[],"turn_max_raises":0},
    {"id":"S7", "name":"Heavy flop (15×15, raise)", "board":["Jh","8d","4c"],
     "ip_range":"AA,KK,QQ,JJ,TT,99,88,AKs,AQs,AJs,ATs,KQs,KJs,QJs,JTs",
     "oop_range":"77,66,55,44,33,A9s,A8s,A7s,A6s,A5s,KTs,K9s,Q9s,T9s,98s",
     "bet_sizes":[0.5,1.0],"raise_sizes":[2.5],"max_raises":1,"preset":"standard","fixed_iters":200},
    {"id":"S8", "name":"Fast preset (6×6, raise)", "board":["Ks","7d","2c"],
     "ip_range":"AA,KK,QQ,AKs,AKo,AQs","oop_range":"JJ,TT,99,AJs,KQs,QJs",
     "bet_sizes":[0.5,1.0],"raise_sizes":[2.5],"max_raises":1,"preset":"fast","fixed_iters":100},
    {"id":"S9", "name":"Deep preset (6×6, raise)", "board":["Ks","7d","2c"],
     "ip_range":"AA,KK,QQ,AKs,AKo,AQs","oop_range":"JJ,TT,99,AJs,KQs,QJs",
     "bet_sizes":[0.5,1.0],"raise_sizes":[2.5],"max_raises":1,"preset":"deep","fixed_iters":350},
    {"id":"S10", "name":"Trivial deep (AA vs KK)", "board":["Ks","7d","2c"],
     "ip_range":"AA","oop_range":"KK","bet_sizes":[0.5],"raise_sizes":[],"max_raises":0,
     "preset":"deep","fixed_iters":150},
]

def make_request(s, max_it):
    return SolveRequest(
        board=s["board"], ip_range=s["ip_range"], oop_range=s["oop_range"],
        pot=10.0, effective_stack=50.0, bet_sizes=s["bet_sizes"],
        raise_sizes=s["raise_sizes"], max_iterations=max_it,
        max_raises=s["max_raises"], deterministic=True,
        include_turn=s.get("include_turn",False), max_turn_cards=s.get("max_turn_cards",0),
        turn_bet_sizes=s.get("turn_bet_sizes",[0.5,1.0]),
        turn_raise_sizes=s.get("turn_raise_sizes",[]), turn_max_raises=s.get("turn_max_raises",0),
        include_river=s.get("include_river",False), max_river_cards=s.get("max_river_cards",0),
        river_bet_sizes=s.get("river_bet_sizes",[0.5,1.0]),
        river_raise_sizes=s.get("river_raise_sizes",[]), river_max_raises=s.get("river_max_raises",0),
    )

def run_solve(s, mode):
    """mode='adaptive' or 'fixed'"""
    req = make_request(s, s["fixed_iters"])
    req._preset = s["preset"]
    solver = CfrSolver()
    cb = (lambda info: None) if mode == "adaptive" else None
    start = time.time()
    result = solver.solve(req, progress_callback=cb)
    elapsed = time.time() - start
    return {
        "iters": result.iterations, "conv": result.convergence_metric,
        "exploit": result.exploitability_mbb, "time": round(elapsed, 3),
        "stop": result.stop_reason,
        "quality": result.metadata.get("solve_quality",{}).get("quality_class","?"),
        "grade": result.metadata.get("difficulty_grade","?"),
        "matchups": result.matchups, "nodes": result.tree_nodes,
        "budget_target": result.metadata.get("adaptive_budget",{}).get("target_iterations","?"),
        "conv_target": result.metadata.get("adaptive_budget",{}).get("convergence_target","?"),
    }

if __name__ == "__main__":
    rows = []
    print("=" * 140)
    print("Phase 16B: Fixed vs Adaptive — 10 scenarios")
    print("=" * 140)

    for s in SCENARIOS:
        print(f"\n[{s['id']}] {s['name']} (preset={s['preset']})...", end="", flush=True)
        ada = run_solve(s, "adaptive")
        fixed = run_solve(s, "fixed")
        
        # Analysis
        iters_saved = fixed["iters"] - ada["iters"]
        time_saved = fixed["time"] - ada["time"]
        time_pct = (time_saved / max(fixed["time"], 0.001)) * 100
        conv_ratio = ada["conv"] / max(fixed["conv"], 0.000001) if fixed["conv"] > 0 else 1

        if iters_saved > 0 and conv_ratio < 1.5:
            verdict = "HELPS"
        elif iters_saved > 0 and conv_ratio >= 1.5:
            verdict = "RISKY"
        elif iters_saved == 0:
            verdict = "NEUTRAL"
        else:
            verdict = "UNCLEAR"

        row = {**s, "ada": ada, "fixed": fixed, "verdict": verdict, "time_pct": round(time_pct, 1)}
        rows.append(row)
        print(f" ada={ada['iters']}it/{ada['time']}s fixed={fixed['iters']}it/{fixed['time']}s → {verdict}")

    # Summary table
    print("\n\n" + "=" * 140)
    hdr = f"{'ID':<5} {'Scenario':<30} {'Pre':<5} {'FxIt':>5}→{'AdIt':>4} {'FxConv':>10} {'AdConv':>10} "
    hdr += f"{'FxT':>6} {'AdT':>6} {'Save%':>6} {'Stop':>16} {'Qual':>12} {'Grade':>8} {'Verdict':>8}"
    print(hdr)
    print("-" * 140)
    for r in rows:
        a, f = r["ada"], r["fixed"]
        print(f"{r['id']:<5} {r['name']:<30} {r['preset']:<5} "
              f"{f['iters']:>5}→{a['iters']:>4} {f['conv']:>10.6f} {a['conv']:>10.6f} "
              f"{f['time']:>6.3f} {a['time']:>6.3f} {r['time_pct']:>+5.1f}% "
              f"{a['stop']:>16} {a['quality']:>12} {a['grade']:>8} {r['verdict']:>8}")
    print("=" * 140)

    with open("benchmark_16b_results.json", "w") as fp:
        json.dump([{
            "id": r["id"], "name": r["name"], "preset": r["preset"],
            "fixed_iters": r["fixed"]["iters"], "ada_iters": r["ada"]["iters"],
            "fixed_conv": r["fixed"]["conv"], "ada_conv": r["ada"]["conv"],
            "fixed_time": r["fixed"]["time"], "ada_time": r["ada"]["time"],
            "stop_reason": r["ada"]["stop"], "quality": r["ada"]["quality"],
            "grade": r["ada"]["grade"], "verdict": r["verdict"],
            "matchups": r["ada"]["matchups"],
        } for r in rows], fp, indent=2)
    print("\n✓ Saved benchmark_16b_results.json")
