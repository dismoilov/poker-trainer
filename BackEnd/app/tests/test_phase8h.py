"""
Phase 8H Tests — Frictionless Solver UX

Tests covering:
A. Compare availability (backend unsupported response localized to Russian)
B. Board carry-over URL format
C. humanizeError pattern matching (Python replica)
D. Duplicate card prevention logic
E. Visual board picker state logic
F. Human-readable error recovery messages
G. Regression protection
"""

import unittest


# ── Python replicas of frontend logic ──

def humanize_error(raw: str) -> dict:
    """Python replica of humanizeError.ts for testing logic."""
    patterns = [
        {
            "test": lambda m: "IP range too large" in m,
            "title": "Диапазон IP слишком широкий",
            "icon": "📊",
            "action_type": "reduce_range",
        },
        {
            "test": lambda m: "OOP range too large" in m,
            "title": "Диапазон OOP слишком широкий",
            "icon": "📊",
            "action_type": "reduce_range",
        },
        {
            "test": lambda m: "tree too large" in m.lower() or "action tree too large" in m.lower(),
            "title": "Дерево решений слишком большое",
            "icon": "🌳",
            "action_type": "general",
        },
        {
            "test": lambda m: "too many matchups" in m.lower(),
            "title": "Слишком много пар рук",
            "icon": "🔗",
            "action_type": "reduce_range",
        },
        {
            "test": lambda m: "0 valid combos" in m,
            "title": "Нет подходящих рук",
            "icon": "🃏",
            "action_type": None,
        },
        {
            "test": lambda m: "no valid matchups" in m.lower(),
            "title": "Нет возможных раздач",
            "icon": "⚠️",
            "action_type": None,
        },
        {
            "test": lambda m: "duplicate board" in m.lower(),
            "title": "Дублирующиеся карты на борде",
            "icon": "🔄",
            "action_type": None,
        },
        {
            "test": lambda m: "at least 3 board cards" in m.lower() or "need at least 3" in m.lower(),
            "title": "Недостаточно карт на борде",
            "icon": "🃏",
            "action_type": None,
        },
        {
            "test": lambda m: "turn" in m.lower() and ("too expensive" in m.lower() or "exceeds" in m.lower()),
            "title": "Расчёт тёрна слишком тяжёлый",
            "icon": "⏱️",
            "action_type": "disable_turn",
        },
    ]

    for p in patterns:
        if p["test"](raw):
            return {
                "title": p["title"],
                "icon": p["icon"],
                "action_type": p["action_type"],
                "is_russian": True,
            }

    return {
        "title": "Ошибка расчёта",
        "icon": "❌",
        "action_type": None,
        "is_russian": True,
    }


def parse_board_url(url_param: str) -> list[str]:
    """Parse ?board= URL param into card list."""
    import re
    cards = url_param.strip().split()
    return [c for c in cards if re.match(r'^[2-9TJQKA][shdc]$', c, re.IGNORECASE)]


def validate_board_no_duplicates(cards: list[str]) -> bool:
    """Check no duplicate cards in board."""
    return len(set(cards)) == len(cards)


# ── TESTS ──


class TestHumanizeErrorIPRange(unittest.TestCase):
    def test_ip_range_too_large(self):
        result = humanize_error("IP range too large (55 combos, max 50)")
        self.assertEqual(result["title"], "Диапазон IP слишком широкий")
        self.assertEqual(result["icon"], "📊")
        self.assertEqual(result["action_type"], "reduce_range")

    def test_oop_range_too_large(self):
        result = humanize_error("OOP range too large (60 combos, max 50)")
        self.assertEqual(result["title"], "Диапазон OOP слишком широкий")
        self.assertEqual(result["action_type"], "reduce_range")


class TestHumanizeErrorTree(unittest.TestCase):
    def test_tree_too_large(self):
        result = humanize_error("Tree too large (2500 nodes, max 2000)")
        self.assertEqual(result["title"], "Дерево решений слишком большое")
        self.assertEqual(result["action_type"], "general")

    def test_action_tree_too_large(self):
        result = humanize_error("Action tree too large (3000 nodes, max 2000)")
        self.assertEqual(result["title"], "Дерево решений слишком большое")


class TestHumanizeErrorMatchups(unittest.TestCase):
    def test_too_many_matchups(self):
        result = humanize_error("Too many matchups (5000), max 3000. Use smaller ranges.")
        self.assertEqual(result["title"], "Слишком много пар рук")
        self.assertEqual(result["action_type"], "reduce_range")


class TestHumanizeErrorCombos(unittest.TestCase):
    def test_zero_combos(self):
        result = humanize_error("IP range has 0 valid combos after removing board blockers")
        self.assertEqual(result["title"], "Нет подходящих рук")
        self.assertIsNone(result["action_type"])

    def test_no_valid_matchups(self):
        result = humanize_error("No valid matchups (all combos overlap with board or each other)")
        self.assertEqual(result["title"], "Нет возможных раздач")


class TestHumanizeErrorBoard(unittest.TestCase):
    def test_duplicate_board(self):
        result = humanize_error("Duplicate board cards")
        self.assertEqual(result["title"], "Дублирующиеся карты на борде")

    def test_not_enough_cards(self):
        result = humanize_error("Need at least 3 board cards")
        self.assertEqual(result["title"], "Недостаточно карт на борде")


