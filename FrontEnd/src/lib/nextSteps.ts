/**
 * NextSteps Helper — Phase 8E
 *
 * Generates contextual "what to do next" suggestions
 * based on user activity state.
 */

export interface NextStepSuggestion {
  id: string;
  title: string;
  description: string;
  route: string;
  icon: 'target' | 'explore' | 'play' | 'solver' | 'analytics';
  priority: 'primary' | 'secondary';
}

export interface LearningTip {
  emoji: string;
  text: string;
}

/**
 * Generate a contextual learning tip based on user stats.
 */
export function getLearningTip(stats: {
  totalSessions?: number;
  totalQuestions?: number;
  accuracy?: number;
  avgEvLoss?: number;
} | null): LearningTip {
  if (!stats || !stats.totalSessions || stats.totalSessions === 0) {
    return {
      emoji: '👋',
      text: 'Добро пожаловать! Начните с тренировки — выберите спот и попробуйте решить несколько ситуаций по GTO.',
    };
  }

  if (stats.totalQuestions && stats.totalQuestions < 10) {
    return {
      emoji: '🎯',
      text: `Вы ответили на ${stats.totalQuestions} вопросов. Продолжайте тренировку, чтобы закрепить навыки!`,
    };
  }

  if (stats.accuracy != null && stats.accuracy < 0.5) {
    return {
      emoji: '📚',
      text: `Ваша точность ${(stats.accuracy * 100).toFixed(0)}%. Попробуйте изучить стратегии в разделе «Обзор», чтобы лучше понять GTO-решения.`,
    };
  }

  if (stats.accuracy != null && stats.accuracy >= 0.8) {
    return {
      emoji: '🏆',
      text: `Отличная точность ${(stats.accuracy * 100).toFixed(0)}%! Попробуйте солвер для более глубокого анализа ситуаций.`,
    };
  }

  if (stats.accuracy != null) {
    return {
      emoji: '💪',
      text: `Точность ${(stats.accuracy * 100).toFixed(0)}%. Хороший прогресс! Продолжайте тренировку, чтобы закрепить результат.`,
    };
  }

  return {
    emoji: '🎮',
    text: 'Сыграйте партию за столом и проверьте свои знания на практике.',
  };
}

/**
 * Learning pathway steps — the recommended order.
 */
export const LEARNING_PATHWAY = [
  {
    step: 1,
    id: 'drill',
    title: 'Тренировка',
    subtitle: 'Начните здесь',
    description: 'Решайте GTO-ситуации и получайте обратную связь',
    route: '/drill',
    icon: 'target' as const,
    color: 'emerald',
  },
  {
    step: 2,
    id: 'explore',
    title: 'Обзор',
    subtitle: 'Изучайте стратегии',
    description: 'Навигация по дереву решений и матрица частот',
    route: '/explore',
    icon: 'explore' as const,
    color: 'blue',
  },
  {
    step: 3,
    id: 'play',
    title: 'Игра',
    subtitle: 'Практика за столом',
    description: 'Играйте и сравнивайте решения с солвером',
    route: '/play',
    icon: 'play' as const,
    color: 'amber',
  },
  {
    step: 4,
    id: 'solver',
    title: 'Солвер',
    subtitle: 'Глубокий анализ',
    description: 'Рассчитайте оптимальную стратегию самостоятельно',
    route: '/solver',
    icon: 'solver' as const,
    color: 'violet',
  },
] as const;

/**
 * Post-solve next actions for the solver result page.
 */
export const POST_SOLVE_ACTIONS = [
  {
    id: 'drill',
    title: 'Потренировать',
    description: 'Закрепите знания на практике',
    route: '/drill',
    emoji: '🎯',
  },
  {
    id: 'explore',
    title: 'Изучить стратегию',
    description: 'Подробнее о дереве решений',
    route: '/explore',
    emoji: '📊',
  },
  {
    id: 'play',
    title: 'Сыграть за столом',
    description: 'Проверьте себя в реальной игре',
    route: '/play',
    emoji: '🎮',
  },
] as const;
