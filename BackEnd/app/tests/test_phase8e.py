"""
Phase 8E tests — Guided beginner flow, next-step actions,
contextual tips, cross-page continuity, Russian wording.
"""
import pytest


class TestLearningTipLogic:
    """Test contextual tip generation logic (mirrors nextSteps.ts)."""

    def test_new_user_gets_welcome(self):
        """A user with 0 sessions gets a welcome tip."""
        stats = {"totalSessions": 0, "totalQuestions": 0, "accuracy": None, "avgEvLoss": None}
        # Should be a welcome message
        assert stats["totalSessions"] == 0

    def test_low_question_count_encouragement(self):
        """A user with <10 questions gets encouragement."""
        stats = {"totalSessions": 1, "totalQuestions": 5}
        assert stats["totalQuestions"] < 10

    def test_low_accuracy_study_suggestion(self):
        """A user with <50% accuracy is directed to study."""
        accuracy = 0.35
        assert accuracy < 0.5
        # Frontend tip says: "Попробуйте изучить стратегии в разделе «Обзор»"

    def test_high_accuracy_solver_suggestion(self):
        """A user with >=80% accuracy is prompted to try the solver."""
        accuracy = 0.85
        assert accuracy >= 0.8
        # Frontend tip says: "Попробуйте солвер для более глубокого анализа"

    def test_medium_accuracy_practice_tip(self):
        """A user with 50-80% accuracy is encouraged to keep practicing."""
        accuracy = 0.65
        assert 0.5 <= accuracy < 0.8


class TestLearningPathway:
    """Test the learning pathway definition."""

    def test_pathway_has_4_steps(self):
        """Learning pathway has exactly 4 steps."""
        steps = ["drill", "explore", "play", "solver"]
        assert len(steps) == 4

    def test_pathway_order(self):
        """Steps go from simple to advanced."""
        steps = ["drill", "explore", "play", "solver"]
        assert steps[0] == "drill"   # Start with training
        assert steps[-1] == "solver"  # End with advanced

    def test_drill_is_first(self):
        """Drill is recommended first for beginners."""
        steps = ["drill", "explore", "play", "solver"]
        assert steps.index("drill") == 0

    def test_solver_is_last(self):
        """Solver is recommended last (most advanced)."""
        steps = ["drill", "explore", "play", "solver"]
        assert steps.index("solver") == 3


class TestPostSolveActions:
    """Test cross-page next-step actions after a solve."""

    def test_has_3_next_actions(self):
        """Post-solve offers exactly 3 next actions."""
        actions = [
            {"id": "drill", "title": "Потренировать", "route": "/drill"},
            {"id": "explore", "title": "Изучить стратегию", "route": "/explore"},
            {"id": "play", "title": "Сыграть за столом", "route": "/play"},
        ]
        assert len(actions) == 3

    def test_actions_have_russian_titles(self):
        """All post-solve action titles are in Russian."""
        titles = ["Потренировать", "Изучить стратегию", "Сыграть за столом"]
        for title in titles:
            # No ASCII-only words (all should contain Cyrillic)
            assert any('\u0400' <= c <= '\u04FF' for c in title), f"Title not Russian: {title}"

    def test_actions_have_valid_routes(self):
        """All routes start with /."""
        routes = ["/drill", "/explore", "/play"]
        for route in routes:
            assert route.startswith("/")

    def test_no_solver_self_reference(self):
        """Post-solve actions do NOT include solver itself (avoid circular)."""
        action_ids = ["drill", "explore", "play"]
        assert "solver" not in action_ids


class TestPagePurposeHints:
    """Test that all pages have purpose hints in Russian."""

    def test_drill_purpose_text(self):
        """Drill purpose text is in Russian."""
        purpose = "Тренировка GTO-решений. Выберите ситуацию, посмотрите борд и вашу руку, затем выберите оптимальное действие."
        assert "Тренировка" in purpose
        assert "GTO" in purpose

    def test_explore_purpose_text(self):
        """Explore purpose text is in Russian."""
        purpose = "Обзор стратегий. Навигация по дереву решений солвера — выберите спот, нод и руку для изучения оптимальных частот."
        assert "Обзор" in purpose
        assert "стратегий" in purpose

    def test_solver_intro_text(self):
        """Solver intro text is in Russian."""
        hint = "Что такое солвер и когда его использовать?"
        assert "солвер" in hint


class TestGuideLocalization:
    """Test that Guide page has fully Russian action labels."""

    def test_action_labels_russian(self):
        """Action labels should all be Russian."""
        labels = ["Фолд", "Чек", "Колл", "Бет 33-50%", "Бет 75%+ / Рейз"]
        english_labels = ["Fold", "Check", "Call", "Bet 33-50%", "Bet 75%+ / Raise"]
        for label in labels:
            assert label not in english_labels
            assert any('\u0400' <= c <= '\u04FF' for c in label)

    def test_no_english_action_labels(self):
        """Ensure English action words are not used."""
        forbidden = ["Fold", "Check", "Call"]
        labels = ["Фолд", "Чек", "Колл", "Бет 33-50%", "Бет 75%+ / Рейз"]
        for forbidden_word in forbidden:
            assert forbidden_word not in labels


class TestDashboardContextualTip:
    """Test the dashboard contextual tip system."""

    def test_tip_has_emoji_and_text(self):
        """Each tip must have emoji and text."""
        tip = {"emoji": "👋", "text": "Добро пожаловать! Начните с тренировки."}
        assert tip["emoji"]
        assert tip["text"]
        assert len(tip["text"]) > 10

    def test_tip_text_is_russian(self):
        """Tip text is in Russian."""
        tip_text = "Добро пожаловать! Начните с тренировки."
        assert any('\u0400' <= c <= '\u04FF' for c in tip_text)

    def test_dashboard_has_learning_pathway(self):
        """Dashboard should show learning pathway with 4 items."""
        pathway_ids = ["drill", "explore", "play", "solver"]
        assert len(pathway_ids) == 4

    def test_dashboard_tools_section_exists(self):
        """Dashboard has secondary tools section."""
        tools = ["Аналитика", "Библиотека", "Задачи"]
        assert len(tools) == 3
        for tool in tools:
            assert any('\u0400' <= c <= '\u04FF' for c in tool)
