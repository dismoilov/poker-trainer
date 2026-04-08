"""
Phase 13D: Comprehensive benchmark & correctness validation.
Compares Rust CFR traversal vs Python CFR traversal for RIVER scenarios.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.solver.cfr_solver import CfrSolver, SolveRequest

def solve_python(request):
    solver = CfrSolver()
    solver._should_use_rust_cfr = lambda r, c=None, p=None: False
    t0 = time.time()
    output = solver.solve(request)
    return {
        'convergence': output.convergence_metric,
        'exploitability': output.exploitability_mbb,
        'time': round(time.time() - t0, 4),
        'nodes': output.tree_nodes,
        'strategies': output.strategies,
    }

def solve_rust(request):
    solver = CfrSolver()
    t0 = time.time()
    output = solver.solve(request)
    return {
        'convergence': output.convergence_metric,
        'exploitability': output.exploitability_mbb,
        'time': round(time.time() - t0, 4),
        'nodes': output.tree_nodes,
        'strategies': output.strategies,
    }

# ── River-enabled scenarios ──
scenarios = [
    {
        'name': 'AA vs KK river 1tc+1rc (15 iter)',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=1,
            include_river=True, max_river_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ),
    },
    {
        'name': 'AA vs KK river 2tc+2rc (15 iter)',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ),
    },
    {
        'name': 'QQ vs JJ river 2tc+1rc (15 iter)',
        'request': SolveRequest(
            board=['9s', '7d', '2c'], ip_range='QQ', oop_range='JJ',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ),
    },
    {
        'name': 'AA,KK vs QQ,JJ river 2tc+2rc (15 iter)',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA,KK', oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ),
    },
    {
        'name': 'AA vs KK river 3tc+3rc (20 iter)',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=20, deterministic=True,
            include_turn=True, max_turn_cards=3,
            include_river=True, max_river_cards=3,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ),
    },
    {
        'name': 'Multi bet sizes 2tc+2rc (15 iter)',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.33, 0.5, 1.0],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ),
    },
    {
        'name': 'AA,KK,QQ vs JJ,TT river 2tc+2rc (15 iter)',
        'request': SolveRequest(
            board=['8s', '7d', '2c'], ip_range='AA,KK,QQ', oop_range='JJ,TT',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ),
    },
    # Flop-only regression
    {
        'name': 'Flop-only AA vs KK (50 iter) REGRESSION',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ),
    },
    # Turn-only regression
    {
        'name': 'Turn-only AA vs KK (20 iter) REGRESSION',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=20, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ),
    },
]

print("=" * 100)
print("PHASE 13D: PYTHON VS RUST RIVER CFR CORRECTNESS & PERFORMANCE")
print("=" * 100)
print()

results = []
for scenario in scenarios:
    name = scenario['name']
    request = scenario['request']
    print(f"  {name}:")
    
    py = solve_python(request)
    print(f"    Python: conv={py['convergence']:.6f}, exploit={py['exploitability']:.1f}, time={py['time']:.4f}s, nodes={py['nodes']}")
    
    rs = solve_rust(request)
    print(f"    Rust:   conv={rs['convergence']:.6f}, exploit={rs['exploitability']:.1f}, time={rs['time']:.4f}s, nodes={rs['nodes']}")
    
    conv_match = abs(py['convergence'] - rs['convergence']) < 0.001
    exploit_match = abs(py['exploitability'] - rs['exploitability']) < 10.0
    speedup = py['time'] / max(rs['time'], 0.0001)
    verdict = "✅" if conv_match and exploit_match else "❌"
    
    print(f"    Speedup: {speedup:.1f}×  Conv match: {conv_match}  Exploit match: {exploit_match}  {verdict}")
    print()
    
    results.append({
        'name': name, 'py_conv': py['convergence'], 'rs_conv': rs['convergence'],
        'py_exploit': py['exploitability'], 'rs_exploit': rs['exploitability'],
        'py_time': py['time'], 'rs_time': rs['time'], 'speedup': speedup,
        'conv_match': conv_match, 'exploit_match': exploit_match, 'verdict': verdict,
        'nodes': py['nodes'],
    })

# Strategy comparison for first river scenario
print("=" * 100)
print("STRATEGY COMPARISON (River: AA vs KK, 2tc+2rc, 15 iter)")
print("=" * 100)
req = scenarios[1]['request']
py = solve_python(req)
rs = solve_rust(req)
matched = 0
total = 0
for node_id in sorted(py['strategies'].keys())[:5]:
    py_node = py['strategies'][node_id]
    rs_node = rs['strategies'].get(node_id, {})
    for combo in sorted(py_node.keys())[:2]:
        py_strat = py_node[combo]
        rs_strat = rs_node.get(combo, {})
        match = all(abs(py_strat.get(a, 0) - rs_strat.get(a, 0)) < 0.01
                    for a in set(list(py_strat.keys()) + list(rs_strat.keys())))
        total += 1
        matched += match
        py_str = ", ".join(f"{a}:{v:.3f}" for a, v in sorted(py_strat.items()))
        rs_str = ", ".join(f"{a}:{v:.3f}" for a, v in sorted(rs_strat.items()))
        print(f"  {node_id[:25]:25s} {combo:6s}  py=[{py_str}]")
        print(f"  {'':25s} {'':6s}  rs=[{rs_str}]  {'✅' if match else '❌'}")
print(f"\n  Strategy match: {matched}/{total}")

# Summary
print()
print("=" * 100)
print("SUMMARY")
print("=" * 100)
all_match = all(r['conv_match'] and r['exploit_match'] for r in results)
avg_speedup = sum(r['speedup'] for r in results) / len(results)
print(f"  All correctness checks: {'✅ PASS' if all_match else '❌ FAIL'}")
print(f"  Average speedup: {avg_speedup:.1f}×")
print(f"  Scenarios tested: {len(results)}")
for r in results:
    print(f"    {r['name']:55s}  py={r['py_time']:.4f}s  rs={r['rs_time']:.4f}s  {r['speedup']:6.1f}×  {r['verdict']}  nodes={r['nodes']}")
