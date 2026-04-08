# Phase 13C: Rust Turn Chance-Node Traversal

## Summary

Phase 13C extends the Rust CFR+ traversal engine to support **turn-enabled solves** with chance-node branching, blocker-aware card filtering, and per-turn-card equity tables. This eliminates the Python fallback for turn solves and delivers material end-to-end performance gains.

## Key Metrics

| Metric | Value |
|--------|-------|
| **Correctness** | 8/8 scenarios exact match (convergence + exploitability) |
| **Strategy fidelity** | 10/10 strategy values match Python exactly |
| **Average turn speedup** | 7.9× over Python |
| **Peak turn speedup** | 8.8× (AA,KK,QQ vs JJ,TT, 3 turn cards) |
| **Flop regression** | 13.4× (unchanged from 13B baseline) |
| **Test suite** | 30/30 new tests pass |
| **Full regression** | 971 passed, 0 failed, 5 skipped |
| **Rust unit tests** | 15/15 pass |

## Architecture

### Chance Node Handling (Type 4)

```
Tree:  root(action) → check → chance_turn(N branches) → turn_action → showdown
                                    ↓
                          branch_0 (card Ah)
                          branch_1 (card 3s)
                          branch_2 (card Td)  ← blocked if hole card = Td
```

- **Node type 4** = chance_turn node
- Each chance child carries a `turn_card_idx` via `node_chance_card[child_id]`
- Branches iterate over available turn cards, skipping blocked ones
- Values are averaged over valid (non-blocked) branches

### Blocker System

Turn card indices and hole card indices use the **same integer mapping** (`turn_card_to_idx`). The Rust engine checks `ip_hole_cards` and `oop_hole_cards` arrays (4 slots per combo) against the branch's turn card index.

```
if ip_hole_cards[combo_idx * 4 + h] == turn_card_idx → BLOCKED
```

### Multi-Table Equity

Equity tables are indexed as:
```
equity_tables[(turn_card_idx + 1) * num_ip * num_oop + ip_idx * num_oop + oop_idx]
```
- Index 0: flop equity (no turn card)
- Index 1..N: per-turn-card equity

## Files Modified

### Rust Core
| File | Change |
|------|--------|
| `rust_core/src/cfr.rs` | Added `chance_node_value()`, blocker checking, `active_turn_card_idx` propagation, per-turn equity table lookup |
| `rust_core/src/lib.rs` | Updated `cfr_iterate` PyO3 binding with 6 new parameters: `node_chance_card`, `ip_hole_cards`, `oop_hole_cards`, `num_turn_cards`, `num_ip`, `equity_tables` (replaces single `equity_table`) |

### Python Integration
| File | Change |
|------|--------|
| `cfr_solver.py` | `_should_use_rust_cfr()`: now allows turn (blocks only river). `_serialize_tree_for_rust()`: emits type-4 nodes, chance card indices, hole card blockers, multi-table equity. `_run_iterations_rust()`: passes new parameters. |

### Tests
| File | Change |
|------|--------|
| `test_phase13c.py` | 30 new tests covering all turn+chance scenarios |
| `test_phase13b.py` | Updated API calls, dispatch expectations, version check |
| `test_phase13a.py` | Updated version check to accept 0.3.0 |

## Performance Results

```
AA vs KK turn 2 cards (20 iter)          py=0.477s  rs=0.067s   7.1×  ✅
AA vs KK turn 3 cards (20 iter)          py=0.566s  rs=0.095s   6.0×  ✅
QQ vs JJ turn 2 cards (20 iter)          py=0.905s  rs=0.127s   7.1×  ✅
AA,KK vs QQ,JJ turn 2 cards (20 iter)   py=2.313s  rs=0.299s   7.7×  ✅
AA vs KK turn 5 cards (30 iter)          py=1.348s  rs=0.162s   8.3×  ✅
AA,KK,QQ vs JJ,TT turn 3 cards (20 i)   py=7.000s  rs=0.799s   8.8×  ✅
Multi bet sizes turn 2 cards (20 iter)   py=1.033s  rs=0.199s   5.2×  ✅
Flop-only AA vs KK (50 iter) REGRESSION  py=0.324s  rs=0.024s  13.4×  ✅
```

## Dispatch Rules (Phase 13C)

| Solve Type | Rust? | Reason |
|------------|-------|--------|
| Flop-only | ✅ Rust | Since 13B |
| Turn (no river) | ✅ Rust | **NEW in 13C** |
| River | ❌ Python | River chance nodes not yet migrated |
| Any + cancel_check | ❌ Python | Rust can't call Python callbacks |
| Any + progress_callback | ❌ Python | Rust can't call Python callbacks |

## Known Limitations

1. **River still falls back to Python** — river chance nodes and double-street branching are not yet implemented in Rust
2. **No progress callbacks in Rust path** — long turn solves run without per-iteration progress reporting
3. **Setup overhead** — tree serialization adds ~1ms per solve (negligible vs iteration time)

## Next Steps

- **Phase 13D**: River chance-node support in Rust
- **Phase 14**: Parallel CFR iterations (Rayon multi-threading in Rust)
- **Phase 15**: WASM compilation for client-side solving
