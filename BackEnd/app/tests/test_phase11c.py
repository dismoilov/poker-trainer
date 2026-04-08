"""
Phase 11C tests: River preset integration, expanded abstraction, guardrails.
"""
import pytest
from app.solver.cfr_solver import CfrSolver, SolveRequest, validate_solve_request
from app.solver.tree_builder import TreeConfig, build_tree_skeleton


# ── Deep preset integration ──────────────────────────────────────

class TestDeepPresetRiver:
    """Tests for river integration in the 'deep' preset."""

    def test_deep_preset_has_river_fields(self):
        """Deep preset must include river configuration."""
        from app.api.routes_solver import SOLVER_PRESETS
        deep = SOLVER_PRESETS["deep"]
        assert deep["include_river"] is True
        assert deep["max_river_cards"] == 2
        assert deep["river_bet_sizes"] == [0.33, 0.5, 1.0]
        assert deep["river_raise_sizes"] == [2.5]
        assert deep["river_max_raises"] == 2

    def test_fast_preset_no_river(self):
        """Fast preset must NOT include river."""
        from app.api.routes_solver import SOLVER_PRESETS
        fast = SOLVER_PRESETS["fast"]
        assert fast.get("include_river", False) is False

    def test_standard_preset_no_river(self):
        """Standard preset must NOT include river."""
        from app.api.routes_solver import SOLVER_PRESETS
        std = SOLVER_PRESETS["standard"]
        assert std.get("include_river", False) is False

    def test_deep_preset_solves_with_river(self):
        """Deep preset config must produce a valid river-enabled solve."""
        from app.api.routes_solver import SOLVER_PRESETS
        p = SOLVER_PRESETS["deep"]
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=p["bet_sizes"],
            raise_sizes=p["raise_sizes"],
            max_iterations=50,  # reduced for test speed
            max_raises=p["max_raises"],
            deterministic=True,
            include_turn=p["include_turn"],
            max_turn_cards=p["max_turn_cards"],
            turn_bet_sizes=p["turn_bet_sizes"],
            turn_raise_sizes=p["turn_raise_sizes"],
            turn_max_raises=p["turn_max_raises"],
            include_river=p["include_river"],
            max_river_cards=p["max_river_cards"],
            river_bet_sizes=p["river_bet_sizes"],
            river_raise_sizes=p["river_raise_sizes"],
            river_max_raises=p["river_max_raises"],
        ))
        assert output.metadata["street_depth"] == "flop_plus_turn_plus_river"
        assert output.metadata["include_river"] is True
        assert output.metadata["river_bet_sizes"] == [0.33, 0.5, 1.0]
        assert output.metadata["river_max_raises"] == 2


# ── Expanded river abstraction ───────────────────────────────────

class TestExpandedRiverAbstraction:
    """Tests for the 11C expanded river abstraction (3 bets, 1 raise)."""

    def test_three_river_bet_sizes(self):
        """Tree with 3 river bet sizes should have more nodes than 2."""
        config_2 = TreeConfig(
            starting_pot=10.0, effective_stack=50.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5, 1.0), flop_raise_sizes=(),
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            river_bet_sizes_override=(0.5, 1.0),
            river_raise_sizes_override=(),
            river_max_raises=2,
        )
        config_3 = TreeConfig(
            starting_pot=10.0, effective_stack=50.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5, 1.0), flop_raise_sizes=(),
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            river_bet_sizes_override=(0.33, 0.5, 1.0),
            river_raise_sizes_override=(),
            river_max_raises=2,
        )
        _, stats_2 = build_tree_skeleton(config_2)
        _, stats_3 = build_tree_skeleton(config_3)
        assert stats_3.total_nodes > stats_2.total_nodes

    def test_river_raise_increases_nodes(self):
        """Adding 1 river raise should increase tree size."""
        config_no = TreeConfig(
            starting_pot=10.0, effective_stack=50.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5, 1.0), flop_raise_sizes=(),
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            river_bet_sizes_override=(0.33, 0.5, 1.0),
            river_raise_sizes_override=(),
            river_max_raises=2,
        )
        config_yes = TreeConfig(
            starting_pot=10.0, effective_stack=50.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5, 1.0), flop_raise_sizes=(),
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            river_bet_sizes_override=(0.33, 0.5, 1.0),
            river_raise_sizes_override=(2.5,),
            river_max_raises=2,
        )
        _, stats_no = build_tree_skeleton(config_no)
        _, stats_yes = build_tree_skeleton(config_yes)
        assert stats_yes.total_nodes > stats_no.total_nodes

    def test_expanded_solve_completes(self):
        """A solve with 3 bet sizes + 1 raise on river must complete."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[],
            max_iterations=30,
            max_raises=1,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
            turn_bet_sizes=[0.5],
            turn_raise_sizes=[],
            turn_max_raises=0,
            include_river=True,
            max_river_cards=2,
            river_bet_sizes=[0.33, 0.5, 1.0],
            river_raise_sizes=[2.5],
            river_max_raises=2,
        ))
        assert output.iterations == 30
        assert output.metadata["street_depth"] == "flop_plus_turn_plus_river"
        assert output.metadata["river_bet_sizes"] == [0.33, 0.5, 1.0]
        assert output.metadata["river_raise_sizes"] == [2.5]
        assert output.metadata["river_max_raises"] == 2

    def test_expanded_river_has_raise_strategies(self):
        """Solve with river raises should produce raise_ actions in strategies."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[],
            max_iterations=30,
            max_raises=1,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
            turn_bet_sizes=[0.5],
            turn_raise_sizes=[],
            turn_max_raises=0,
            include_river=True,
            max_river_cards=2,
            river_bet_sizes=[0.33, 0.5, 1.0],
            river_raise_sizes=[2.5],
            river_max_raises=2,
        ))
        # Check that at least one node has a raise action
        has_raise = False
        for node_id, combos in output.strategies.items():
            for combo_str, freqs in combos.items():
                for action in freqs.keys():
                    if action.startswith("raise"):
                        has_raise = True
                        break
        assert has_raise, "No raise actions found in expanded river strategies"


# ── Guardrails ───────────────────────────────────────────────────

class TestPhase11CGuardrails:
    """Tests for river-specific guardrails after 11C expansion."""

    def test_river_still_requires_turn(self):
        """River without turn must still be rejected."""
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            include_turn=False,
            include_river=True,
        )
        valid, error = validate_solve_request(req)
        assert not valid
        assert "turn" in error.lower()

    def test_river_combo_limit_still_enforced(self):
        """Wide ranges should still be rejected with river."""
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKs,AQs,AJs",
            oop_range="AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKs,AQs,AJs",
            pot=10.0,
            effective_stack=50.0,
            include_turn=True,
            max_turn_cards=2,
            include_river=True,
            max_river_cards=2,
        )
        valid, error = validate_solve_request(req)
        assert not valid
        assert "too large" in error.lower() or "combos" in error.lower()


# ── Regression ───────────────────────────────────────────────────

class TestPhase11CRegression:
    """Regression tests: flop-only and turn-only must still work."""

    def test_flop_only_unaffected(self):
        """Flop-only solve must still produce valid output."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            max_iterations=30,
            deterministic=True,
        ))
        assert output.metadata["street_depth"] == "flop_only"

    def test_turn_only_unaffected(self):
        """Turn-only solve must still produce valid output."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            max_iterations=30,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
        ))
        assert output.metadata["street_depth"] == "flop_plus_turn"
        assert output.metadata.get("include_river") is False
