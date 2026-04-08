"""
Phase 13A: Correctness verification and performance benchmarks.

Compares Python hand evaluator / equity against Rust poker_core.
"""

import time
import sys

sys.path.insert(0, '.')

from app.poker_engine.cards import Card
from app.poker_engine.hand_eval import evaluate_best as py_evaluate_best
from app.poker_engine.types import HandCategory
from app.solver.cfr_solver import compute_showdown_equity, CfrSolver, SolveRequest
from app.solver.rust_bridge import (
    RUST_AVAILABLE, card_to_int, combo_to_ints, board_to_ints,
    rust_compute_equity, rust_evaluate_hand
)
import poker_core


def card(s):
    return Card.parse(s)


def cards(ss):
    return [Card.parse(s) for s in ss]


# ══════════════════════════════════════════════════════════════
# 1. CORRECTNESS: Hand Evaluation Equivalence
# ══════════════════════════════════════════════════════════════

print("=" * 70)
print("CORRECTNESS: Python vs Rust Hand Evaluation")
print("=" * 70)

eval_scenarios = [
    ("AA vs KK on 972r", ["Ah", "Ad", "9s", "7d", "2c"], ["Kh", "Kd", "9s", "7d", "2c"]),
    ("AA vs AA tie",      ["Ah", "Ad", "9s", "7d", "2c"], ["Ac", "As", "9s", "7d", "2c"]),
    ("KK vs QQ on K72",   ["Kh", "Kd", "Ks", "7d", "2c"], ["Qh", "Qd", "Ks", "7d", "2c"]),
    ("Set vs overpair",   ["2h", "2d", "As", "7d", "2c"], ["Ah", "Ad", "As", "7d", "2c"]),
    ("Flush vs straight", ["Ah", "Kh", "Qh", "Jh", "9h"], ["Tc", "9d", "8s", "7h", "6c"]),
    ("Full vs flush",     ["Ah", "Ad", "Ac", "Kh", "Kd"], ["Qh", "Jh", "Th", "9h", "2h"]),
    ("Quads vs full",     ["Ah", "Ad", "Ac", "As", "Kd"], ["Kh", "Kc", "Ks", "Qh", "Qd"]),
    ("Str flush vs quads",["5h", "6h", "7h", "8h", "9h"], ["Ah", "Ad", "Ac", "As", "Kd"]),
    ("Wheel straight",    ["Ah", "2d", "3s", "4h", "5c"], ["Kh", "Qd", "Js", "Th", "2c"]),
    ("7-card board",      ["Ah", "Kh", "9s", "7d", "2c", "Th", "Jh"], ["Qs", "Qd", "9s", "7d", "2c", "Th", "Jh"]),
]

all_match = True
for name, hand1_strs, hand2_strs in eval_scenarios:
    hand1 = cards(hand1_strs)
    hand2 = cards(hand2_strs)

    py_rank1 = py_evaluate_best(hand1)
    py_rank2 = py_evaluate_best(hand2)
    py_winner = "hand1" if py_rank1 > py_rank2 else ("hand2" if py_rank2 > py_rank1 else "tie")

    rust_rank1 = poker_core.evaluate_hand([card_to_int(c) for c in hand1])
    rust_rank2 = poker_core.evaluate_hand([card_to_int(c) for c in hand2])
    rust_winner = "hand1" if rust_rank1 > rust_rank2 else ("hand2" if rust_rank2 > rust_rank1 else "tie")

    match = py_winner == rust_winner
    if not match:
        all_match = False
    print(f"  {name:30s}  py={py_winner:6s}  rust={rust_winner:6s}  {'✅' if match else '❌ MISMATCH'}")

print(f"\nOverall equivalence: {'✅ ALL MATCH' if all_match else '❌ MISMATCH'}")


# ══════════════════════════════════════════════════════════════
# 2. CORRECTNESS: Showdown Equity Equivalence
# ══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("CORRECTNESS: Python vs Rust Showdown Equity")
print("=" * 70)

