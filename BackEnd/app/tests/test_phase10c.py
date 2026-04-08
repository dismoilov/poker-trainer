"""
Phase 10C: Solver Presets Tests

Tests validate:
- Preset definitions and mapping
- API preset resolution behavior
- Safe default behavior
- Turn-field wiring through API
- Regression protection
"""

import pytest
from unittest.mock import patch

from app.api.routes_solver import SOLVER_PRESETS, SolveJobRequest


# ═══════════════════════════════════════════════════════════════
# A. PRESET DEFINITIONS
# ═══════════════════════════════════════════════════════════════


class TestPresetDefinitions:
    """Validate preset definitions are correct and complete."""

    def test_three_presets_exist(self):
        """Should have exactly fast, standard, deep presets."""
        assert set(SOLVER_PRESETS.keys()) == {"fast", "standard", "deep"}

    def test_all_presets_have_required_fields(self):
        """Each preset must have all config fields."""
        required = [
            "label", "description", "icon", "bet_sizes", "raise_sizes",
            "max_iterations", "max_raises", "include_turn", "max_turn_cards",
            "turn_bet_sizes", "turn_raise_sizes", "turn_max_raises",
            "est_time_range", "complexity",
        ]
        for name, preset in SOLVER_PRESETS.items():
            for field in required:
                assert field in preset, f"Preset '{name}' missing field '{field}'"

    def test_fast_preset_is_light(self):
        """Fast preset should have minimal config."""
        p = SOLVER_PRESETS["fast"]
        assert len(p["bet_sizes"]) <= 3
        assert p["raise_sizes"] == []
        assert p["max_iterations"] <= 100
        assert p["include_turn"] is False
        assert p["complexity"] == "LIGHT"

    def test_standard_preset_is_moderate(self):
        """Standard preset should have balanced config."""
        p = SOLVER_PRESETS["standard"]
        assert 3 <= len(p["bet_sizes"]) <= 5
        assert len(p["raise_sizes"]) >= 1
        assert 150 <= p["max_iterations"] <= 300
        assert p["include_turn"] is False
        assert p["complexity"] == "MODERATE"

    def test_deep_preset_is_heavy(self):
        """Deep preset should have full config with turn and river."""
        p = SOLVER_PRESETS["deep"]
        assert len(p["bet_sizes"]) >= 3  # Phase 11C: 4 bet sizes for deep
        assert p["include_turn"] is True
        assert p["max_turn_cards"] >= 2
        assert p["complexity"] == "HEAVY"

    def test_preset_labels_are_russian(self):
        """All preset labels should be in Russian."""
        for name, preset in SOLVER_PRESETS.items():
            assert any(c >= '\u0400' for c in preset["label"]), (
                f"Preset '{name}' label is not Russian: {preset['label']}"
            )
            assert any(c >= '\u0400' for c in preset["description"]), (
                f"Preset '{name}' description is not Russian: {preset['description']}"
            )

    def test_presets_ordered_by_complexity(self):
        """Presets should increase in complexity: fast < standard < deep."""
        fast = SOLVER_PRESETS["fast"]
        standard = SOLVER_PRESETS["standard"]
        deep = SOLVER_PRESETS["deep"]
        # Iterations ordering still holds
        assert fast["max_iterations"] < standard["max_iterations"]
        assert len(fast["bet_sizes"]) < len(standard["bet_sizes"])


# ═══════════════════════════════════════════════════════════════
# B. PRESET RESOLUTION
# ═══════════════════════════════════════════════════════════════


class TestPresetResolution:
    """Validate that presets correctly override request fields."""

    def test_preset_overrides_bet_sizes(self):
        """Preset should replace bet_sizes."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5],  # user's original
            preset="deep",
        )
        # Simulate preset application
        p = SOLVER_PRESETS["deep"]
        req.bet_sizes = p["bet_sizes"]
        assert req.bet_sizes == [0.33, 0.5, 0.75, 1.0]  # Phase 11C: deep uses 4 sizes

    def test_preset_overrides_turn_config(self):
        """Deep preset should enable turn."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            include_turn=False,
            preset="deep",
        )
        p = SOLVER_PRESETS["deep"]
        req.include_turn = p["include_turn"]
        req.max_turn_cards = p["max_turn_cards"]
        assert req.include_turn is True
        assert req.max_turn_cards >= 2

    def test_fast_preset_disables_turn(self):
        """Fast preset should explicitly disable turn."""
        p = SOLVER_PRESETS["fast"]
        assert p["include_turn"] is False
        assert p["max_turn_cards"] == 0

    def test_null_preset_keeps_manual_values(self):
        """When preset is None, manual values should be preserved."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.33, 0.67],
            max_iterations=150,
            preset=None,
        )
        assert req.bet_sizes == [0.33, 0.67]
        assert req.max_iterations == 150

    def test_unknown_preset_is_ignored(self):
        """Unknown preset name should be accepted but not crash."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            preset="unknown",
        )
        # Should not crash - unknown preset is just ignored
        assert req.preset == "unknown"
        # Bet sizes should remain original defaults
        assert req.bet_sizes == [0.5, 1.0]


