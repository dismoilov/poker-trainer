# Phase 15B Report: Rust Solver Observability — Progress & Cancellation

**Date:** 2026-04-06  
**Status:** ✅ COMPLETE  
**Architect:** Claude Opus 4.6

---

## 1. Executive Summary

Phase 15B eliminates the last major Python-dependent operational gap in the solver's execution lifecycle. Before this phase, providing a `progress_callback` or `cancel_check` to the solver forced a fallback from the proven Rust CFR+ engine to the slower Python loop — negating all performance gains from Phases 13A–15A.

**After Phase 15B:**
- Progress reporting and cooperative cancellation work **natively on the Rust path**
- **Zero fallback to Python** for any bounded workload
- **Negligible overhead** (< 1% measured)
- **No correctness impact** — strategies remain deterministically identical

---

## 2. Problem Statement

| Before 15B | After 15B |
|---|---|
| `cancel_check` → Python fallback | `cancel_check` → Rust chunked iteration |
| `progress_callback` → Python fallback | `progress_callback` → Rust chunked iteration |
| Long solves: no progress UX | Progress updates every 25 iterations |
| No way to stop a running Rust solve | Cooperative cancel between chunks |
| Python fallback: **5–50× slower** | Rust path: full speed retained |

---

## 3. Architecture

### 3.1 Design: Chunked Iteration

The key insight: numpy arrays are GIL-protected and cannot be shared between Python threads and Rust's `py.allow_threads()` context simultaneously. A threading approach with shared control arrays was prototyped and **rejected** because writes from Python's polling thread are deferred until the GIL is re-acquired — making real-time cancel impossible.

**Chosen design: Chunked iteration**

```
┌─────────────────────────────────────────────────┐
│              Python solve() loop                 │
│                                                  │
│  while completed < max_iterations:               │
│    ├── check cancel_check() → break if True     │
│    ├── call Rust cfr_iterate(chunk=25 iters)    │
│    ├── completed += chunk                        │
│    └── call progress_callback(completed, total)  │
│                                                  │
│  No control needed? → single cfr_iterate(all)   │
└─────────────────────────────────────────────────┘
```

### 3.2 Control Model

| Parameter | Description |
|---|---|
| `cancel_check` | Callable returning `True` to cancel. Checked **between chunks** |
| `progress_callback(done, total)` | Called after each chunk with iteration count |
| Chunk size | 25 iterations (balances responsiveness vs overhead) |
| Cancel granularity | ≤ 25 iterations (worst case: one extra chunk) |
| Progress granularity | Every 25 iterations |

### 3.3 Two Paths

| Condition | Path | Overhead |
|---|---|---|
| No callbacks | Single `cfr_iterate(all)` call | **Zero** |
| With callbacks | Chunked `cfr_iterate(25)` calls | **< 1%** |

---

## 4. Changes Made

### 4.1 Rust Engine (`rust_core/src/cfr.rs`)

- **NEW:** `cfr_iterate_with_control()` — iteration loop with shared `i32` control array
  - `control[0]` = iterations completed (Rust writes)
  - `control[1]` = cancel flag (Rust reads between iterations)
  - Returns `(convergence, actual_iterations)` tuple
  - Cancel check has zero overhead inside the hot traversal path

### 4.2 PyO3 Bindings (`rust_core/src/lib.rs`)

- **NEW:** `cfr_iterate_with_control` PyO3 function with GIL release
- **UPDATED:** Version to `0.6.0 (Phase 15B: progress/cancel control)`
- **UPDATED:** Module registration to include new function

### 4.3 Python Solver (`solver/cfr_solver.py`)

- **UPDATED:** `_should_use_rust_cfr()` — removed Python fallback for callbacks
- **UPDATED:** `_run_iterations_rust()` — added `cancel_check`, `progress_callback` parameters
  - When callbacks present: chunked iteration (25 iterations per call)
  - When no callbacks: original single-call path (zero overhead)
- **UPDATED:** `solve()` call site — passes callbacks to Rust path

### 4.4 Test Updates

- **NEW:** `test_phase15b.py` — 17 tests across 6 categories
- **UPDATED:** `test_phase13a.py` — version check compatibility
- **UPDATED:** `test_phase13b.py` — version check compatibility
- **UPDATED:** `test_phase13c.py` — version check + dispatch test (callbacks → Rust, not Python)
- **UPDATED:** `test_phase13d.py` — version check + dispatch tests
- **UPDATED:** `test_phase14b.py` — `**kwargs` for monkey-patched runners

---

## 5. Benchmark Results

### 5.1 Overhead: No-Control vs With-Progress

| Scenario | No-ctrl | Progress | Overhead |
|---|---|---|---|
| AA vs KK flop 200i | 0.016s | 0.012s | −25.0% (noise) |
| 3×3 pairs flop 200i | 0.152s | 0.113s | −25.8% (noise) |
| Realistic flop 200i | 0.311s | 0.308s | −0.9% |
| Wide flop 100i | 0.841s | 0.847s | +0.7% |
| Realistic turn 50i | 2.247s | 2.222s | −1.1% |

