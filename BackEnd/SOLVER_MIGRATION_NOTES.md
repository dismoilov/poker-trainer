# Solver Migration Notes

## How to Integrate a Real Solver

### Step 1: Implement `StrategyProvider`

Edit `app/solver/real_provider.py`. The interface is defined in `app/solver/base.py`:

```python
class StrategyProvider(ABC):
    @property
    def provider_type(self) -> ProviderType: ...
    @property
    def supports_iterative(self) -> bool: ...
    def generate_strategy(self, node_id, actions, config=None) -> StrategyMatrix: ...
    def get_progress(self) -> SolveProgress: ...
    def cancel(self) -> None: ...
```

### Step 2: Input Contract

`SolveConfig` provides:
- `board`: List of card strings (e.g. `["Ks", "7d", "2c"]`)
- `ip_range` / `oop_range`: Preflop range strings
- `pot`, `ip_stack`, `oop_stack`: Game tree parameters
- `allowed_bet_sizes`, `allowed_raise_sizes`: Bet tree
- `max_iterations`, `target_exploitability`: Convergence

### Step 3: Output Contract

`generate_strategy()` must return `StrategyMatrix`:
```python
{
  "AA":  {"check": 0.1, "bet33": 0.3, "bet75": 0.6},
  "AKs": {"check": 0.2, "bet33": 0.4, "bet75": 0.4},
  # ... all 169 hands
}
```
- Keys: 169 hand labels (AA, AKs, AKo, ..., 22)
- Values: `{action_id: frequency}` normalized to sum=1.0
- Action IDs must match the `actions` parameter

### Step 4: Wire Up Provider Selection

Edit `app/solver/jobs.py`:
```python
def get_provider_for_job(job_type: str = "solve") -> StrategyProvider:
    if job_type == "real_solve":
        return RealSolverProvider()
    return HeuristicProvider()  # default fallback
```

### Step 5: Progress Reporting (Optional)

For iterative solvers, implement `get_progress()`:
```python
def get_progress(self) -> SolveProgress:
    return SolveProgress(
        iterations_done=self._iter,
        total_iterations=self._max_iter,
        exploitability=self._exploit,
        converged=self._exploit < self._target,
    )
```

### Recommended Solver Engines
- **PioSOLVER** — Commercial, C++ core, fast
- **GTO+** — Open format, good for research
- **Custom CFR+/DCFR** — Build from scratch using counterfactual regret minimization
- **OpenSpiel** — Google's game-solving framework (supports CFR)
