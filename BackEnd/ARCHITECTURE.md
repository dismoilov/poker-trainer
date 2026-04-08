# Architecture Overview

## System Layers

```
┌──────────────────────────────────────────────┐
│                  Frontend (React)             │
│  Pages: Dashboard, Play, Drill, Explore,      │
│         Analytics, Library, Jobs, Guide        │
├──────────────────────────────────────────────┤
│              REST API (FastAPI)                │
│  /api/play, /api/drill, /api/explore,         │
│  /api/spots, /api/jobs, /api/analytics        │
├──────────────┬─────────────┬─────────────────┤
│ Game Sessions│   Solver    │   Trainer        │
│ (app/game_   │ Abstraction │   Services       │
│  sessions/)  │ (app/solver)│ (app/services/)  │
├──────────────┴──────┬──────┴─────────────────┤
│         Poker Engine (app/poker_engine/)       │
│   Cards, Deck, Actions, State, Transitions,   │
│   Hand Evaluation, Showdown                    │
├──────────────────────────────────────────────┤
│           Database (SQLite + SQLAlchemy)       │
└──────────────────────────────────────────────┘
```

## Module Descriptions

### `app/poker_engine/` — Pure Game Logic
Zero DB dependencies. Handles all poker rules:
- **types.py**: Rank, Suit, Street, ActionType, Position, HandCategory enums
- **cards.py**: Immutable Card value objects with parsing
- **deck.py**: 52-card Deck with shuffle/deal/remove
- **actions.py**: Legal action generation from game state
- **state.py**: Immutable GameState dataclass
- **transitions.py**: `apply_action()` state machine
- **hand_eval.py**: 5-card hand evaluator (combinatorial)
- **showdown.py**: Winner determination

### `app/solver/` — Strategy Provider Abstraction
Decouples strategy generation from consumers:
- **base.py**: Abstract `StrategyProvider` interface
- **heuristic_provider.py**: Wraps existing frequency-table logic
- **real_provider.py**: Scaffold for future real solver
- **jobs.py**: Alternative job runner using provider interface

### `app/game_sessions/` — Live Play
Manages playable poker sessions:
- **models.py**: GameSessionModel, HandRecordModel
- **schemas.py**: API request/response schemas
- **service.py**: Session lifecycle, villain AI, showdown
- **api.py**: REST endpoints under `/api/play/`

### `app/services/` — Trainer Services (Legacy)
Existing trainer functionality (unchanged behavior):
- **strategy.py**: Heuristic frequency generation (NOT a solver)
- **drill.py**: Question generation and answer processing
- **spots.py**: Spot CRUD and node tree generation
- **jobs.py**: Job management using solver interface
- **gto_data.py**: Hand tier tables, board textures
- **explanations.py**: Strategy explanation generation

## What Is Real vs Heuristic

| Component | Status |
|-----------|--------|
| Poker engine (cards, deck, showdown) | **Real** — correct game logic |
| Hand evaluator | **Real** — evaluates all hand categories |
| Game sessions (deal, fold, check) | **Real** — uses engine |
| Strategy frequencies (169-hand matrix) | **Heuristic** — lookup tables + jitter |
| Solver interface | **Real interface**, heuristic implementation |
| Real solver engine | **Not yet integrated** — scaffold only |
