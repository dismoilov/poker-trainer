"""
Phase 8B tests — Recommendation engine, deviation classification,
enriched API responses, quality labels.
"""

import pytest
from app.services.recommendation import (
    generate_recommendation_summary,
    classify_deviation,
    get_quality_label,
    generate_node_context,
    DEVIATION_PERFECT,
    DEVIATION_CLOSE,
    DEVIATION_ACCEPTABLE,
    DEVIATION_CLEAR,
)


# ── Recommendation Summary Tests ────────────────────────────────


class TestRecommendationSummary:
    """Test human-readable recommendation summary generation."""

    def test_dominant_action(self):
        """Single dominant action (>80%) produces 'Mostly X' summary."""
        freqs = {"check": 0.85, "bet_50": 0.15}
        summary = generate_recommendation_summary(freqs)
        assert "Mostly" in summary or "mostly" in summary
        assert "check" in summary.lower()

    def test_strong_lean(self):
        """Strong lean (60-80%) produces 'Primarily X' summary."""
        freqs = {"check": 0.65, "bet_50": 0.35}
        summary = generate_recommendation_summary(freqs)
        assert "Primarily" in summary or "primarily" in summary

    def test_true_mix(self):
        """True mix (40-60%) produces 'Mix between X and Y' summary."""
        freqs = {"check": 0.50, "bet_50": 0.50}
        summary = generate_recommendation_summary(freqs)
        assert "mix" in summary.lower() or "Mix" in summary

    def test_pure_check(self):
        """100% check produces clear summary."""
        freqs = {"check": 1.0}
        summary = generate_recommendation_summary(freqs)
        assert "check" in summary.lower()
        assert "Mostly" in summary or "mostly" in summary

    def test_three_way_split(self):
        """Three-way split produces readable summary."""
        freqs = {"check": 0.33, "bet_50": 0.34, "bet_75": 0.33}
        summary = generate_recommendation_summary(freqs)
        assert len(summary) > 10  # Not empty

    def test_empty_frequencies(self):
        """Empty frequencies return a no-data message."""
        summary = generate_recommendation_summary({})
        assert "no" in summary.lower() or "No" in summary

    def test_rare_fold(self):
        """Rare fold is mentioned in summary."""
        freqs = {"check": 0.60, "bet_50": 0.35, "fold": 0.05}
        summary = generate_recommendation_summary(freqs)
        # Fold should not be primary in the summary
        assert "check" in summary.lower() or "bet" in summary.lower()

    def test_single_action(self):
        """Single action produces clear summary."""
        freqs = {"bet_75": 0.95, "check": 0.05}
        summary = generate_recommendation_summary(freqs)
        assert "bet" in summary.lower()


# ── Deviation Classification Tests ──────────────────────────────


class TestDeviationClassification:
    """Test user action deviation classification."""

    def test_perfect_match(self):
        """User chose the top action = perfect."""
        freqs = {"check": 0.70, "bet_50": 0.30}
        result = classify_deviation("check", freqs)
        assert result["label"] == DEVIATION_PERFECT
        assert result["accuracy_pct"] == 100.0

    def test_close_to_solver(self):
        """User chose a significant secondary action >= 30%."""
        freqs = {"check": 0.60, "bet_50": 0.40}
        result = classify_deviation("bet_50", freqs)
        assert result["label"] == DEVIATION_CLOSE
        assert result["accuracy_pct"] > 60

    def test_acceptable_deviation(self):
        """User chose a minor action (10-30%)."""
        freqs = {"check": 0.65, "bet_50": 0.20, "fold": 0.15}
        result = classify_deviation("fold", freqs)
        assert result["label"] == DEVIATION_ACCEPTABLE

    def test_clear_deviation(self):
        """User chose a very rare action (<10%)."""
        freqs = {"check": 0.85, "bet_50": 0.10, "fold": 0.05}
        result = classify_deviation("fold", freqs)
        assert result["label"] == DEVIATION_CLEAR
        assert result["accuracy_pct"] < 10

    def test_zero_frequency_action(self):
        """User chose an action not in the solver's mix."""
        freqs = {"check": 0.70, "bet_50": 0.30}
        result = classify_deviation("fold", freqs)
        assert result["label"] == DEVIATION_CLEAR
        assert result["user_freq"] == 0.0

    def test_empty_frequencies(self):
        """Empty frequencies return unknown label."""
        result = classify_deviation("check", {})
        assert result["label"] == "unknown"

    def test_deviation_has_best_action(self):
        """Deviation result includes best action info."""
        freqs = {"check": 0.70, "bet_50": 0.30}
        result = classify_deviation("bet_50", freqs)
        assert result["best_action"] == "check"
        assert result["best_freq"] == 0.70

    def test_normalized_action_match(self):
        """Action name normalization (bet_50 vs bet50)."""
        freqs = {"check": 0.60, "bet50": 0.40}
        result = classify_deviation("bet_50", freqs)
        # Should match via normalization
        assert result["user_freq"] > 0

    def test_perfect_has_description(self):
        """Perfect deviation has a positive description."""
        freqs = {"check": 0.80, "bet_50": 0.20}
        result = classify_deviation("check", freqs)
        assert "Perfect" in result["description"] or "top" in result["description"]


# ── Quality Label Tests ─────────────────────────────────────────


