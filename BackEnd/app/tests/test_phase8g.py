"""
Phase 8G Tests — Solver as Coach

Tests covering:
A. Coaching summary generation (main idea, takeaway, strictness)
B. Drill coaching feedback (severity, learning insight, mixed notes)
C. Node takeaway generation
D. Context transfer structure
E. Edge cases / fallback states
F. Regression protection
"""

import unittest


# ── A. Coaching Summary Logic (Python replica of TS coachingEngine) ──

def generate_coaching_summary(root_strategy: dict | None) -> dict:
    """Python replica of TS generateCoachingSummary for testing logic."""
    if not root_strategy:
        return {
            "main_idea": "Запустите расчёт, чтобы получить рекомендации тренера.",
            "key_takeaway": "Нет данных для анализа.",
            "strictness": "hand_dependent",
            "strictness_label": "Нет данных",
        }

    sorted_actions = sorted(root_strategy.items(), key=lambda x: x[1], reverse=True)
    top_action, top_freq = sorted_actions[0]

    if top_freq >= 0.85:
        strictness = "strict"
        strictness_label = "Строго"
    elif top_freq >= 0.60:
        strictness = "flexible"
        strictness_label = "Гибко"
    else:
        strictness = "hand_dependent"
        strictness_label = "Зависит от руки"

    # Main idea
    if top_freq >= 0.85:
        main_idea = f"В этом споте солвер почти всегда выбирает {top_action}."
    elif top_freq >= 0.60:
        sec = sorted_actions[1][0] if len(sorted_actions) > 1 else ""
        main_idea = f"Основная линия — {top_action}, но иногда нужно балансировать через {sec}."
    else:
        top2 = [a for a, _ in sorted_actions[:2]]
        main_idea = f"Смешанная стратегия: {' и '.join(top2)}."

    # Key takeaway
    if top_freq >= 0.85:
        key_takeaway = f"{top_action} — почти единственное правильное действие."
    elif top_freq >= 0.60:
        key_takeaway = f"{top_action} в {top_freq*100:.0f}% случаев — хорошее правило."
    else:
        key_takeaway = "Варьируйте решения по рукам."

    return {
        "main_idea": main_idea,
        "key_takeaway": key_takeaway,
        "strictness": strictness,
        "strictness_label": strictness_label,
    }


def generate_drill_coaching(chosen: str, correct: str, frequencies: dict, accuracy: float) -> dict:
    """Python replica of TS generateDrillCoaching for testing logic."""
    chosen_freq = frequencies.get(chosen, 0)
    correct_freq = frequencies.get(correct, 0)

    sorted_actions = sorted(frequencies.items(), key=lambda x: x[1], reverse=True)
    is_mixed = len(sorted_actions) >= 2 and sorted_actions[0][1] < 0.80

    # Severity
    if accuracy >= 1.0:
        severity = "perfect"
        severity_label = "Отлично!"
    elif chosen_freq >= 0.30:
        severity = "minor"
        severity_label = "Небольшое отклонение"
    elif chosen_freq >= 0.10:
        severity = "significant"
        severity_label = "Заметная ошибка"
    else:
        severity = "critical"
        severity_label = "Серьёзная ошибка"

    # Learning insight
    if accuracy >= 1.0:
        learning_insight = f"Правильно выбрано {correct}."
    elif chosen_freq >= 0.30:
        learning_insight = f"Допустимо: {chosen} ({chosen_freq*100:.0f}%). Основная линия — {correct}."
    elif chosen_freq >= 0.10:
        learning_insight = f"{chosen} применяется редко ({chosen_freq*100:.0f}%)."
    else:
        learning_insight = f"Солвер не выбирает {chosen}. Правильно — {correct}."

    # Mixed note
    mixed_note = None
    if is_mixed and accuracy < 1.0:
        mixed_note = "Спот со смешанной стратегией."

    return {
        "severity": severity,
        "severity_label": severity_label,
        "learning_insight": learning_insight,
        "mixed_note": mixed_note,
    }


