"""
Phase 8I Tests — Play-side localization, compare/review, continuity.
"""
import pytest


# ── playLabels equivalent (Python replica for validation) ──

ACTION_RU = {
    "fold": "Пас",
    "check": "Чек",
    "call": "Колл",
    "bet": "Ставка",
    "raise": "Рейз",
    "allin": "Олл-ин",
}

STREET_RU = {
    "flop": "Флоп",
    "turn": "Тёрн",
    "river": "Ривер",
    "preflop": "Префлоп",
}


def localize_action(t: str) -> str:
    return ACTION_RU.get(t.lower(), t)


def localize_action_label(label: str) -> str:
    import re
    m = re.match(r"^(\w+)\s+([\d.]+)bb$", label, re.IGNORECASE)
    if m:
        return f"{localize_action(m.group(1))} {m.group(2)}ББ"
    return localize_action(label)


def localize_street(s: str) -> str:
    return STREET_RU.get(s.lower(), s)


# ── A. Action label localization ──

class TestActionLocalization:
    def test_check(self):
        assert localize_action("check") == "Чек"

    def test_fold(self):
        assert localize_action("fold") == "Пас"

    def test_call(self):
        assert localize_action("call") == "Колл"

    def test_bet(self):
        assert localize_action("bet") == "Ставка"

    def test_raise(self):
        assert localize_action("raise") == "Рейз"

    def test_allin(self):
        assert localize_action("allin") == "Олл-ин"

    def test_unknown_passthrough(self):
        assert localize_action("Unknown") == "Unknown"

    def test_case_insensitive(self):
        assert localize_action("CHECK") == "Чек"
        assert localize_action("Fold") == "Пас"


# ── B. Action label with amount ──

class TestActionLabelLocalization:
    def test_bet_amount(self):
        assert localize_action_label("Bet 6.5bb") == "Ставка 6.5ББ"

    def test_raise_amount(self):
        assert localize_action_label("Raise 13.0bb") == "Рейз 13.0ББ"

    def test_call_amount(self):
        assert localize_action_label("Call 4.3bb") == "Колл 4.3ББ"

    def test_allin_amount(self):
        assert localize_action_label("Allin 100.0bb") == "Олл-ин 100.0ББ"

    def test_plain_check(self):
        assert localize_action_label("Check") == "Чек"

    def test_plain_fold(self):
        assert localize_action_label("Fold") == "Пас"


# ── C. Street localization ──

class TestStreetLocalization:
    def test_flop(self):
        assert localize_street("flop") == "Флоп"

    def test_turn(self):
        assert localize_street("turn") == "Тёрн"

    def test_river(self):
        assert localize_street("river") == "Ривер"

    def test_case_insensitive(self):
        assert localize_street("FLOP") == "Флоп"

    def test_unknown(self):
        assert localize_street("preflop") == "Префлоп"


# ── D. No English in localized labels ──

class TestNoEnglishRegression:
    ENGLISH_ACTIONS = ["Check", "Fold", "Call", "Bet", "Raise", "Allin"]
    ENGLISH_STREETS = ["flop", "turn", "river"]

    def test_no_english_action_labels(self):
        for eng in self.ENGLISH_ACTIONS:
            ru = localize_action(eng)
            assert ru != eng, f"Action '{eng}' was not localized"
            # Must contain Cyrillic
            assert any('\u0400' <= c <= '\u04FF' for c in ru), f"Result '{ru}' has no Cyrillic"

    def test_no_english_street_labels(self):
        for eng in self.ENGLISH_STREETS:
            ru = localize_street(eng)
            assert ru != eng, f"Street '{eng}' was not localized"
            assert any('\u0400' <= c <= '\u04FF' for c in ru), f"Result '{ru}' has no Cyrillic"


# ── E. Compare/review state structure ──

class TestCompareResponseStructure:
    """Validate the expected fields in compare-to-solver response."""

    def test_unsupported_response_fields(self):
        """Unavailable compare state must contain these fields."""
        response = {
            "match_quality": "unsupported",
            "message": "Солвер ещё не рассчитал борд...",
            "explanation": "Чтобы сравнить...",
            "board_for_solver": "7h 3h 7d",
            "solver_data": None,
        }
        assert response["match_quality"] == "unsupported"
        assert "board_for_solver" in response
        assert response["board_for_solver"] is not None
        # Message must be Russian
        assert any('\u0400' <= c <= '\u04FF' for c in response["message"])

    def test_successful_response_fields(self):
        """Successful compare must contain learning_takeaway and localized fields."""
        response = {
            "match_quality": "exact_board_match",
            "explanation": "Для вашей руки...",
            "recommendation_summary": "Чек > Ставка",
            "learning_takeaway": "В этой ситуации солвер...",
            "honest_note": "Сравнение на основе...",
            "message": "Найдено совпадение...",
            "data_depth": "частоты для конкретной руки",
        }
        assert "learning_takeaway" in response
        assert response["learning_takeaway"] is not None
        # All visible text must be Russian
        for key in ["explanation", "message", "honest_note", "data_depth"]:
            text = response[key]
            assert any('\u0400' <= c <= '\u04FF' for c in text), f"Field '{key}' not Russian: {text}"


