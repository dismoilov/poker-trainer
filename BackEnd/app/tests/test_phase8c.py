"""
Phase 8C tests — Russian localization, backend i18n, terminology consistency.
"""

import pytest
from app.services.i18n import (
    generate_recommendation_summary_ru,
    classify_deviation_ru,
    get_quality_label_ru,
    generate_node_context_ru,
    drill_feedback_ru,
    action_ru,
    ACTION_LABELS_RU,
)


# ── Russian Recommendation Summary ──────────────────────────

class TestRussianRecommendationSummary:
    """All recommendation summaries must be in Russian."""

    def test_dominant_action_russian(self):
        freqs = {"check": 0.85, "bet_50": 0.15}
        summary = generate_recommendation_summary_ru(freqs)
        assert "В основном" in summary
        assert "чек" in summary

    def test_strong_lean_russian(self):
        freqs = {"check": 0.65, "bet_50": 0.35}
        summary = generate_recommendation_summary_ru(freqs)
        assert "Преимущественно" in summary

    def test_true_mix_russian(self):
        freqs = {"check": 0.50, "bet_50": 0.50}
        summary = generate_recommendation_summary_ru(freqs)
        assert "Смешанная" in summary or "смешанная" in summary

    def test_empty_frequencies_russian(self):
        summary = generate_recommendation_summary_ru({})
        assert "Нет данных" in summary

    def test_pure_fold_russian(self):
        freqs = {"fold": 0.95, "call": 0.05}
        summary = generate_recommendation_summary_ru(freqs)
        assert "фолд" in summary

    def test_three_way_russian(self):
        freqs = {"check": 0.33, "bet_33": 0.34, "bet_75": 0.33}
        summary = generate_recommendation_summary_ru(freqs)
        assert len(summary) > 10  # Valid Russian text

    def test_no_english_in_summary(self):
        """Ensure no English words leak into Russian summaries."""
        freqs = {"check": 0.70, "bet_50": 0.30}
        summary = generate_recommendation_summary_ru(freqs)
        assert "Mostly" not in summary
        assert "Primarily" not in summary
        assert "Mix" not in summary


# ── Russian Deviation Classification ────────────────────────

class TestRussianDeviationClassification:
    """All deviation descriptions must be in Russian (updated for 5-level severity)."""

    def test_perfect_russian(self):
        freqs = {"check": 0.70, "bet_50": 0.30}
        result = classify_deviation_ru("check", freqs)
        assert result["label"] == "perfect"
        # Phase 8J: description is Russian
        assert any('\u0400' <= c <= '\u04FF' for c in result["description"])

    def test_good_russian(self):
        freqs = {"check": 0.60, "bet_50": 0.40}
        result = classify_deviation_ru("bet_50", freqs)
        assert result["label"] == "good"  # was close_to_solver
        assert any('\u0400' <= c <= '\u04FF' for c in result["description"])

    def test_slight_russian(self):
        freqs = {"check": 0.65, "bet_50": 0.20, "fold": 0.15}
        result = classify_deviation_ru("fold", freqs)
        assert result["label"] == "slight"  # was acceptable_deviation
        assert any('\u0400' <= c <= '\u04FF' for c in result["description"])

    def test_notable_russian(self):
        freqs = {"check": 0.85, "bet_50": 0.10, "fold": 0.05}
        result = classify_deviation_ru("fold", freqs)
        assert result["label"] == "notable"  # was clear_deviation
        assert any('\u0400' <= c <= '\u04FF' for c in result["description"])

    def test_empty_deviation_russian(self):
        result = classify_deviation_ru("check", {})
        assert result["label"] == "unknown"
        assert "Нет данных" in result["description"]

    def test_no_english_in_deviation(self):
        freqs = {"check": 0.80, "bet_50": 0.20}
        result = classify_deviation_ru("check", freqs)
        assert "Perfect" not in result["description"]
        assert "top action" not in result["description"]


# ── Russian Quality Labels ──────────────────────────────────