def generate_node_takeaway(strategy: dict | None, player: str, street: str) -> dict:
    """Python replica of TS generateNodeTakeaway."""
    if not strategy:
        return {"takeaway": f"Решение на {street}.", "suggestion": "Выберите руку."}

    agg = {}
    total = 0
    for hand_freqs in strategy.values():
        total += 1
        for action, freq in hand_freqs.items():
            agg[action] = agg.get(action, 0) + freq
    if total:
        for a in agg:
            agg[a] /= total

    sorted_a = sorted(agg.items(), key=lambda x: x[1], reverse=True)
    if not sorted_a:
        return {"takeaway": f"Решение на {street}.", "suggestion": "Выберите руку."}

    top_action, top_freq = sorted_a[0]

    if top_freq >= 0.80:
        takeaway = f"Рейндж в основном играет через {top_action} ({top_freq*100:.0f}%)."
    elif top_freq >= 0.55:
        sec = sorted_a[1][0] if len(sorted_a) > 1 else ""
        takeaway = f"Преимущественно {top_action}, часть рук — {sec}."
    else:
        takeaway = "Смешанная стратегия."

    return {"takeaway": takeaway, "suggestion": "Изучите матрицу."}


# ── TEST CLASSES ──


class TestCoachingSummaryPure(unittest.TestCase):
    def test_pure_strategy_strict(self):
        result = generate_coaching_summary({"check": 0.90, "bet33": 0.10})
        self.assertEqual(result["strictness"], "strict")
        self.assertEqual(result["strictness_label"], "Строго")
        self.assertIn("check", result["main_idea"])

    def test_pure_strategy_takeaway(self):
        result = generate_coaching_summary({"check": 0.92, "bet33": 0.08})
        self.assertIn("единственное", result["key_takeaway"])


class TestCoachingSummaryMixed(unittest.TestCase):
    def test_flexible_strategy(self):
        result = generate_coaching_summary({"check": 0.65, "bet33": 0.35})
        self.assertEqual(result["strictness"], "flexible")
        self.assertEqual(result["strictness_label"], "Гибко")

    def test_hand_dependent_strategy(self):
        result = generate_coaching_summary({"check": 0.40, "bet33": 0.35, "bet75": 0.25})
        self.assertEqual(result["strictness"], "hand_dependent")
        self.assertEqual(result["strictness_label"], "Зависит от руки")
        self.assertIn("Смешанная", result["main_idea"])


class TestCoachingSummaryEmpty(unittest.TestCase):
    def test_none_strategy(self):
        result = generate_coaching_summary(None)
        self.assertEqual(result["strictness"], "hand_dependent")
        self.assertIn("Нет данных", result["key_takeaway"])

    def test_empty_strategy(self):
        result = generate_coaching_summary({})
        self.assertEqual(result["strictness"], "hand_dependent")


class TestDrillCoachingPerfect(unittest.TestCase):
    def test_perfect_answer(self):
        result = generate_drill_coaching("check", "check", {"check": 0.8, "bet33": 0.2}, 1.0)
        self.assertEqual(result["severity"], "perfect")
        self.assertEqual(result["severity_label"], "Отлично!")

    def test_perfect_no_mixed_note(self):
        result = generate_drill_coaching("check", "check", {"check": 0.9, "bet33": 0.1}, 1.0)
        self.assertIsNone(result["mixed_note"])


class TestDrillCoachingMinor(unittest.TestCase):
    def test_minor_deviation(self):
        result = generate_drill_coaching("bet33", "check", {"check": 0.55, "bet33": 0.45}, 0.45 / 0.55)
        self.assertEqual(result["severity"], "minor")
        self.assertIn("Допустимо", result["learning_insight"])

    def test_minor_has_mixed_note(self):
        result = generate_drill_coaching("bet33", "check", {"check": 0.55, "bet33": 0.45}, 0.45 / 0.55)
        self.assertIsNotNone(result["mixed_note"])


class TestDrillCoachingCritical(unittest.TestCase):
    def test_critical_mistake(self):
        result = generate_drill_coaching("fold", "check", {"check": 0.85, "bet33": 0.15, "fold": 0.0}, 0.0)
        self.assertEqual(result["severity"], "critical")
        self.assertIn("Серьёзная", result["severity_label"])

    def test_significant_mistake(self):
        result = generate_drill_coaching("bet75", "check", {"check": 0.70, "bet33": 0.20, "bet75": 0.10}, 0.10 / 0.70)
        self.assertEqual(result["severity"], "significant")