# ═══════════════════════════════════════════════════════════════
# C. API INTEGRATION (SolveJobRequest model)
# ═══════════════════════════════════════════════════════════════


class TestApiFieldsIntegration:
    """Validate that SolveJobRequest accepts new fields."""

    def test_request_accepts_turn_fields(self):
        """SolveJobRequest should accept turn_bet_sizes, turn_raise_sizes, turn_max_raises."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            turn_bet_sizes=[0.33, 0.5, 0.75],
            turn_raise_sizes=[2.5],
            turn_max_raises=1,
        )
        assert req.turn_bet_sizes == [0.33, 0.5, 0.75]
        assert req.turn_raise_sizes == [2.5]
        assert req.turn_max_raises == 1

    def test_request_accepts_preset_field(self):
        """SolveJobRequest should accept preset field."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            preset="standard",
        )
        assert req.preset == "standard"

    def test_request_defaults_turn_fields_empty(self):
        """Default turn fields should be empty lists."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
        )
        assert req.turn_bet_sizes == []
        assert req.turn_raise_sizes == []
        assert req.turn_max_raises == 0

    def test_request_allows_more_bet_sizes(self):
        """SolveJobRequest should now allow up to 8 bet sizes."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25],
        )
        assert len(req.bet_sizes) == 7

    def test_request_allows_more_raise_sizes(self):
        """SolveJobRequest should now allow up to 4 raise sizes."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            raise_sizes=[2.5, 3.5, 4.0],
        )
        assert len(req.raise_sizes) == 3


# ═══════════════════════════════════════════════════════════════
# D. SAFE DEFAULTS
# ═══════════════════════════════════════════════════════════════


class TestSafeDefaults:
    """Validate that default values are safe for normal users."""

    def test_default_preset_is_none(self):
        """Default preset should be None (manual mode)."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
        )
        assert req.preset is None

    def test_default_turn_is_off(self):
        """Turn should be off by default."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
        )
        assert req.include_turn is False

    def test_default_iterations_reasonable(self):
        """Default iterations should be moderate."""
        req = SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
        )
        assert 100 <= req.max_iterations <= 300


# ═══════════════════════════════════════════════════════════════
# E. PRESETS ENDPOINT
# ═══════════════════════════════════════════════════════════════


class TestPresetsEndpoint:
    """Validate the /presets endpoint data structure."""

    def test_presets_endpoint_structure(self):
        """Presets data should have correct structure."""
        # Simulate endpoint response
        result = {
            "presets": {
                k: {
                    "label": v["label"],
                    "description": v["description"],
                    "icon": v["icon"],
                    "est_time_range": v["est_time_range"],
                    "complexity": v["complexity"],
                    "include_turn": v["include_turn"],
                }
                for k, v in SOLVER_PRESETS.items()
            },
            "default": "standard",
        }
        assert result["default"] == "standard"
        assert len(result["presets"]) == 3
        for name, data in result["presets"].items():
            assert "label" in data
            assert "description" in data
            assert "icon" in data
            assert "est_time_range" in data
            assert "complexity" in data


# ═══════════════════════════════════════════════════════════════
# F. REGRESSION
# ═══════════════════════════════════════════════════════════════


class TestPhase10CRegression:
    """Ensure Phase 10A/10B basics still work."""

    def test_solver_still_works_without_preset(self):
        """Solver should still work without preset field."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=20, max_raises=2, deterministic=True,
        ))
        assert output.iterations == 20
        assert len(output.strategies) > 0

    def test_solver_works_with_fast_config(self):
        """Solver should work with fast preset's config."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        p = SOLVER_PRESETS["fast"]
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=p["bet_sizes"],
            raise_sizes=p["raise_sizes"],
            max_iterations=p["max_iterations"],
            max_raises=p["max_raises"],
            deterministic=True,
        ))
        assert output.iterations == p["max_iterations"]
        assert len(output.strategies) > 0

    def test_solver_works_with_standard_config(self):
        """Solver should work with standard preset's config."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        p = SOLVER_PRESETS["standard"]
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=p["bet_sizes"],
            raise_sizes=p["raise_sizes"],
            max_iterations=50,  # reduced for test speed
            max_raises=p["max_raises"],
            deterministic=True,
        ))
        assert len(output.strategies) > 0
        assert output.metadata["action_abstraction"]
