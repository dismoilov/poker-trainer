"""
Phase 13B: Comprehensive benchmark & correctness validation.

Compares Rust CFR traversal vs Python CFR traversal across multiple scenarios.
Measures end-to-end solver runtime before/after.
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.solver.cfr_solver import CfrSolver, SolveRequest

# ── Monkeypatch to force Python path ──
def solve_python(request: SolveRequest) -> dict:
    """Force Python iteration path."""
    solver = CfrSolver()
    # Temporarily disable Rust
    original = solver._should_use_rust_cfr
    solver._should_use_rust_cfr = lambda r, c=None, p=None: False
    t0 = time.time()
    output = solver.solve(request)
    t1 = time.time()
    return {
        'convergence': output.convergence_metric,
        'exploitability': output.exploitability_mbb,
        'iterations': output.iterations,
        'time': round(t1 - t0, 4),
        'nodes': output.tree_nodes,
        'strategies': output.strategies,
    }

def solve_rust(request: SolveRequest) -> dict:
    """Force Rust iteration path (default for flop-only)."""
    solver = CfrSolver()
    t0 = time.time()
    output = solver.solve(request)
    t1 = time.time()
    return {
        'convergence': output.convergence_metric,
        'exploitability': output.exploitability_mbb,
        'iterations': output.iterations,
        'time': round(t1 - t0, 4),
        'nodes': output.tree_nodes,
        'strategies': output.strategies,
    }


# ── Scenarios ──
scenarios = [
    {
        'name': 'Narrow AA vs KK (50 iter)',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ),
    },
    {
        'name': 'QQ vs JJ (50 iter)',
        'request': SolveRequest(
            board=['9s', '7d', '2c'], ip_range='QQ', oop_range='JJ',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ),
    },
    {
        'name': 'AK vs QQ (100 iter)',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AKs,AKo', oop_range='QQ',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=100, deterministic=True,
        ),
    },
    {
        'name': 'Broad 4x4 (50 iter)',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA,KK,QQ,JJ',
            oop_range='TT,99,AKs,AQs',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ),
    },
    {
        'name': 'Wide 6x4 (50 iter)',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA,KK,QQ,JJ,TT,99',
            oop_range='88,77,AKs,AQs',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ),
    },
    {
        'name': 'Multi-size 3 bets (50 iter)',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.33, 0.5, 1.0],
            max_iterations=50, deterministic=True,
        ),
    },
    {
        'name': 'AA vs KK 200 iter',
        'request': SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=200, deterministic=True,
        ),
    },
]

# ── Run comparisons ──
print("=" * 90)
print("PHASE 13B: PYTHON VS RUST CFR CORRECTNESS & PERFORMANCE")
print("=" * 90)
print()

results = []

for scenario in scenarios:
    name = scenario['name']
    request = scenario['request']
    
    print(f"  {name}:")
    
    # Python path
    py = solve_python(request)
    print(f"    Python: conv={py['convergence']:.6f}, exploit={py['exploitability']:.1f}, time={py['time']:.4f}s")
    
    # Rust path
    rs = solve_rust(request)
    print(f"    Rust:   conv={rs['convergence']:.6f}, exploit={rs['exploitability']:.1f}, time={rs['time']:.4f}s")
    
    # Compare convergence
    conv_match = abs(py['convergence'] - rs['convergence']) < 0.001
    exploit_match = abs(py['exploitability'] - rs['exploitability']) < 10.0
    
    speedup = py['time'] / max(rs['time'], 0.0001)
    
    verdict = "✅" if conv_match and exploit_match else "❌"
    print(f"    Speedup: {speedup:.1f}×  Convergence match: {conv_match}  Exploit match: {exploit_match}  {verdict}")
    print()
    
    results.append({
        'name': name,
        'py_conv': py['convergence'],
        'rs_conv': rs['convergence'],
        'py_exploit': py['exploitability'],
        'rs_exploit': rs['exploitability'],
        'py_time': py['time'],
        'rs_time': rs['time'],
        'speedup': speedup,
        'conv_match': conv_match,
        'exploit_match': exploit_match,
        'verdict': verdict,
    })

# ── Strategy comparison for one scenario ──
print("=" * 90)
print("STRATEGY COMPARISON: AA vs KK")
print("=" * 90)

req = scenarios[0]['request']
py = solve_python(req)
rs = solve_rust(req)

for node_id in sorted(py['strategies'].keys()):
    py_node = py['strategies'][node_id]
    rs_node = rs['strategies'].get(node_id, {})
    
    for combo in sorted(py_node.keys())[:3]:  # Show first 3 combos
        py_strat = py_node[combo]
        rs_strat = rs_node.get(combo, {})
        
        py_str = ", ".join(f"{a}:{v:.3f}" for a, v in sorted(py_strat.items()))
        rs_str = ", ".join(f"{a}:{v:.3f}" for a, v in sorted(rs_strat.items()))
        
        match = all(abs(py_strat.get(a, 0) - rs_strat.get(a, 0)) < 0.01 for a in set(list(py_strat.keys()) + list(rs_strat.keys())))
        print(f"  {node_id[:30]:30s} {combo:6s}  py=[{py_str}]")
        print(f"  {'':30s} {'':6s}  rs=[{rs_str}]  {'✅' if match else '❌'}")

# ── Summary ──
print()
print("=" * 90)
print("SUMMARY")
print("=" * 90)
all_match = all(r['conv_match'] and r['exploit_match'] for r in results)
avg_speedup = sum(r['speedup'] for r in results) / len(results)
print(f"  All correctness checks: {'✅ PASS' if all_match else '❌ FAIL'}")
print(f"  Average speedup: {avg_speedup:.1f}×")
print(f"  Scenarios tested: {len(results)}")
for r in results:
    print(f"    {r['name']:35s}  py={r['py_time']:.4f}s  rs={r['rs_time']:.4f}s  {r['speedup']:.1f}×  {r['verdict']}")