equity_scenarios = [
    ("AA vs KK, 972r flop", ("Ah", "Ad"), ("Kh", "Kd"), ["9s", "7d", "2c"]),
    ("AA vs AA tie, 972r",  ("Ah", "Ad"), ("Ac", "As"), ["9s", "7d", "2c"]),
    ("KK vs QQ, K72 flop",  ("Kh", "Kd"), ("Qh", "Qd"), ["Ks", "7d", "2c"]),
    ("22 vs AA, A72 flop",  ("2h", "2d"), ("Ah", "Ad"), ["As", "7d", "2c"]),
    ("AKs vs QJs, QJT flop", ("Ah", "Kh"), ("Qd", "Jd"), ["Qs", "Jc", "Ts"]),
    ("AA vs KK, 4-card turn", ("Ah", "Ad"), ("Kh", "Kd"), ["9s", "7d", "2c", "3h"]),
    ("KK vs 77, 7-high board", ("Kh", "Kd"), ("7h", "7s"), ["9s", "7d", "2c"]),
    ("AA vs KK, 5-card river", ("Ah", "Ad"), ("Kh", "Kd"), ["9s", "7d", "2c", "3h", "5d"]),
]

eq_all_match = True
for name, ip_strs, oop_strs, board_strs in equity_scenarios:
    ip_combo = tuple(cards(list(ip_strs)))
    oop_combo = tuple(cards(list(oop_strs)))
    board = cards(board_strs)

    py_eq = compute_showdown_equity(ip_combo, oop_combo, board)
    rust_eq = rust_compute_equity(ip_combo, oop_combo, board)

    match = abs(py_eq - rust_eq) < 0.001
    if not match:
        eq_all_match = False
    print(f"  {name:30s}  py={py_eq:.4f}  rust={rust_eq:.4f}  {'✅' if match else '❌ MISMATCH'}")

print(f"\nOverall equity equivalence: {'✅ ALL MATCH' if eq_all_match else '❌ MISMATCH'}")


# ══════════════════════════════════════════════════════════════
# 3. PERFORMANCE: Hand Evaluation (single calls)
# ══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("PERFORMANCE: Hand Evaluation (100K calls)")
print("=" * 70)

test_hands = [
    cards(["Ah", "Ad", "9s", "7d", "2c"]),
    cards(["Kh", "Kd", "Ks", "7d", "2c"]),
    cards(["5h", "6h", "7h", "8h", "9h"]),
    cards(["Ah", "Kh", "9s", "7d", "2c", "Th", "Jh"]),
]

N = 100_000

# Python
t0 = time.time()
for _ in range(N):
    for hand in test_hands:
        py_evaluate_best(hand)
py_time = time.time() - t0

# Rust
rust_hands = [[card_to_int(c) for c in hand] for hand in test_hands]
t0 = time.time()
for _ in range(N):
    for hand in rust_hands:
        poker_core.evaluate_hand(hand)
rust_time = time.time() - t0

print(f"  Python: {py_time:.3f}s ({N * len(test_hands)} evals)")
print(f"  Rust:   {rust_time:.3f}s ({N * len(test_hands)} evals)")
print(f"  Speedup: {py_time / rust_time:.1f}×")


# ══════════════════════════════════════════════════════════════
# 4. PERFORMANCE: Equity Computation (single calls)
# ══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("PERFORMANCE: Single Equity Calls (10K calls)")
print("=" * 70)

N_eq = 10_000
ip_c = tuple(cards(["Ah", "Ad"]))
oop_c = tuple(cards(["Kh", "Kd"]))
board_c = cards(["9s", "7d", "2c"])

t0 = time.time()
for _ in range(N_eq):
    compute_showdown_equity(ip_c, oop_c, board_c)
py_eq_time = time.time() - t0

ip_ints = combo_to_ints(ip_c)
oop_ints = combo_to_ints(oop_c)
board_ints = board_to_ints(board_c)
t0 = time.time()
for _ in range(N_eq):
    poker_core.compute_equity(ip_ints, oop_ints, board_ints)
rust_eq_time = time.time() - t0

print(f"  Python: {py_eq_time:.3f}s ({N_eq} calls)")
print(f"  Rust:   {rust_eq_time:.3f}s ({N_eq} calls)")
print(f"  Speedup: {py_eq_time / rust_eq_time:.1f}×")


