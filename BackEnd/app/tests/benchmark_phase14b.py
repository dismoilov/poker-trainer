"""
Phase 14B: Serial vs Parallel Rust CFR Benchmark Suite.

Runs identical scenarios through both serial and parallel Rust paths,
measuring time, convergence, and exploitability for direct comparison.
"""
import time
import json
import sys
import os

# Ensure imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.solver.cfr_solver import CfrSolver, SolveRequest


SCENARIOS = [
    # --- FLOP NARROW ---
    {
        "name": "flop_narrow_AA_vs_KK",
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AA", "oop_range": "KK",
        "pot": 10.0, "stack": 50.0,
        "bet_sizes": [0.5, 1.0], "raise_sizes": [],
        "max_iter": 200, "max_raises": 0,
        "include_turn": False, "include_river": False,
        "turn_cfg": {},
    },
    # --- FLOP BROADER ---
    {
        "name": "flop_broad_3x3_ranges",
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AA,KK,QQ", "oop_range": "JJ,TT,99",
        "pot": 10.0, "stack": 50.0,
        "bet_sizes": [0.5, 1.0], "raise_sizes": [2.5],
        "max_iter": 200, "max_raises": 2,
        "include_turn": False, "include_river": False,
        "turn_cfg": {},
    },
    # --- FLOP WIDEST ---
    {
        "name": "flop_widest_6_ranges",
        "board": ["9s", "6d", "3c"],
        "ip_range": "AA,KK,QQ,JJ,TT,99", "oop_range": "88,77,66,55,44,33",
        "pot": 10.0, "stack": 50.0,
        "bet_sizes": [0.5, 1.0], "raise_sizes": [],
        "max_iter": 100, "max_raises": 0,
        "include_turn": False, "include_river": False,
        "turn_cfg": {},
    },
    # --- TURN NARROW ---
    {
        "name": "turn_narrow_AA_vs_KK_2tc",
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AA", "oop_range": "KK",
        "pot": 10.0, "stack": 50.0,
        "bet_sizes": [0.5], "raise_sizes": [],
        "max_iter": 200, "max_raises": 0,
        "include_turn": True, "include_river": False,
        "turn_cfg": {"max_turn_cards": 2, "turn_bet_sizes": [0.5],
                     "turn_raise_sizes": [], "turn_max_raises": 0},
    },
    # --- TURN BROADER ---
    {
        "name": "turn_broad_QQ_vs_JJ_3tc",
        "board": ["Ks", "7d", "2c"],
        "ip_range": "QQ,JJ", "oop_range": "TT,99",
        "pot": 10.0, "stack": 50.0,
        "bet_sizes": [0.5], "raise_sizes": [],
        "max_iter": 100, "max_raises": 0,
        "include_turn": True, "include_river": False,
        "turn_cfg": {"max_turn_cards": 3, "turn_bet_sizes": [0.5],
                     "turn_raise_sizes": [], "turn_max_raises": 0},
    },
    # --- RIVER NARROW ---
    {
        "name": "river_narrow_AA_vs_KK_2tc2rc",
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AA", "oop_range": "KK",
        "pot": 10.0, "stack": 50.0,
        "bet_sizes": [0.5], "raise_sizes": [],
        "max_iter": 200, "max_raises": 0,
        "include_turn": True, "include_river": True,
        "turn_cfg": {"max_turn_cards": 2, "turn_bet_sizes": [0.5],
                     "turn_raise_sizes": [], "turn_max_raises": 0,
                     "max_river_cards": 2, "river_bet_sizes": [0.5],
                     "river_raise_sizes": [], "river_max_raises": 0},
    },
    # --- RIVER BROADER ---
    {
        "name": "river_broad_QQ_vs_JJ_2tc2rc",
        "board": ["9s", "7d", "2c"],
        "ip_range": "QQ", "oop_range": "JJ",
        "pot": 10.0, "stack": 50.0,
        "bet_sizes": [0.5], "raise_sizes": [],
        "max_iter": 100, "max_raises": 0,
        "include_turn": True, "include_river": True,
        "turn_cfg": {"max_turn_cards": 2, "turn_bet_sizes": [0.5],
                     "turn_raise_sizes": [], "turn_max_raises": 0,
                     "max_river_cards": 2, "river_bet_sizes": [0.5],
                     "river_raise_sizes": [], "river_max_raises": 0},
    },
    # --- HEAVIER PRACTICAL ---
    {
        "name": "practical_heavy_3x3_turn_river",
        "board": ["Ks", "7d", "2c"],
        "ip_range": "AA,KK,QQ", "oop_range": "JJ,TT,99",
        "pot": 10.0, "stack": 50.0,
        "bet_sizes": [0.5], "raise_sizes": [],
        "max_iter": 50, "max_raises": 0,
        "include_turn": True, "include_river": True,
        "turn_cfg": {"max_turn_cards": 2, "turn_bet_sizes": [0.5],
                     "turn_raise_sizes": [], "turn_max_raises": 0,
                     "max_river_cards": 2, "river_bet_sizes": [0.5],
                     "river_raise_sizes": [], "river_max_raises": 0},
    },
]