**Conclusion:** Overhead is within measurement noise. The chunked approach adds essentially zero cost because each Python↔Rust transition costs < 0.1ms, and only 4–8 transitions occur per solve.

### 5.2 Cancel Effectiveness

| Scenario | Requested | Completed | Time Saved |
|---|---|---|---|
| 5000 iter, cancel@50 | 5000 | 50 | ~99% |
| Strategy valid after cancel | ✅ | — | — |
| Convergence metric valid | ✅ | — | — |

### 5.3 Progress Accuracy

| Scenario | Updates | First | Last |
|---|---|---|---|
| 200 iter turn solve | 8 | 25/200 | 200/200 |
| 100 iter flop solve | 4 | 25/100 | 100/100 |

---

## 6. Test Results

### 6.1 Phase 15B Tests (17/17 PASS)

| Category | Tests | Status |
|---|---|---|
| Progress Reporting | 4 | ✅ |
| Cancellation | 4 | ✅ |
| No Corruption | 1 | ✅ |
| Rust Path Used | 2 | ✅ |
| Rust API | 2 | ✅ |
| Regression | 4 | ✅ |

### 6.2 Full Regression (184/184 PASS)

| Suite | Tests | Status |
|---|---|---|
| Phase 13A | 23 | ✅ |
| Phase 13B | 36 | ✅ |
| Phase 13C | 38 | ✅ |
| Phase 13D | 34 | ✅ |
| Phase 14B | 15 | ✅ |
| Phase 15A | 21 | ✅ |
| Phase 15B | 17 | ✅ |
| **Total** | **184** | **✅ ALL PASS** |

---

## 7. Verification Results

| Check | Result |
|---|---|
| Normal solve (no control) | ✅ 100 iters, conv=0.8708 |
| Solve with progress | ✅ 200 iters, 8 progress updates |
| Solve with cancel | ✅ 50/5000 iters, strategies valid |
| Deterministic equivalence | ✅ Strategies match exactly |
| Rust version | ✅ poker_core 0.6.0 (Phase 15B) |
| cfr_iterate_with_control API | ✅ Available |

---

## 8. What Was Tried and Rejected

### 8.1 Threading + Shared Control Array (Rejected)

**Approach:** Pass a numpy `int32[2]` array to Rust. Rust writes `control[0]` = progress, Python background thread writes `control[1]` = cancel flag.

**Why it failed:** When Rust borrows the numpy array via `as_slice_mut()` inside `py.allow_threads()`, the GIL is released. However, Python's background thread cannot write to the numpy array because it's still borrowed by Rust. The write is deferred until the Rust call completes — making cancel impossible.

**The Rust `cfr_iterate_with_control` function was still added** to the crate (it works for Rust-only consumers) but is not used by the Python integration. The chunked approach solved both progress and cancel without it.

### 8.2 Why Chunked Iteration is Superior

1. **Simple:** No threading, no shared memory, no unsafe synchronization
2. **Correct:** Cancel/progress checked on the Python side where the GIL is held
3. **Zero overhead:** 25-iteration chunks = 4–8 Python↔Rust transitions per solve
4. **Reliable:** No race conditions possible

---

## 9. PM Recommendations

### 9.1 Immediate Value

- **Progress bars in UI:** The frontend can now display real-time progress during solves by passing a callback through the API layer
- **Cancel buttons:** Long-running solves can be stopped cleanly with valid partial results
- **No performance trade-off:** Users get observability for free

### 9.2 Next Steps

| Priority | Item | Rationale |
|---|---|---|
| High | Wire progress/cancel to WebSocket or SSE in the API layer | Enable real-time UI feedback |
| Medium | Memory profiling for 100+ combo ranges | Current `info_map` scales linearly |
| Low | Adaptive chunk sizing | Scale chunk based on iteration speed (fast = bigger chunks) |

---

## 10. Files Modified

| File | Change |
|---|---|
| `rust_core/src/cfr.rs` | Added `cfr_iterate_with_control` |
| `rust_core/src/lib.rs` | Added PyO3 binding, updated version to 0.6.0 |
| `solver/cfr_solver.py` | Removed Python fallback, chunked iteration dispatcher |
| `tests/test_phase15b.py` | **NEW** — 17 tests |
| `tests/test_phase13a.py` | Version compatibility |
| `tests/test_phase13b.py` | Version compatibility |
| `tests/test_phase13c.py` | Version + dispatch compatibility |
| `tests/test_phase13d.py` | Version + dispatch compatibility |
| `tests/test_phase14b.py` | Signature compatibility (`**kwargs`) |
| `docs/phase15b_report.md` | **NEW** — This report |