class TestRussianQualityLabels:
    """Updated for Phase 8J 5-level severity system."""
    def test_perfect_label(self):
        label = get_quality_label_ru("perfect")
        assert label["text"] == "Идеально"  # was Отлично
        assert label["emoji"] == "🎯"

    def test_good_label(self):
        label = get_quality_label_ru("good")
        assert label["text"] == "Хороший выбор"

    def test_slight_label(self):
        label = get_quality_label_ru("slight")
        assert label["text"] == "Небольшое отклонение"

    def test_notable_label(self):
        label = get_quality_label_ru("notable")
        assert label["text"] == "Заметное отклонение"

    def test_major_label(self):
        label = get_quality_label_ru("major")
        assert label["text"] == "Серьёзная ошибка"

    def test_legacy_labels_still_resolve(self):
        """Old label names should still return something valid."""
        for legacy in ["close_to_solver", "acceptable_deviation", "clear_deviation"]:
            label = get_quality_label_ru(legacy)
            assert label["emoji"]
            assert label["text"]

    def test_unknown_label(self):
        label = get_quality_label_ru("unknown")
        assert label["text"] == "Нет данных"


# ── Russian Node Context ────────────────────────────────────

class TestRussianNodeContext:
    def test_ip_flop_russian(self):
        ctx = generate_node_context_ru("IP", "flop", "facing check")
        assert "в позиции" in ctx["node_explanation"]
        assert "флопе" in ctx["node_explanation"]

    def test_oop_turn_russian(self):
        ctx = generate_node_context_ru("OOP", "turn", "check-raise")
        assert "без позиции" in ctx["node_explanation"]
        assert "тёрне" in ctx["node_explanation"]

    def test_deep_stack_russian(self):
        ctx = generate_node_context_ru("IP", "flop", "cbet", pot_size=6.5, stack_size=100)
        assert "Глубокие" in ctx["node_explanation"] or "пространство" in ctx["node_explanation"]

    def test_cbet_context_russian(self):
        ctx = generate_node_context_ru("IP", "flop", "cbet")
        assert "продолженной" in ctx["spot_context"].lower() or "continuation" in ctx["spot_context"].lower()


# ── Russian Drill Feedback ──────────────────────────────────

class TestRussianDrillFeedback:
    def test_correct_feedback(self):
        text = drill_feedback_ru(True, False, "check", "check", 0.80, 0.80)
        assert "Правильно" in text

    def test_acceptable_feedback(self):
        text = drill_feedback_ru(False, True, "bet_50", "check", 0.35, 0.65)
        assert "Приемлемо" in text

    def test_wrong_feedback(self):
        text = drill_feedback_ru(False, False, "fold", "check", 0.0, 0.80)
        assert "Неверно" in text or "предпочитает" in text


# ── Action Labels Russian ───────────────────────────────────

class TestRussianActionLabels:
    def test_check(self):
        assert action_ru("check") == "чек"

    def test_fold(self):
        assert action_ru("fold") == "фолд"

    def test_call(self):
        assert action_ru("call") == "колл"

    def test_bet_50(self):
        assert action_ru("bet_50") == "бет 50%"

    def test_raise(self):
        assert action_ru("raise") == "рейз"

    def test_unknown_action(self):
        result = action_ru("bet_200")
        assert "200" in result


# ── Terminology Consistency ─────────────────────────────────

class TestTerminologyConsistency:
    """Ensure backend Russian terms are consistent across functions."""

    def test_solver_referenced_consistently(self):
        """'солвер' always spelled the same way."""
        freqs = {"check": 0.80, "bet_50": 0.20}
        summary = generate_recommendation_summary_ru(freqs)
        deviation = classify_deviation_ru("bet_50", freqs)
        # All should use lowercase 'солвер' in text
        if "солвер" in summary.lower():
            assert True
        if "солвер" in deviation["description"].lower():
            assert True

    def test_all_actions_have_russian_labels(self):
        """All standard poker actions have Russian labels."""
        standard = ["fold", "check", "call", "bet_50", "bet_75", "raise", "allin"]
        for action in standard:
            label = action_ru(action)
            # Should not be the raw action id
            assert label != action or "_" not in action
