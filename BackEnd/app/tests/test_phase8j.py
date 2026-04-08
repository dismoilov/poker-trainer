"""
Phase 8J Tests — 5-level severity, coaching messages, hand narrative, next steps.
"""
import pytest
from app.services.i18n import (
    classify_deviation_ru,
    get_quality_label_ru,
    _detect_is_mixed,
    _coaching_message,
)


# ── A. 5-Level Severity Classification ──

class TestSeverityLevels:
    """Test all 5 severity levels with representative frequencies."""

    def test_perfect_match(self):
        freqs = {"check": 0.70, "bet": 0.30}
        result = classify_deviation_ru("check", freqs)
        assert result["label"] == "perfect"
        assert result["severity_level"] == 1
        assert result["accuracy_pct"] == 100.0

    def test_good_choice(self):
        freqs = {"check": 0.55, "bet": 0.45}
        result = classify_deviation_ru("bet", freqs)
        assert result["label"] == "good"
        assert result["severity_level"] == 2
        assert result["user_freq"] == 0.45

    def test_slight_deviation(self):
        freqs = {"check": 0.70, "bet": 0.15, "fold": 0.15}
        result = classify_deviation_ru("bet", freqs)
        assert result["label"] == "slight"
        assert result["severity_level"] == 3

    def test_notable_deviation(self):
        freqs = {"check": 0.85, "bet": 0.10, "fold": 0.05}
        result = classify_deviation_ru("fold", freqs)
        assert result["label"] == "notable"
        assert result["severity_level"] == 4

    def test_major_mistake(self):
        freqs = {"check": 0.90, "bet": 0.09, "fold": 0.01}
        result = classify_deviation_ru("fold", freqs)
        assert result["label"] == "major"
        assert result["severity_level"] == 5

    def test_unknown_no_freqs(self):
        result = classify_deviation_ru("check", {})
        assert result["label"] == "unknown"
        assert result["severity_level"] == 0

    def test_zero_freq_major(self):
        """Action with 0% frequency should be major."""
        freqs = {"check": 0.80, "bet": 0.20}
        result = classify_deviation_ru("fold", freqs)
        assert result["label"] == "major"
        assert result["severity_level"] == 5
        assert result["user_freq"] == 0.0


# ── B. Coaching Messages ──

class TestCoachingMessages:

    def test_coaching_level_1(self):
        msg = _coaching_message(1, "чек", "чек", 0.70, 0.70, False)
        assert "Так держать" in msg

    def test_coaching_level_2_mixed(self):
        msg = _coaching_message(2, "ставка", "чек", 0.40, 0.60, True)
        assert "смешивает" in msg
        assert "допустимы" in msg

    def test_coaching_level_2_not_mixed(self):
        msg = _coaching_message(2, "ставка", "чек", 0.35, 0.65, False)
        assert "хороший выбор" in msg

    def test_coaching_level_3_mixed(self):
        msg = _coaching_message(3, "колл", "чек", 0.15, 0.70, True)
        assert "смешанной стратегии" in msg

    def test_coaching_level_3_not_mixed(self):
        msg = _coaching_message(3, "колл", "чек", 0.15, 0.70, False)
        assert "не основная линия" in msg

    def test_coaching_level_4(self):
        msg = _coaching_message(4, "фолд", "чек", 0.05, 0.80, False)
        assert "редко" in msg
        assert "разобраться" in msg

    def test_coaching_level_5(self):
        msg = _coaching_message(5, "фолд", "чек", 0.01, 0.85, False)
        assert "практически никогда" in msg
        assert "изучения" in msg

    def test_all_coaching_messages_are_russian(self):
        for level in range(1, 6):
            msg = _coaching_message(level, "чек", "ставка", 0.10, 0.70, False)
            assert any('\u0400' <= c <= '\u04FF' for c in msg), f"Level {level} not Russian: {msg}"


# ── C. Mixed Spot Detection ──

class TestMixedSpotDetection:

    def test_pure_spot(self):
        assert not _detect_is_mixed({"check": 0.90, "bet": 0.10})

    def test_mixed_spot(self):
        assert _detect_is_mixed({"check": 0.55, "bet": 0.45})

    def test_three_way_mixed(self):
        assert _detect_is_mixed({"check": 0.40, "bet": 0.35, "fold": 0.25})

    def test_dominant_not_mixed(self):
        assert not _detect_is_mixed({"check": 0.70, "bet": 0.30})

    def test_empty(self):
        assert not _detect_is_mixed({})

    def test_single_action(self):
        assert not _detect_is_mixed({"check": 1.0})

    def test_is_mixed_in_deviation_response(self):
        freqs = {"check": 0.55, "bet": 0.45}
        result = classify_deviation_ru("bet", freqs)
        assert result["is_mixed_spot"] is True


# ── D. Quality Labels ──

