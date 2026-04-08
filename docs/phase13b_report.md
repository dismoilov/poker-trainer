# Phase 13B: Rust CFR Inner Loop — Technical Report

## Executive Summary

Phase 13B moved the CFR+ traversal inner loop — the solver's primary bottleneck at ~70% of runtime — into compiled Rust. The result is a **3.9×–37.6× end-to-end solver speedup** (average **16.9×**) for flop-only solves, with **exact correctness** (convergence values match Python to 6 decimal places).

## Scope

| Aspect | Detail |
|--------|--------|
| **Target** | `_cfr_traverse()` + `_get_current_strategy()` + `_accumulate_strategy()` + `_terminal_value_fast()` |
| **Runtime share** | ~70% of total solver time |
| **Boundary** | Flop-only solves (no chance nodes) |
| **Fallback** | Turn/river solves use Python; cancel/progress callbacks use Python |

## Architecture

### Tree Serialization

The Python `GameTreeNode` tree is serialized into **6 flat NumPy arrays** that Rust processes via zero-copy access:

```
node_types[N]:       i32  — 0=action, 1=fold_ip, 2=fold_oop, 3=showdown
node_players[N]:     i32  — 0=IP, 1=OOP
node_pots[N]:        f64  — pot at each node
node_num_actions[N]: i32  — number of children
node_first_child[N]: i32  — index into children_ids
children_ids[E]:     i32  — flat child node IDs, ordered by _actions_tuple
```

### Info-Set Mapping

Python's dict-based `_fast_info_map[(node_int_id, combo_idx)] → info_idx` is serialized to a flat array:

```
info_map[N × max_combos]: i32 → info_idx  (or -1 for invalid)
```

### Equity Table

Precomputed showdown equities are packed into a 2D array:

```
equity_table[num_ip × num_oop]: f64 → IP equity (0.0, 0.5, or 1.0)
```

### Rust Traversal

The Rust function `cfr_iterate()` receives all arrays and performs **N iterations × M matchups × 2 traversals** in a single call:

```python
convergence = poker_core.cfr_iterate(
    node_types, node_players, node_pots, node_num_actions,
    node_first_child, children_ids,
    info_map, max_combos,
    regrets,          # mutated in-place
    strategy_sums,    # mutated in-place
    max_actions,
    equity_table, num_oop,
    matchup_ip, matchup_oop,
    num_iterations,
    root_node_id,
)
```

Regrets and strategy_sums are **mutated in-place** via `PyReadwriteArray1` — no data copies.

### Dispatch Logic

```
Flop-only + Rust available + no callbacks → Rust path
Turn/River OR no Rust OR callbacks → Python path (original loop)
```

## Performance Results

### Benchmark: 7 Scenarios

| Scenario | Python | Rust | Speedup | Convergence Match |
|----------|--------|------|---------|-------------------|
| AA vs KK (50 iter) | 0.426s | 0.027s | **15.6×** | ✅ Exact |
| QQ vs JJ (50 iter) | 0.654s | 0.048s | **13.7×** | ✅ Exact |
| AK vs QQ (100 iter) | 2.391s | 0.094s | **25.4×** | ✅ Exact |
| Broad 4×4 (50 iter) | 6.583s | 1.695s | **3.9×** | ✅ Exact |
| Wide 6×4 (50 iter) | 8.820s | 0.929s | **9.5×** | ✅ Exact |
| Multi-size 3 bets (50 iter) | 3.254s | 0.253s | **12.9×** | ✅ Exact |
| AA vs KK (200 iter) | 1.187s | 0.032s | **37.6×** | ✅ Exact |

**Average speedup: 16.9×**

### Why Speedup Varies

- **Narrow ranges** (AA vs KK): most time is in traversal → maximum speedup (15–37×)
- **Broad ranges** (4×4, 6×4): more time in equity precompute and Python setup → lower ratio (4–10×) but still significant absolute improvement
- **More iterations**: higher speedup because Rust amortizes serialization cost

### Strategy Values Match

All individual strategy values match Python to 3 decimal places across all tested scenarios. Sample:

```
node_0  AhAc  py=[bet_50:0.167, bet_100:0.167, check:0.667]
                rs=[bet_50:0.167, bet_100:0.167, check:0.667]  ✅
```

## Files Modified

### Rust Crate
| File | Change |
|------|--------|
| `BackEnd/rust_core/Cargo.toml` | Added `numpy = "0.24"` dependency |
| `BackEnd/rust_core/src/cfr.rs` | **[NEW]** Core CFR+ traversal on flat arrays (275 lines) |
| `BackEnd/rust_core/src/lib.rs` | Added `cfr_iterate()` PyO3 function with zero-copy numpy |

### Python Integration
| File | Change |
|------|--------|
| `BackEnd/app/solver/cfr_solver.py` | Added `_should_use_rust_cfr()`, `_serialize_tree_for_rust()`, `_run_iterations_rust()`, `_run_iterations_python()`. Dispatch in `solve()`. |
| `BackEnd/app/tests/test_phase13a.py` | Updated version assertion |

### Tests & Benchmarks
| File | Change |
|------|--------|
| `BackEnd/app/tests/test_phase13b.py` | **[NEW]** 27 tests across 7 categories |
| `BackEnd/benchmark_13b.py` | **[NEW]** Comprehensive Python vs Rust benchmark |

## Verification

### Test Results

| Suite | Result |
|-------|--------|
| test_phase13b.py | **27/27 passed** |
| Full regression | **941 passed, 0 failed, 5 skipped** |
| Rust cargo test | **14/14 passed** |

### Browser Verification

Solver page loads, runs flop-only solve with Rust path, returns correct strategy recommendations. Dashboard fully functional.

### Canonical Regression

Convergence for AA vs KK at 50 iterations: **0.215773** — exact match with all previous phases.

## Design Decisions

1. **Flop-only scope**: Turn/river have chance nodes requiring card-string branching, not yet worth the complexity. Flop-only covers the common fast-solve use case.

2. **Array-of-structs → struct-of-arrays**: Serialized as 6 parallel arrays rather than one array of node structs. Better cache locality, simpler PyO3 binding.

3. **Fixed-size strategy buffer**: `[f64; 16]` stack array for strategy computation. No heap allocation in the hot path. 16 actions is more than enough (typical trees have 3–7).

4. **Callback fallback**: When `cancel_check` or `progress_callback` are provided, Python loop is used. This matches the API contract without FFI complexity.

5. **Version bump**: `poker_core` 0.1.0 → 0.2.0.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Rust/Python array mismatch | Exact convergence verification against Python baseline |
| Stack overflow on deep trees | 16-action fixed buffer; trees are bounded by MAX_TREE_NODES |
| Turn/River regression | Explicit fallback path; turn tests pass |
| Callback consumers (UI, jobs) | Callback presence triggers Python path automatically |

## Next Steps

1. **Phase 13C**: Extend Rust traversal to turn solves (add chance-node handling in Rust)
2. **Batch equity in traversal**: Inline equity lookup instead of table access for turn/river
3. **Parallelism**: Per-matchup parallelism within Rust iterations (rayon)
4. **WASM/SIMD**: Auto-vectorized regret updates
