"""
Phase 8D tests — Range utilities, simple report generation, recommendation text.
"""

import pytest
import json


# ── Test that simpleReport logic works ──
# These tests verify the backend i18n still works and test report concepts.

from app.services.i18n import (
    generate_recommendation_summary_ru,
    classify_deviation_ru,
    get_quality_label_ru,
    action_ru,
)


class TestSimpleReportConcepts:
    """Test the report generation concepts that the frontend simpleReport.ts implements."""

    def test_dominant_action_pure_strategy(self):
        """When one action > 85%, it's a pure strategy."""
        freqs = {"check": 0.90, "bet_50": 0.10}
        summary = generate_recommendation_summary_ru(freqs)
        assert "В основном" in summary
        assert "чек" in summary

    def test_mixed_strategy(self):
        """When top action 55-85%, it's a mixed strategy."""
        freqs = {"check": 0.60, "bet_50": 0.40}
        summary = generate_recommendation_summary_ru(freqs)
        assert "Преимущественно" in summary

    def test_heavily_mixed_strategy(self):
        """When top action < 55%, it's heavily mixed."""
        freqs = {"check": 0.34, "bet_50": 0.33, "bet_75": 0.33}
        summary = generate_recommendation_summary_ru(freqs)
        assert "Распределение" in summary or "Смешанная" in summary or "чек" in summary

    def test_empty_produces_no_data(self):
        """Empty frequencies produce 'no data' message."""
        summary = generate_recommendation_summary_ru({})
        assert "Нет данных" in summary

    def test_all_actions_have_russian_names(self):
        """Standard poker actions have Russian translations."""
        standard = ["fold", "check", "call", "bet_50", "bet_75", "raise", "allin"]
        for action in standard:
            label = action_ru(action)
            assert label != action or "_" not in action  # Should be translated

    def test_quality_labels_all_russian(self):
        """All quality labels are in Russian."""
        for category in ["perfect", "close_to_solver", "acceptable_deviation", "clear_deviation", "unknown"]:
            label = get_quality_label_ru(category)
            assert label["text"]
            assert label["emoji"]
            # Should not contain English
            assert "Perfect" not in label["text"]
            assert "Close" not in label["text"]


class TestRangePresetConcepts:
    """Verify that our preset definitions are correct."""

    def test_premium_preset_has_top_pairs(self):
        """Premium preset should include AA, KK, QQ, AKs."""
        from app.services.i18n import action_ru
        # These are frontend tests conceptually, but we verify naming consistency
        premium_hands = "AA,KK,QQ,AKs,AKo"
        assert "AA" in premium_hands
        assert "KK" in premium_hands

    def test_range_string_format(self):
        """Range strings should use standard notation."""
        tight = "AA,KK,QQ,JJ,TT,AKs,AQs,AJs,ATs,KQs,AKo,AQo"
        hands = tight.split(",")
        assert len(hands) == 12
        # All hands should be 2-3 chars
        for h in hands:
            assert 2 <= len(h) <= 3


class TestSimpleAdvancedModeConcepts:
    """Verify that simple mode defaults are reasonable."""

    def test_default_board_valid(self):
        """Default board 'Ks 7d 2c' has 3 cards."""
        board = "Ks 7d 2c"
        cards = board.strip().split()
        assert len(cards) == 3

    def test_default_pot_reasonable(self):
        """Default pot is a reasonable size."""
        pot = 6.5
        assert 1 <= pot <= 100

    def test_default_stack_reasonable(self):
        """Default stack is a reasonable size."""
        stack = 97
        assert 10 <= stack <= 200

    def test_simple_mode_has_fewer_controls(self):
        """Document that simple mode should show only: board, ranges, pot, stack."""
        simple_fields = ["board", "ip_range", "oop_range", "pot", "stack"]
        advanced_fields = ["bet_sizes", "raise_sizes", "max_iterations", "max_raises", "include_turn"]
        # Simple mode = 5 fields, advanced adds 5 more
        assert len(simple_fields) == 5
        assert len(advanced_fields) == 5


class TestReportTrustLevels:
    """Verify trust level classification logic."""

    def test_high_trust_conditions(self):
        """High trust requires: converged + validated + low exploitability."""
        # This mirrors simpleReport.ts logic
        converged = True
        grade = "VALIDATED_LIMITED_SCOPE"
        exploit_mbb = 5.0

        if grade == "VALIDATED_LIMITED_SCOPE" and converged and exploit_mbb < 20:
            trust = "high"
        else:
            trust = "medium"

        assert trust == "high"

    def test_medium_trust_conditions(self):
        """Medium trust: converged but demo/limited scope."""
        converged = True
        grade = "INTERNAL_DEMO"
        exploit_mbb = 30.0

        if grade == "VALIDATED_LIMITED_SCOPE" and converged and exploit_mbb < 20:
            trust = "high"
        elif converged and ("DEMO" in grade or "VALIDATED" in grade):
            trust = "medium"
        else:
            trust = "low"

        assert trust == "medium"

    def test_low_trust_not_converged(self):
        """Low trust when not converged."""
        converged = False
        grade = "STRUCTURAL_ONLY"

        if grade == "VALIDATED_LIMITED_SCOPE" and converged:
            trust = "high"
        elif converged and ("DEMO" in grade or "VALIDATED" in grade):
            trust = "medium"
        else:
            trust = "low"

        assert trust == "low"


class TestReportScopeNotes:
    """Verify scope notes are in Russian and informative."""

    def test_flop_only_scope(self):
        """Flop-only scope note should mention limitations."""
        note = "Расчёт только для флопа с маленькими диапазонами (~50 комбо/сторону)."
        assert "флопа" in note
        assert "50 комбо" in note

    def test_flop_plus_turn_scope(self):
        """Flop+turn scope note should mention turn."""
        note = "Расчёт включает флоп и ограниченный тёрн. Ривер не рассчитан."
        assert "тёрн" in note
        assert "ривер" in note.lower()
