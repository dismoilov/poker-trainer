"""
Recommendation & Review Engine — Phase 8B.

Generates human-readable recommendation summaries and deviation classifications
for solver-backed learning flows. Used by Play review, Drill feedback, and Explore.

HONEST NOTE: Recommendations are based on solver frequencies within the current
abstraction (flop-only HU postflop with fixed bet sizes). They are NOT universal
poker advice. Mixed strategies mean multiple actions can be correct.
"""

from __future__ import annotations
from typing import Optional


# ── Recommendation Summary ───────────────────────────────────────

def generate_recommendation_summary(frequencies: dict[str, float]) -> str:
    """Generate a human-readable recommendation summary from action frequencies.

    Examples:
      {"check": 0.85, "bet_50": 0.15}  → "Mostly check (85%). Occasionally bet 50% pot."
      {"check": 0.45, "bet_50": 0.55}  → "Mix between bet 50% pot and check."
      {"fold": 0.01, "call": 0.60, "raise": 0.39} → "Primarily call (60%). Sometimes raise."
    """
    if not frequencies:
        return "No solver data available for this spot."

    sorted_actions = sorted(frequencies.items(), key=lambda x: x[1], reverse=True)
    top_action, top_freq = sorted_actions[0]
    top_label = _humanize_action(top_action)

    # Single dominant action (>80%)
    if top_freq >= 0.80:
        parts = [f"Mostly {top_label} ({top_freq*100:.0f}%)."]
        for action, freq in sorted_actions[1:]:
            if freq >= 0.05:
                parts.append(f"Occasionally {_humanize_action(action)}.")
        return " ".join(parts)

    # Strong lean (60-80%)
    if top_freq >= 0.60:
        second_action, second_freq = sorted_actions[1] if len(sorted_actions) > 1 else ("", 0)
        parts = [f"Primarily {top_label} ({top_freq*100:.0f}%)."]
        if second_freq >= 0.15:
            parts.append(f"Sometimes {_humanize_action(second_action)} ({second_freq*100:.0f}%).")
        return " ".join(parts)

    # True mix (40-60% top action)
    if top_freq >= 0.40:
        secondary = [a for a, f in sorted_actions[1:] if f >= 0.20]
        if secondary:
            mix_labels = [top_label] + [_humanize_action(a) for a in secondary]
            return f"Mix between {' and '.join(mix_labels)}."
        else:
            return f"Lean towards {top_label} ({top_freq*100:.0f}%), but mixed strategy."

    # Spread across many actions
    significant = [(a, f) for a, f in sorted_actions if f >= 0.15]
    if len(significant) >= 3:
        labels = [f"{_humanize_action(a)} {f*100:.0f}%" for a, f in significant]
        return f"Split: {', '.join(labels)}."
    elif len(significant) == 2:
        a1, f1 = significant[0]
        a2, f2 = significant[1]
        return f"Mix between {_humanize_action(a1)} ({f1*100:.0f}%) and {_humanize_action(a2)} ({f2*100:.0f}%)."
    else:
        return f"Slight lean towards {top_label} ({top_freq*100:.0f}%)."


def _humanize_action(action_id: str) -> str:
    """Convert action IDs to readable labels."""
    mappings = {
        "fold": "fold",
        "check": "check",
        "call": "call",
        "bet33": "bet 33% pot",
        "bet_33": "bet 33% pot",
        "bet50": "bet 50% pot",
        "bet_50": "bet 50% pot",
        "bet75": "bet 75% pot",
        "bet_75": "bet 75% pot",
        "bet150": "bet 150% pot",
        "bet_150": "bet 150% pot",
        "raise": "raise",
        "allin": "go all-in",
    }
    return mappings.get(action_id, action_id.replace("_", " "))


# ── Deviation Classification ─────────────────────────────────────

DEVIATION_PERFECT = "perfect"
DEVIATION_CLOSE = "close_to_solver"
DEVIATION_ACCEPTABLE = "acceptable_deviation"
DEVIATION_CLEAR = "clear_deviation"