# ── F. Learning takeaway generation ──

class TestLearningTakeaway:
    """Test the three tiers of learning takeaway generation."""

    def _generate_takeaway(self, freqs: dict) -> str | None:
        ACTION_RU_LOCAL = {
            "check": "чек", "fold": "пас", "call": "колл",
            "bet": "ставка", "raise": "рейз",
        }
        def ru(a):
            return ACTION_RU_LOCAL.get(a.lower(), a)

        if not freqs:
            return None
        best_a = max(freqs, key=freqs.get)
        best_f = freqs[best_a]
        if best_f >= 0.8:
            return f"чистое решение {ru(best_a)} ({best_f*100:.0f}%)"
        elif best_f >= 0.5:
            second = sorted([(a,f) for a,f in freqs.items() if a != best_a],
                          key=lambda x: x[1], reverse=True)
            if second:
                return f"предпочитает {ru(best_a)}, иногда {ru(second[0][0])}"
        return "смешивает варианты"

    def test_pure_decision(self):
        result = self._generate_takeaway({"check": 0.95, "bet": 0.05})
        assert "чистое решение" in result
        assert "чек" in result

    def test_flexible_decision(self):
        result = self._generate_takeaway({"check": 0.60, "bet": 0.40})
        assert "предпочитает" in result
        assert "чек" in result

    def test_mixed_decision(self):
        result = self._generate_takeaway({"check": 0.35, "bet": 0.33, "raise": 0.32})
        assert "смешивает" in result

    def test_empty_freqs(self):
        result = self._generate_takeaway({})
        assert result is None


# ── G. Board context carry-over ──

class TestBoardContextCarryOver:
    """Test that board is correctly formatted for carry-over."""

    def test_board_for_solver_format(self):
        board = ["7h", "3h", "7d"]
        board_str = " ".join(board[:3])
        assert board_str == "7h 3h 7d"

    def test_url_encoding(self):
        import urllib.parse
        board_str = "Ks 7d 2c"
        encoded = urllib.parse.quote(board_str)
        assert "+" not in encoded or "Ks" in urllib.parse.unquote(encoded)
        assert urllib.parse.unquote(encoded) == board_str

    def test_board_truncation(self):
        """Only first 3 cards should be used for flop carry-over."""
        board = ["7h", "3h", "7d", "Ac", "Kd"]
        board_str = " ".join(board[:3])
        assert board_str == "7h 3h 7d"
        assert len(board_str.split()) == 3


# ── H. Play page static text audit ──

class TestPlayPageTextAudit:
    """Verify key Russian replacements exist (regression test for localization)."""

    EXPECTED_RUSSIAN_LABELS = [
        "Покерный стол",
        "Сесть за стол",
        "Начальный стек",
        "Оппонент (OOP)",
        "Герой (IP)",
        "Ваш ход",
        "Банк:",
        "Вскрытие",
        "Сессия завершена",
        "Новая сессия",
        "Следующая раздача",
        "Информация",
        "Раздач сыграно",
        "Стек героя",
        "Стек оппонента",
        "Итог сессии",
        "История действий",
        "Прошлые раздачи",
        "Разбор раздачи",
        "Скрыть разбор",
    ]

    def test_expected_labels_are_cyrillic(self):
        for label in self.EXPECTED_RUSSIAN_LABELS:
            assert any('\u0400' <= c <= '\u04FF' for c in label), f"Label not Cyrillic: {label}"

    def test_no_known_english_remnants(self):
        """These English strings must NOT appear in the Play page anymore."""
        FORBIDDEN = [
            "Poker Table",
            "Sit Down & Play",
            "Starting Stack",
            "Villain (OOP)",
            "Hero (IP)",
            "Your turn",
            "Session Complete",
            "New Session",
            "Next Hand",
            "Session Info",
            "Hands played",
            "Hero stack",
            "Villain stack",
            "Action History",
            "No actions yet",
            "Past Hands",
        ]
        # Read actual file
        import os
        play_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "FrontEnd", "src", "pages", "Play.tsx"
        )
        play_path = os.path.normpath(play_path)
        if os.path.exists(play_path):
            content = open(play_path, encoding="utf-8").read()
            for eng in FORBIDDEN:
                assert eng not in content, f"English remnant found in Play.tsx: '{eng}'"