class TestNodeTakeaway(unittest.TestCase):
    def test_pure_node(self):
        strategy = {
            "AKs": {"check": 0.9, "bet33": 0.1},
            "QTo": {"check": 0.85, "bet33": 0.15},
        }
        result = generate_node_takeaway(strategy, "OOP", "flop")
        self.assertIn("check", result["takeaway"].lower())

    def test_mixed_node(self):
        strategy = {
            "AKs": {"check": 0.5, "bet33": 0.3, "bet75": 0.2},
            "QTo": {"check": 0.4, "bet33": 0.4, "bet75": 0.2},
        }
        result = generate_node_takeaway(strategy, "IP", "flop")
        self.assertIn("Смешанная", result["takeaway"])

    def test_empty_strategy(self):
        result = generate_node_takeaway(None, "IP", "flop")
        self.assertIn("flop", result["takeaway"])


class TestContextTransfer(unittest.TestCase):
    def test_context_structure(self):
        ctx = {
            "spotId": None,
            "fromSolver": True,
            "mainIdea": "Основная линия — чек",
            "keyTakeaway": "Чек — единственное правильное действие",
            "strictness": "strict",
            "strictnessLabel": "Строго",
            "rootStrategy": {"check": 0.90, "bet33": 0.10},
        }
        self.assertTrue(ctx["fromSolver"])
        self.assertIn("mainIdea", ctx)
        self.assertIn("keyTakeaway", ctx)
        self.assertIn("strictness", ctx)
        self.assertIn("rootStrategy", ctx)

    def test_context_without_coaching(self):
        ctx = {"spotId": None, "fromSolver": True}
        self.assertTrue(ctx["fromSolver"])
        self.assertNotIn("mainIdea", ctx)

    def test_context_clear(self):
        ctx = {"spotId": None, "fromSolver": False}
        self.assertFalse(ctx["fromSolver"])


class TestStrictnessClassification(unittest.TestCase):
    def test_strict_threshold(self):
        r = generate_coaching_summary({"check": 0.85, "bet33": 0.15})
        self.assertEqual(r["strictness"], "strict")

    def test_flexible_threshold(self):
        r = generate_coaching_summary({"check": 0.60, "bet33": 0.40})
        self.assertEqual(r["strictness"], "flexible")

    def test_hand_dependent_threshold(self):
        r = generate_coaching_summary({"check": 0.40, "bet33": 0.35, "bet75": 0.25})
        self.assertEqual(r["strictness"], "hand_dependent")


class TestRegressionProtection(unittest.TestCase):
    def test_all_severity_levels_exist(self):
        levels = {"perfect", "minor", "significant", "critical"}
        results = set()
        results.add(generate_drill_coaching("check", "check", {"check": 0.9}, 1.0)["severity"])
        results.add(generate_drill_coaching("bet33", "check", {"check": 0.55, "bet33": 0.45}, 0.8)["severity"])
        results.add(generate_drill_coaching("bet75", "check", {"check": 0.70, "bet75": 0.15}, 0.2)["severity"])
        results.add(generate_drill_coaching("fold", "check", {"check": 0.90, "fold": 0.0}, 0.0)["severity"])
        self.assertEqual(results, levels)

    def test_all_strictness_levels_exist(self):
        levels = {"strict", "flexible", "hand_dependent"}
        results = set()
        results.add(generate_coaching_summary({"check": 0.90})["strictness"])
        results.add(generate_coaching_summary({"check": 0.65, "bet33": 0.35})["strictness"])
        results.add(generate_coaching_summary({"check": 0.40, "bet33": 0.35, "bet75": 0.25})["strictness"])
        self.assertEqual(results, levels)

    def test_russian_labels_in_coaching(self):
        r = generate_coaching_summary({"check": 0.90, "bet33": 0.10})
        self.assertIn("Строго", r["strictness_label"])

    def test_russian_labels_in_drill(self):
        r = generate_drill_coaching("check", "check", {"check": 0.9}, 1.0)
        self.assertIn("Отлично", r["severity_label"])


if __name__ == "__main__":
    unittest.main()