def make_request(s, force_parallel):
    """Build a SolveRequest from scenario dict."""
    kw = dict(
        board=s["board"], ip_range=s["ip_range"], oop_range=s["oop_range"],
        pot=s["pot"], effective_stack=s["stack"],
        bet_sizes=s["bet_sizes"], raise_sizes=s["raise_sizes"],
        max_iterations=s["max_iter"], max_raises=s["max_raises"],
        deterministic=True,
        include_turn=s["include_turn"],
        include_river=s["include_river"],
    )
    tc = s["turn_cfg"]
    if s["include_turn"]:
        kw.update(max_turn_cards=tc["max_turn_cards"],
                  turn_bet_sizes=tc["turn_bet_sizes"],
                  turn_raise_sizes=tc["turn_raise_sizes"],
                  turn_max_raises=tc["turn_max_raises"])
    if s["include_river"]:
        kw.update(max_river_cards=tc["max_river_cards"],
                  river_bet_sizes=tc["river_bet_sizes"],
                  river_raise_sizes=tc["river_raise_sizes"],
                  river_max_raises=tc["river_max_raises"])
    return SolveRequest(**kw)


def run_one(scenario, force_parallel):
    """Run a solve forcing serial or parallel, return metrics."""
    solver = CfrSolver()
    
    # Monkey-patch the dispatch to force the mode
    orig_run = solver._run_iterations_rust
    def patched_run(max_iter, start_time, setup_time, 
                    include_turn=False, include_river=False):
        import poker_core
        tree_data = solver._serialize_tree_for_rust(
            include_turn=include_turn, include_river=include_river,
        )
        num_matchups = len(tree_data['matchup_ip'])
        
        convergence = poker_core.cfr_iterate(
            tree_data['node_types'], tree_data['node_players'],
            tree_data['node_pots'], tree_data['node_num_actions'],
            tree_data['node_first_child'], tree_data['children_ids'],
            tree_data['node_chance_card_abs'], tree_data['node_chance_equity_idx'],
            tree_data['ip_hole_cards_abs'], tree_data['oop_hole_cards_abs'],
            tree_data['turn_idx_to_abs'],
            tree_data['num_turn_cards'], tree_data['num_river_cards'],
            tree_data['info_map'], tree_data['max_combos'],
            solver._arrays.regrets, solver._arrays.strategy_sums,
            solver._arrays.max_actions,
            tree_data['equity_tables'],
            tree_data['num_ip'], tree_data['num_oop'],
            tree_data['matchup_ip'], tree_data['matchup_oop'],
            max_iter, tree_data['root_node_id'],
            force_parallel,  # <-- forced mode
        )
        solver._iteration_count = max_iter
        return max_iter
    
    solver._run_iterations_rust = patched_run
    
    req = make_request(scenario, force_parallel)
    t0 = time.time()
    output = solver.solve(req)
    elapsed = time.time() - t0
    
    return {
        "time": elapsed,
        "convergence": output.convergence_metric,
        "exploitability_mbb": output.exploitability_mbb,
        "iterations": output.iterations,
        "tree_nodes": output.tree_nodes,
        "matchups": getattr(output, '_matchup_count', 0),
    }