# ══════════════════════════════════════════════════════════════
# 5. PERFORMANCE: Batch Equity (solver-style)
# ══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("PERFORMANCE: Batch Equity (solver-style precompute)")
print("=" * 70)

# Build combos manually for benchmark
from app.poker_engine.cards import Card as C

def make_pair(r1, r2, s1, s2):
    return (C.parse(f"{r1}{s1}"), C.parse(f"{r2}{s2}"))

# IP: AA, KK, QQ, JJ — 6 combos each = 24
ip_combos = []
for r in ["A", "K", "Q", "J"]:
    for s1, s2 in [("h","d"), ("h","c"), ("h","s"), ("d","c"), ("d","s"), ("c","s")]:
        ip_combos.append(make_pair(r, r, s1, s2))

# OOP: TT, 99 — 6 combos each = 12
oop_combos = []
for r in ["T", "9"]:
    for s1, s2 in [("h","d"), ("h","c"), ("h","s"), ("d","c"), ("d","s"), ("c","s")]:
        oop_combos.append(make_pair(r, r, s1, s2))

board_cards = cards(["Ks", "7d", "2c"])

# Build valid matchups (no blocker conflicts)
board_set = {str(c) for c in board_cards}
valid = []
for i, ic in enumerate(ip_combos):
    ic_strs = {str(ic[0]), str(ic[1])}
    if ic_strs & board_set:
        continue
    for j, oc in enumerate(oop_combos):
        oc_strs = {str(oc[0]), str(oc[1])}
        if oc_strs & board_set or oc_strs & ic_strs:
            continue
        valid.append((i, j))

print(f"  IP combos: {len(ip_combos)}, OOP combos: {len(oop_combos)}, valid matchups: {len(valid)}")

# Python batch
N_batch = 100
t0 = time.time()
for _ in range(N_batch):
    for ip_idx, oop_idx in valid:
        compute_showdown_equity(ip_combos[ip_idx], oop_combos[oop_idx], board_cards)
py_batch_time = time.time() - t0

# Rust batch
ip_hands_r = [combo_to_ints(c) for c in ip_combos]
oop_hands_r = [combo_to_ints(c) for c in oop_combos]
board_r = board_to_ints(board_cards)
t0 = time.time()
for _ in range(N_batch):
    poker_core.batch_compute_equity(ip_hands_r, oop_hands_r, board_r, valid)
rust_batch_time = time.time() - t0

print(f"  Python: {py_batch_time:.3f}s ({N_batch} × {len(valid)} = {N_batch * len(valid)} evals)")
print(f"  Rust:   {rust_batch_time:.3f}s ({N_batch} × {len(valid)} = {N_batch * len(valid)} evals)")
print(f"  Speedup: {py_batch_time / rust_batch_time:.1f}×")


# ══════════════════════════════════════════════════════════════
# 6. SOLVER INTEGRATION: Full solve comparison
# ══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("SOLVER INTEGRATION: Full solve with Rust equity")
print("=" * 70)

scenarios = [
    ("Flop narrow AA vs KK", dict(board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
     pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0], max_iterations=50, deterministic=True)),
    ("Flop broad 4×4", dict(board=["Ks", "7d", "2c"], ip_range="AA,KK,QQ,JJ",
     oop_range="TT,99,AKs,AQs", pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
     max_iterations=50, deterministic=True)),
    ("Turn AA vs KK", dict(board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
     pot=10.0, effective_stack=50.0, bet_sizes=[0.5], max_iterations=15, deterministic=True,
     include_turn=True, max_turn_cards=2, turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0)),
]

for name, kwargs in scenarios:
    solver = CfrSolver()
    t0 = time.time()
    output = solver.solve(SolveRequest(**kwargs))
    elapsed = time.time() - t0
    print(f"  {name}: conv={output.convergence_metric:.6f}, exploit={output.exploitability_mbb:.0f}, "
          f"nodes={len(output.strategies)}, time={elapsed:.3f}s")

print("\n✅ All scenarios completed with Rust equity backend")