class TestQualityLabels:

    def test_all_five_labels_exist(self):
        for label in ["perfect", "good", "slight", "notable", "major"]:
            q = get_quality_label_ru(label)
            assert q["emoji"]
            assert q["text"]
            assert q["color"]
            assert any('\u0400' <= c <= '\u04FF' for c in q["text"]), f"{label} text not Russian"

    def test_legacy_labels_still_work(self):
        for label in ["close_to_solver", "acceptable_deviation", "clear_deviation"]:
            q = get_quality_label_ru(label)
            assert q["emoji"]
            assert q["text"]

    def test_unknown_label(self):
        q = get_quality_label_ru("nonexistent")
        assert q["emoji"] == "❓"

    def test_severity_colors_distinct(self):
        colors = set()
        for label in ["perfect", "good", "slight", "notable", "major"]:
            colors.add(get_quality_label_ru(label)["color"])
        assert len(colors) == 5, f"Expected 5 distinct colors, got {colors}"


# ── E. Deviation Response Structure ──

class TestDeviationResponseStructure:

    def test_has_all_required_fields(self):
        freqs = {"check": 0.60, "bet": 0.40}
        result = classify_deviation_ru("bet", freqs)
        required = [
            "label", "severity_level", "description",
            "coaching_message", "accuracy_pct", "user_freq",
            "best_action", "best_freq", "is_mixed_spot",
        ]
        for field in required:
            assert field in result, f"Missing field: {field}"

    def test_accuracy_calculation(self):
        freqs = {"check": 0.80, "bet": 0.20}
        result = classify_deviation_ru("bet", freqs)
        assert result["accuracy_pct"] == 25.0  # 0.20 / 0.80 * 100

    def test_normalized_action_names(self):
        freqs = {"bet_33": 0.50, "check": 0.50}
        result = classify_deviation_ru("bet33", freqs)
        assert result["user_freq"] == 0.50


# ── F. Hand Narrative Format ──

class TestHandNarrative:
    """Validate expected hand_narrative format from compare response."""

    def test_flop_narrative(self):
        board = ["7h", "3c", "Kd"]
        CARD_SUIT_RU = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}

        def card_display(c):
            rank = c[0].upper() if c[0] != 'T' else '10'
            suit = CARD_SUIT_RU.get(c[1], c[1]) if len(c) > 1 else ""
            return f"{rank}{suit}"

        board_display = " ".join(card_display(c) for c in board[:3])
        narrative = f"Флоп: {board_display} • Банк: 6.5ББ"
        assert "Флоп:" in narrative
        assert "7♥" in narrative
        assert "K♦" in narrative
        assert "6.5ББ" in narrative

    def test_turn_narrative(self):
        board = ["7h", "3c", "Kd", "As"]
        CARD_SUIT_RU = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
        def card_display(c):
            rank = c[0].upper() if c[0] != 'T' else '10'
            suit = CARD_SUIT_RU.get(c[1], c[1]) if len(c) > 1 else ""
            return f"{rank}{suit}"
        board_display = " ".join(card_display(c) for c in board[:3])
        narrative = f"Тёрн: {board_display} {card_display(board[3])} • Банк: 12.0ББ"
        assert "Тёрн:" in narrative
        assert "A♠" in narrative


# ── G. Next Steps Structure ──

class TestNextSteps:

    def test_next_steps_format(self):
        steps = [
            {"id": "drill", "label": "Потренировать", "icon": "🎯", "route": "/drill"},
            {"id": "explore", "label": "Изучить", "icon": "🔍", "route": "/explore"},
            {"id": "solver", "label": "Открыть солвер", "icon": "🧮", "route": "/solver?board=7h 3c Kd"},
        ]
        assert len(steps) == 3
        for s in steps:
            assert "id" in s
            assert "label" in s
            assert "icon" in s
            assert "route" in s

    def test_next_steps_all_russian(self):
        labels = [
            "Потренировать этот тип спота",
            "Изучить стратегию подробнее",
            "Открыть солвер с этим бордом",
        ]
        for label in labels:
            assert any('\u0400' <= c <= '\u04FF' for c in label)


# ── H. Regression: All labels Russian ──

class TestRussianRegression:

    def test_all_severity_descriptions_russian(self):
        test_cases = [
            ("check", {"check": 0.70, "bet": 0.30}),
            ("bet", {"check": 0.55, "bet": 0.45}),
            ("bet", {"check": 0.70, "bet": 0.15, "fold": 0.15}),
            ("fold", {"check": 0.85, "bet": 0.10, "fold": 0.05}),
            ("fold", {"check": 0.90, "bet": 0.09, "fold": 0.01}),
        ]
        for user_action, freqs in test_cases:
            result = classify_deviation_ru(user_action, freqs)
            desc = result["description"]
            coaching = result["coaching_message"]
            assert any('\u0400' <= c <= '\u04FF' for c in desc), f"Description not Russian: {desc}"
            assert any('\u0400' <= c <= '\u04FF' for c in coaching), f"Coaching not Russian: {coaching}"

    def test_no_english_in_quality_labels(self):
        for label in ["perfect", "good", "slight", "notable", "major"]:
            q = get_quality_label_ru(label)
            text = q["text"]
            forbidden = ["Perfect", "Good", "Slight", "Notable", "Major", "Deviation", "Error"]
            for eng in forbidden:
                assert eng.lower() not in text.lower(), f"English '{eng}' in label '{label}': {text}"