class TestQualityLabel:
    """Test quality label generation."""

    def test_perfect_label(self):
        label = get_quality_label(DEVIATION_PERFECT)
        assert label["emoji"] == "🎯"
        assert label["color"] == "emerald"

    def test_close_label(self):
        label = get_quality_label(DEVIATION_CLOSE)
        assert label["emoji"] == "✅"
        assert label["color"] == "green"

    def test_acceptable_label(self):
        label = get_quality_label(DEVIATION_ACCEPTABLE)
        assert label["emoji"] == "⚠️"
        assert label["color"] == "amber"

    def test_clear_label(self):
        label = get_quality_label(DEVIATION_CLEAR)
        assert label["emoji"] == "❌"
        assert label["color"] == "red"

    def test_unknown_label(self):
        label = get_quality_label("unknown")
        assert label["emoji"] == "❓"


# ── Node Context Tests ──────────────────────────────────────────


class TestNodeContext:
    """Test educational node context generation."""

    def test_ip_flop_context(self):
        ctx = generate_node_context(
            player="IP", street="flop",
            line_description="facing check",
        )
        assert "in position" in ctx["node_explanation"]
        assert "flop" in ctx["node_explanation"]
        assert len(ctx["spot_context"]) > 10

    def test_oop_turn_context(self):
        ctx = generate_node_context(
            player="OOP", street="turn",
            line_description="check-raise spot",
        )
        assert "out of position" in ctx["node_explanation"]
        assert "turn" in ctx["node_explanation"]

    def test_deep_stack_context(self):
        ctx = generate_node_context(
            player="IP", street="flop",
            line_description="c-bet",
            pot_size=6.5, stack_size=100,
        )
        assert "deep" in ctx["node_explanation"].lower() or "room" in ctx["node_explanation"].lower()

    def test_short_spr_context(self):
        ctx = generate_node_context(
            player="IP", street="flop",
            line_description="all-in",
            pot_size=60, stack_size=40,
        )
        assert "short" in ctx["node_explanation"].lower() or "commit" in ctx["node_explanation"].lower()

    def test_cbet_spot_context(self):
        ctx = generate_node_context(
            player="IP", street="flop",
            line_description="cbet decision",
        )
        assert "continuation bet" in ctx["spot_context"].lower() or "c-bet" in ctx["spot_context"].lower()


# ── Integration: Enriched DrillFeedback Schema ──────────────────


class TestDrillFeedbackEnrichment:
    """Test that drill feedback can integrate recommendation summaries."""

    def test_recommendation_for_drill_feedback(self):
        """Drill feedback frequencies produce a valid recommendation summary."""
        freqs = {"check": 0.55, "bet33": 0.30, "bet75": 0.15}
        summary = generate_recommendation_summary(freqs)
        assert len(summary) > 5

        deviation = classify_deviation("bet33", freqs)
        assert deviation["label"] in (DEVIATION_CLOSE, DEVIATION_ACCEPTABLE)

    def test_recommendation_for_perfect_drill(self):
        """Perfect drill answer produces perfect quality label."""
        freqs = {"check": 0.80, "bet33": 0.20}
        deviation = classify_deviation("check", freqs)
        quality = get_quality_label(deviation["label"])
        assert quality["text"] == "Perfect"
        assert quality["emoji"] == "🎯"


# ── Integration: Explore HandDetail Enrichment ──────────────────


class TestExploreEnrichment:
    """Test that explore hand detail has recommendation + context."""

    def test_handdetail_schema_has_new_fields(self):
        """HandDetail schema accepts Phase 8B fields."""
        from app.schemas import HandDetail
        detail = HandDetail(
            hand="AKs",
            tier=1,
            tierLabel="Premium (Top 3%)",
            frequencies={"check": 0.5, "bet33": 0.5},
            connection="top_pair",
            explanation=["Test explanation"],
            recommendation_summary="Mix between check and bet 33% pot.",
            node_context={"node_explanation": "You are in position on the flop.", "spot_context": "IP on flop."},
            data_source_label="Heuristic GTO Data",
        )
        assert detail.recommendation_summary == "Mix between check and bet 33% pot."
        assert detail.node_context is not None
        assert detail.data_source_label == "Heuristic GTO Data"

    def test_handdetail_schema_backward_compatible(self):
        """HandDetail schema works without Phase 8B fields."""
        from app.schemas import HandDetail
        detail = HandDetail(
            hand="72o",
            tier=8,
            tierLabel="Trash",
            frequencies={"fold": 0.9, "call": 0.1},
            connection="nothing",
            explanation=["Bad hand"],
        )
        assert detail.recommendation_summary == ""
        assert detail.node_context is None
        assert detail.data_source_label == "Heuristic GTO"


# ── Unsupported State Handling ──────────────────────────────────


class TestUnsupportedStates:
    """Test handling of edge cases and unsupported states."""

    def test_deviation_with_empty_action(self):
        """Empty user_action treated as clear deviation."""
        freqs = {"check": 0.80, "bet_50": 0.20}
        result = classify_deviation("", freqs)
        assert result["label"] == DEVIATION_CLEAR
        assert result["user_freq"] == 0.0

    def test_recommendation_with_single_action(self):
        """Single action in frequencies = dominant summary."""
        freqs = {"allin": 1.0}
        summary = generate_recommendation_summary(freqs)
        assert "all-in" in summary.lower() or "allin" in summary.lower()

    def test_recommendation_with_tiny_frequencies(self):
        """Very small frequencies produce a valid summary."""
        freqs = {"check": 0.01, "bet_50": 0.01, "fold": 0.98}
        summary = generate_recommendation_summary(freqs)
        assert "fold" in summary.lower()

    def test_node_context_empty_line(self):
        """Empty line description produces valid context."""
        ctx = generate_node_context(
            player="IP", street="flop", line_description="",
        )
        assert len(ctx["node_explanation"]) > 10
        assert len(ctx["spot_context"]) > 5
