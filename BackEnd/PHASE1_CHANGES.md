# Phase 1 Changes

## What Changed

### New: Poker Engine (`app/poker_engine/`)
8 new files implementing a pure-logic poker engine:
- Card/Deck primitives, legal action generation
- Immutable GameState with state transitions
- 5-card hand evaluator (high card through straight flush)
- Showdown winner determination

### New: Solver Abstraction (`app/solver/`)
4 new files defining a clean strategy provider interface:
- `StrategyProvider` abstract base class
- `HeuristicProvider` wrapping existing frequency tables
- `RealSolverProvider` scaffold (raises NotImplementedError)
- Refactored job runner using provider interface

### New: Game Sessions (`app/game_sessions/`)
4 new files for live playable poker:
- DB models for sessions and hand records
- Session lifecycle service with villain auto-play
- REST API: create session, take action, next hand, history

### New: Frontend Play Page
- `/play` route with full poker table UI
- Green felt table, hero/villain seats, card rendering
- Action buttons, bet sizing, hand history sidebar
- TypeScript types and API client methods

### Modified: Legacy Honesty
- `services/strategy.py`: Docstring corrected to "Heuristic (NOT a real solver)"
- `services/jobs.py`: Uses `HeuristicProvider` via interface; log messages updated

### New: Tests
- `test_poker_engine.py`: 30+ tests
- `test_solver_providers.py`: 14 tests
- `test_game_sessions.py`: 7 tests

## What Did NOT Change
- Drill/Explore/Analytics/Library — fully backward compatible
- Database schema — new tables added, existing tables untouched
- Auth system — unchanged
- Frontend routing — new route added, existing routes unchanged