def classify_deviation(
    user_action: str,
    frequencies: dict[str, float],
) -> dict:
    """Classify how far a user's action deviates from the solver recommendation.

    Returns:
      label: perfect | close_to_solver | acceptable_deviation | clear_deviation
      description: human-readable explanation
      accuracy_pct: 0-100 how well the action matches
      user_freq: solver frequency for the user's chosen action
      best_action: the action the solver prefers most
      best_freq: frequency of the best action
    """
    if not frequencies:
        return {
            "label": "unknown",
            "description": "No solver data available for comparison.",
            "accuracy_pct": 0.0,
            "user_freq": 0.0,
            "best_action": "",
            "best_freq": 0.0,
        }

    best_action = max(frequencies, key=frequencies.get)
    best_freq = frequencies[best_action]
    user_freq = frequencies.get(user_action, 0.0)

    # Also check action name variations (bet_50 vs bet50)
    if user_freq == 0.0:
        normalized = user_action.replace("_", "")
        for k, v in frequencies.items():
            if k.replace("_", "") == normalized:
                user_freq = v
                break

    accuracy_pct = round(user_freq / best_freq * 100, 1) if best_freq > 0 else 0.0

    best_label = _humanize_action(best_action)
    user_label = _humanize_action(user_action)

    if user_action == best_action or user_freq == best_freq:
        return {
            "label": DEVIATION_PERFECT,
            "description": f"Perfect! {user_label.capitalize()} is the solver's top recommendation.",
            "accuracy_pct": 100.0,
            "user_freq": round(user_freq, 4),
            "best_action": best_action,
            "best_freq": round(best_freq, 4),
        }

    if user_freq >= 0.30:
        return {
            "label": DEVIATION_CLOSE,
            "description": (
                f"Close to solver. {user_label.capitalize()} has {user_freq*100:.0f}% "
                f"solver frequency. The top action is {best_label} at {best_freq*100:.0f}%. "
                f"Both are reasonable in this spot."
            ),
            "accuracy_pct": accuracy_pct,
            "user_freq": round(user_freq, 4),
            "best_action": best_action,
            "best_freq": round(best_freq, 4),
        }

    if user_freq >= 0.10:
        return {
            "label": DEVIATION_ACCEPTABLE,
            "description": (
                f"Acceptable deviation. {user_label.capitalize()} has {user_freq*100:.0f}% "
                f"solver frequency — it's part of the mixed strategy, but not the primary line. "
                f"The solver prefers {best_label} at {best_freq*100:.0f}%."
            ),
            "accuracy_pct": accuracy_pct,
            "user_freq": round(user_freq, 4),
            "best_action": best_action,
            "best_freq": round(best_freq, 4),
        }

    return {
        "label": DEVIATION_CLEAR,
        "description": (
            f"Clear deviation. {user_label.capitalize()} has only {user_freq*100:.0f}% "
            f"solver frequency. The solver strongly prefers {best_label} ({best_freq*100:.0f}%). "
            f"Consider why {best_label} is preferred in this spot."
        ),
        "accuracy_pct": accuracy_pct,
        "user_freq": round(user_freq, 4),
        "best_action": best_action,
        "best_freq": round(best_freq, 4),
    }


# ── Quality Labels ────────────────────────────────────────────────

def get_quality_label(deviation_label: str) -> dict:
    """Get a display-friendly quality label with emoji and color hint."""
    labels = {
        DEVIATION_PERFECT: {"emoji": "🎯", "text": "Perfect", "color": "emerald"},
        DEVIATION_CLOSE: {"emoji": "✅", "text": "Close to Solver", "color": "green"},
        DEVIATION_ACCEPTABLE: {"emoji": "⚠️", "text": "Acceptable Deviation", "color": "amber"},
        DEVIATION_CLEAR: {"emoji": "❌", "text": "Clear Deviation", "color": "red"},
        "unknown": {"emoji": "❓", "text": "Unknown", "color": "gray"},
    }
    return labels.get(deviation_label, labels["unknown"])


# ── Node Context for Explore ──────────────────────────────────────

def generate_node_context(
    player: str,
    street: str,
    line_description: str,
    pot_size: float = 0.0,
    stack_size: float = 100.0,
) -> dict:
    """Generate educational context for a decision node.

    Returns node_explanation and spot_context for the Explore page.
    """
    pos_label = "in position (acts last)" if player == "IP" else "out of position (acts first)"

    node_explanation = (
        f"You are {pos_label} on the {street}. "
        f"The action has gone: {line_description or 'start of hand'}. "
    )

    if pot_size > 0:
        spr = stack_size / pot_size if pot_size > 0 else 0
        if spr > 10:
            node_explanation += "With deep stacks relative to the pot, you have room to maneuver. "
        elif spr > 3:
            node_explanation += "Stack-to-pot ratio is medium — commit decisions are approaching. "
        else:
            node_explanation += "Short stack-to-pot ratio — any significant bet commits you to the pot. "

    spot_context = _describe_spot(player, street, line_description)

    return {
        "node_explanation": node_explanation,
        "spot_context": spot_context,
    }


def _describe_spot(player: str, street: str, line_description: str) -> str:
    """Generate a simple description of what situation the user is in."""
    line = (line_description or "").lower()

    if "cbet" in line or "c-bet" in line:
        return "This is a continuation bet situation. The preflop aggressor is deciding whether to bet again."
    if "check" in line and "raise" in line:
        return "This is a check-raise situation. A player checked, faced a bet, and now decides whether to raise."
    if "facing bet" in line or "vs bet" in line:
        return "You are facing a bet and must decide whether to fold, call, or raise."
    if street == "flop":
        if player == "IP":
            return "In position on the flop. You act after your opponent, giving you an information advantage."
        return "Out of position on the flop. You act first, so you must balance checking and betting carefully."
    if street == "turn":
        return "On the turn. An additional board card has changed the situation. Adjust your strategy accordingly."
    if street == "river":
        return "On the river. No more cards to come. Decisions are purely about value and bluffs."

    return f"Decision point on the {street}."