def run_benchmarks():
    """Run all scenarios, serial and parallel, collecting results."""
    import logging
    logging.disable(logging.INFO)  # suppress solver logs for clean output
    
    results = []
    for i, scenario in enumerate(SCENARIOS):
        name = scenario["name"]
        print(f"\n[{i+1}/{len(SCENARIOS)}] {name}")
        
        # Run serial
        print(f"  Running SERIAL...", end="", flush=True)
        serial = run_one(scenario, force_parallel=False)
        print(f" {serial['time']:.3f}s")
        
        # Run parallel  
        print(f"  Running PARALLEL...", end="", flush=True)
        parallel = run_one(scenario, force_parallel=True)
        print(f" {parallel['time']:.3f}s")
        
        speedup = serial["time"] / max(parallel["time"], 0.001)
        
        if speedup > 1.05:
            verdict = f"PARALLEL FASTER ({speedup:.2f}x)"
        elif speedup < 0.95:
            verdict = f"SERIAL FASTER ({1/speedup:.2f}x)"
        else:
            verdict = "NEUTRAL"
        
        result = {
            "name": name,
            "board": " ".join(scenario["board"]),
            "ip_range": scenario["ip_range"],
            "oop_range": scenario["oop_range"],
            "config": f"{'turn+river' if scenario['include_river'] else 'turn' if scenario['include_turn'] else 'flop'}, {scenario['max_iter']}i",
            "serial_time": serial["time"],
            "parallel_time": parallel["time"],
            "speedup": speedup,
            "serial_convergence": serial["convergence"],
            "parallel_convergence": parallel["convergence"],
            "serial_exploitability": serial["exploitability_mbb"],
            "parallel_exploitability": parallel["exploitability_mbb"],
            "convergence_delta": abs(serial["convergence"] - parallel["convergence"]),
            "exploitability_delta": abs(serial["exploitability_mbb"] - parallel["exploitability_mbb"]),
            "tree_nodes": serial["tree_nodes"],
            "verdict": verdict,
        }
        results.append(result)
        
        print(f"  Speedup: {speedup:.2f}x | Verdict: {verdict}")
        print(f"  Conv: serial={serial['convergence']:.6f}, parallel={parallel['convergence']:.6f}, Δ={result['convergence_delta']:.6f}")
        print(f"  Expl: serial={serial['exploitability_mbb']:.1f}, parallel={parallel['exploitability_mbb']:.1f}, Δ={result['exploitability_delta']:.1f} mbb")
    
    return results


def print_table(results):
    """Print a formatted comparison table."""
    print("\n" + "="*160)
    print("SERIAL VS PARALLEL BENCHMARK RESULTS")
    print("="*160)
    hdr = f"{'Scenario':<35} {'Config':<18} {'Serial(s)':<10} {'Par(s)':<10} {'Speedup':<10} {'S-Conv':<10} {'P-Conv':<10} {'ΔConv':<10} {'S-Expl':<10} {'P-Expl':<10} {'ΔExpl':<10} {'Verdict':<20}"
    print(hdr)
    print("-"*160)
    for r in results:
        row = f"{r['name']:<35} {r['config']:<18} {r['serial_time']:<10.3f} {r['parallel_time']:<10.3f} {r['speedup']:<10.2f} {r['serial_convergence']:<10.4f} {r['parallel_convergence']:<10.4f} {r['convergence_delta']:<10.4f} {r['serial_exploitability']:<10.1f} {r['parallel_exploitability']:<10.1f} {r['exploitability_delta']:<10.1f} {r['verdict']:<20}"
        print(row)
    print("="*160)


if __name__ == "__main__":
    print("Phase 14B: Serial vs Parallel Rust CFR Benchmark")
    print(f"CPU cores: {os.cpu_count()}")
    results = run_benchmarks()
    print_table(results)
    
    # Save JSON for report
    out_path = os.path.join(os.path.dirname(__file__), "benchmark_phase14b_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")