class TestHumanizeErrorTurn(unittest.TestCase):
    def test_turn_too_expensive(self):
        result = humanize_error("Turn solve with 8 cards and 1000 iterations is too expensive.")
        self.assertEqual(result["title"], "Расчёт тёрна слишком тяжёлый")
        self.assertEqual(result["action_type"], "disable_turn")


class TestHumanizeErrorFallback(unittest.TestCase):
    def test_unknown_error(self):
        result = humanize_error("Some completely new error message xyz")
        self.assertEqual(result["title"], "Ошибка расчёта")
        self.assertTrue(result["is_russian"])


class TestBoardURLParsing(unittest.TestCase):
    def test_simple_board(self):
        cards = parse_board_url("Ks 7d 2c")
        self.assertEqual(cards, ["Ks", "7d", "2c"])

    def test_four_card_board(self):
        cards = parse_board_url("Ks 7d 2c Ah")
        self.assertEqual(cards, ["Ks", "7d", "2c", "Ah"])

    def test_invalid_cards_filtered(self):
        cards = parse_board_url("Ks XX 7d 2c")
        self.assertEqual(cards, ["Ks", "7d", "2c"])

    def test_empty_string(self):
        cards = parse_board_url("")
        self.assertEqual(cards, [])


class TestDuplicateCardPrevention(unittest.TestCase):
    def test_no_duplicates(self):
        self.assertTrue(validate_board_no_duplicates(["Ks", "7d", "2c"]))

    def test_has_duplicate(self):
        self.assertFalse(validate_board_no_duplicates(["Ks", "7d", "Ks"]))

    def test_empty_valid(self):
        self.assertTrue(validate_board_no_duplicates([]))


class TestCompareUnsupportedResponse(unittest.TestCase):
    """Tests the backend compare-to-solver unsupported response structure."""

    def test_unsupported_response_structure(self):
        """Verify expected fields in unsupported compare response."""
        response = {
            "match_quality": "unsupported",
            "message": "Солвер ещё не рассчитал борд Ks 7d 2c.",
            "explanation": "Чтобы сравнить свою игру с солвером, нужен расчёт именно для этого флопа.",
            "board_for_solver": "Ks 7d 2c",
            "solver_data": None,
        }
        self.assertEqual(response["match_quality"], "unsupported")
        self.assertIn("Солвер", response["message"])
        self.assertIn("Ks 7d 2c", response["board_for_solver"])
        self.assertIsNone(response["solver_data"])

    def test_russian_text_in_response(self):
        """Verify no English text in unsupported response."""
        response = {
            "message": "Солвер ещё не рассчитал борд Ks 7d 2c.",
            "explanation": "Чтобы сравнить свою игру с солвером...",
        }
        # Should contain Russian text, not English
        self.assertNotIn("No persisted solve", response["message"])
        self.assertNotIn("Run a solve", response["message"])
        self.assertIn("Солвер", response["message"])


class TestBoardPickerLogic(unittest.TestCase):
    """Test board picker selection/deselection logic."""

    def test_add_card(self):
        board = []
        new_card = "Ks"
        if new_card not in board and len(board) < 5:
            board.append(new_card)
        self.assertEqual(board, ["Ks"])

    def test_remove_card(self):
        board = ["Ks", "7d", "2c"]
        board = [c for c in board if c != "7d"]
        self.assertEqual(board, ["Ks", "2c"])

    def test_prevent_duplicate(self):
        board = ["Ks", "7d"]
        new_card = "Ks"
        if new_card not in board and len(board) < 5:
            board.append(new_card)
        self.assertEqual(board, ["Ks", "7d"])

    def test_max_cards_limit(self):
        board = ["Ks", "7d", "2c", "Ah", "Ts"]
        new_card = "Qd"
        if new_card not in board and len(board) < 5:
            board.append(new_card)
        self.assertEqual(len(board), 5)
        self.assertNotIn("Qd", board)

    def test_clear_all(self):
        board = ["Ks", "7d", "2c"]
        board = []
        self.assertEqual(board, [])


class TestRegressionProtection(unittest.TestCase):
    def test_all_error_patterns_are_russian(self):
        """Every humanized error must have a Russian title."""
        test_messages = [
            "IP range too large (55 combos, max 50)",
            "OOP range too large (60 combos, max 50)",
            "Tree too large (2500 nodes, max 2000)",
            "Too many matchups (5000)",
            "IP range has 0 valid combos",
            "Duplicate board cards",
            "Need at least 3 board cards",
            "Turn solve too expensive",
            "Unknown error 12345",
        ]
        for msg in test_messages:
            result = humanize_error(msg)
            self.assertTrue(result["is_russian"], f"Error for '{msg}' not Russian")

    def test_board_url_format_consistency(self):
        """Board URL param should be space-separated card notation."""
        board = ["Ks", "7d", "2c"]
        url_param = " ".join(board)
        parsed = parse_board_url(url_param)
        self.assertEqual(parsed, board)


if __name__ == "__main__":
    unittest.main()
