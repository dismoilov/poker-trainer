/**
 * coachingEngine.ts — Phase 8G
 *
 * Generates structured Russian coaching insights from solver data.
 * This is INTERPRETIVE, not mathematically exact — labeled honestly.
 *
 * Used across: Solver (post-solve), Drill (feedback), Explore (node study).
 */

import { localizeAction } from './localizePoker';

// ── Types ──

export interface CoachingSummary {
  mainIdea: string;
  keyTakeaway: string;
  strictness: 'strict' | 'flexible' | 'hand_dependent';
  strictnessLabel: string;
  strictnessExplanation: string;
  nextStepAdvice: string;
}

export interface DrillCoaching {
  severityLevel: 'perfect' | 'minor' | 'significant' | 'critical';
  severityLabel: string;
  severityEmoji: string;
  severityColor: string;
  learningInsight: string;
  mixedStrategyNote: string | null;
  practiceAdvice: string;
}

export interface NodeTakeaway {
  takeaway: string;
  suggestion: string;
}

// ── A. Post-Solve Coaching Summary ──

/**
 * Generate a coaching summary from root strategy frequencies and solve result.
 * This interprets frequencies into human-readable coaching insights.
 */
export function generateCoachingSummary(
  rootStrategy: Record<string, number> | null | undefined,
  result: {
    converged?: boolean;
    trust_grade?: Record<string, any>;
    metadata?: Record<string, any>;
  } | null,
): CoachingSummary {
  if (!rootStrategy || Object.keys(rootStrategy).length === 0) {
    return {
      mainIdea: 'Запустите расчёт, чтобы получить рекомендации тренера.',
      keyTakeaway: 'Нет данных для анализа.',
      strictness: 'hand_dependent',
      strictnessLabel: 'Нет данных',
      strictnessExplanation: 'Расчёт не выполнен.',
      nextStepAdvice: 'Перейдите в раздел «Настройка» и запустите расчёт.',
    };
  }

  const sorted = Object.entries(rootStrategy).sort(([, a], [, b]) => b - a);
  const [topAction, topFreq] = sorted[0];
  const topRu = localizeAction(topAction);

  // ── Main Idea ──
  let mainIdea: string;
  if (topFreq >= 0.85) {
    mainIdea = `В этом споте солвер почти всегда выбирает ${topRu.toLowerCase()}. Это ваше основное действие.`;
  } else if (topFreq >= 0.60) {
    const secondRu = sorted.length > 1 ? localizeAction(sorted[1][0]).toLowerCase() : '';
    mainIdea = `Основная линия — ${topRu.toLowerCase()}, но иногда нужно балансировать через ${secondRu}.`;
  } else {
    const top2 = sorted.slice(0, 2).map(([a]) => localizeAction(a).toLowerCase());
    mainIdea = `Это спот со смешанной стратегией. Солвер чередует ${top2.join(' и ')} в зависимости от руки.`;
  }

  // ── Key Takeaway ──
  let keyTakeaway: string;
  if (topFreq >= 0.85) {
    keyTakeaway = `Запомните: ${topRu.toLowerCase()} — почти единственное правильное действие. Отклонения здесь стоят EV.`;
  } else if (topFreq >= 0.60) {
    const pct = (topFreq * 100).toFixed(0);
    keyTakeaway = `${topRu} в ${pct}% случаев — хорошее правило. Но обращайте внимание, какими руками стоит отклоняться.`;
  } else {
    keyTakeaway = `Не привязывайтесь к одному действию. В этом споте нужно варьировать решения по рукам.`;
  }

  // ── Strictness ──
  let strictness: CoachingSummary['strictness'];
  let strictnessLabel: string;
  let strictnessExplanation: string;

  if (topFreq >= 0.85) {
    strictness = 'strict';
    strictnessLabel = 'Строго';
    strictnessExplanation = 'Солвер настоятельно рекомендует одно действие. Отклонения снижают EV.';
  } else if (topFreq >= 0.60) {
    strictness = 'flexible';
    strictnessLabel = 'Гибко';
    strictnessExplanation = 'Есть предпочтительное действие, но допустимы варианты. Небольшие отклонения нормальны.';
  } else {
    strictness = 'hand_dependent';
    strictnessLabel = 'Зависит от руки';
    strictnessExplanation = 'Нет одного доминирующего действия. Правильный выбор зависит от конкретных карт.';
  }

  // ── Next Step Advice ──
  let nextStepAdvice: string;
  if (topFreq >= 0.85) {
    nextStepAdvice = 'Потренируйтесь в разделе «Тренировка», чтобы закрепить это решение.';
  } else if (topFreq >= 0.60) {
    nextStepAdvice = 'Изучите матрицу в разделе «Обзор», чтобы понять, какие руки играются по-разному.';
  } else {
    nextStepAdvice = 'Откройте раздел «Обзор» и посмотрите, как частоты распределяются по рукам.';
  }

  return { mainIdea, keyTakeaway, strictness, strictnessLabel, strictnessExplanation, nextStepAdvice };
}

// ── B. Drill Coaching Feedback ──

/**
 * Generate coaching-style drill feedback.
 * Goes beyond "correct/incorrect" to teach the user something.
 */
export function generateDrillCoaching(
  chosenAction: string,
  correctAction: string,
  frequencies: Record<string, number>,
  accuracy: number,
): DrillCoaching {
  const chosenRu = localizeAction(chosenAction);
  const correctRu = localizeAction(correctAction);
  const chosenFreq = frequencies[chosenAction] || 0;
  const correctFreq = frequencies[correctAction] || 0;

  // Check if this is a mixed strategy spot
  const sorted = Object.entries(frequencies).sort(([, a], [, b]) => b - a);
  const isMixed = sorted.length >= 2 && sorted[0][1] < 0.80;
  const isHighlyMixed = sorted.length >= 2 && sorted[0][1] < 0.60;

  // ── Severity ──
  let severityLevel: DrillCoaching['severityLevel'];
  let severityLabel: string;
  let severityEmoji: string;
  let severityColor: string;

  if (accuracy >= 1.0) {
    severityLevel = 'perfect';
    severityLabel = 'Отлично!';
    severityEmoji = '🎯';
    severityColor = 'emerald';
  } else if (chosenFreq >= 0.30) {
    severityLevel = 'minor';
    severityLabel = 'Небольшое отклонение';
    severityEmoji = '👍';
    severityColor = 'green';
  } else if (chosenFreq >= 0.10) {
    severityLevel = 'significant';
    severityLabel = 'Заметная ошибка';
    severityEmoji = '⚠️';
    severityColor = 'amber';
  } else {
    severityLevel = 'critical';
    severityLabel = 'Серьёзная ошибка';
    severityEmoji = '❌';
    severityColor = 'red';
  }

  // ── Learning Insight ──
  let learningInsight: string;
  if (accuracy >= 1.0) {
    if (correctFreq >= 0.85) {
      learningInsight = `Вы правильно определили, что ${correctRu.toLowerCase()} — единственное верное действие в этом споте.`;
    } else {
      learningInsight = `Отлично выбрано! ${correctRu} — самое частое действие солвера, даже в смешанном споте.`;
    }
  } else if (chosenFreq >= 0.30) {
    learningInsight = `Ваш выбор (${chosenRu.toLowerCase()}) допустим — солвер тоже использует его в ${(chosenFreq * 100).toFixed(0)}% случаев. Но основная линия — ${correctRu.toLowerCase()} (${(correctFreq * 100).toFixed(0)}%).`;
  } else if (chosenFreq >= 0.10) {
    learningInsight = `${chosenRu} — часть смешанной стратегии, но применяется редко (${(chosenFreq * 100).toFixed(0)}%). В большинстве случаев лучше ${correctRu.toLowerCase()}.`;
  } else {
    if (chosenFreq === 0) {
      learningInsight = `Солвер никогда не выбирает ${chosenRu.toLowerCase()} в этом споте. Правильное действие — ${correctRu.toLowerCase()} (${(correctFreq * 100).toFixed(0)}%).`;
    } else {
      learningInsight = `${chosenRu} почти не используется солвером (${(chosenFreq * 100).toFixed(0)}%). Подумайте, почему ${correctRu.toLowerCase()} здесь лучше.`;
    }
  }

  // ── Mixed Strategy Note ──
  let mixedStrategyNote: string | null = null;
  if (isMixed && accuracy < 1.0) {
    if (isHighlyMixed) {
      mixedStrategyNote = 'Это спот со смешанной стратегией — солвер использует разные действия для непредсказуемости. Нет единственного «правильного» ответа, но одни варианты лучше других.';
    } else {
      mixedStrategyNote = 'Солвер иногда отклоняется от основной линии в этом споте. Это нормально для баланса стратегии.';
    }
  }

  // ── Practice Advice ──
  let practiceAdvice: string;
  if (accuracy >= 1.0) {
    practiceAdvice = 'Продолжайте тренировку. Попробуйте ответить ещё несколько вопросов для закрепления.';
  } else if (severityLevel === 'minor') {
    practiceAdvice = 'Хороший уровень! Обращайте внимание на нюансы — они отличают хорошую игру от отличной.';
  } else if (severityLevel === 'significant') {
    practiceAdvice = 'Попробуйте изучить этот спот в разделе «Обзор», чтобы понять логику солвера.';
  } else {
    practiceAdvice = 'Рекомендуем повторить этот спот несколько раз и изучить матрицу частот в «Обзоре».';
  }

  return {
    severityLevel,
    severityLabel,
    severityEmoji,
    severityColor,
    learningInsight,
    mixedStrategyNote,
    practiceAdvice,
  };
}

// ── C. Explore Node Takeaway ──

/**
 * Generate a one-liner takeaway for a tree node in Explore.
 * Helps the user understand what this decision point is about.
 */
export function generateNodeTakeaway(
  actions: Array<{ id: string; label: string; type: string }>,
  strategy: Record<string, Record<string, number>> | null,
  player: string,
  street: string,
): NodeTakeaway {
  const streetRu: Record<string, string> = {
    preflop: 'префлопе', flop: 'флопе', turn: 'тёрне', river: 'ривере',
  };
  const posRu = player === 'IP' || player === 'BTN'
    ? 'в позиции'
    : 'без позиции';
  const streetLabel = streetRu[street] || street;

  if (!strategy || Object.keys(strategy).length === 0) {
    return {
      takeaway: `Решение ${posRu} на ${streetLabel}.`,
      suggestion: 'Выберите руку в матрице для подробного анализа.',
    };
  }

  // Compute aggregate frequencies across all hands
  const aggFreqs: Record<string, number> = {};
  let totalHands = 0;
  for (const handFreqs of Object.values(strategy)) {
    totalHands++;
    for (const [action, freq] of Object.entries(handFreqs)) {
      aggFreqs[action] = (aggFreqs[action] || 0) + freq;
    }
  }
  // Normalize
  for (const action of Object.keys(aggFreqs)) {
    aggFreqs[action] /= totalHands;
  }

  const sorted = Object.entries(aggFreqs).sort(([, a], [, b]) => b - a);
  if (sorted.length === 0) {
    return {
      takeaway: `Решение ${posRu} на ${streetLabel}.`,
      suggestion: 'Выберите руку в матрице для подробного анализа.',
    };
  }

  const [topAction, topFreq] = sorted[0];
  const topRu = localizeAction(topAction);

  let takeaway: string;
  let suggestion: string;

  if (topFreq >= 0.80) {
    takeaway = `${posRu.charAt(0).toUpperCase() + posRu.slice(1)} на ${streetLabel}: рейндж в основном играет через ${topRu.toLowerCase()} (${(topFreq * 100).toFixed(0)}%).`;
    suggestion = 'Обратите внимание, какие руки отклоняются от основной линии.';
  } else if (topFreq >= 0.55) {
    const secRu = sorted.length > 1 ? localizeAction(sorted[1][0]).toLowerCase() : '';
    takeaway = `${posRu.charAt(0).toUpperCase() + posRu.slice(1)} на ${streetLabel}: преимущественно ${topRu.toLowerCase()}, но часть рук играет через ${secRu}.`;
    suggestion = 'Изучите, какие руки используют альтернативное действие.';
  } else {
    takeaway = `${posRu.charAt(0).toUpperCase() + posRu.slice(1)} на ${streetLabel}: смешанная стратегия. Действие зависит от конкретной руки.`;
    suggestion = 'Нажмите на ячейки матрицы, чтобы увидеть разбивку по рукам.';
  }

  return { takeaway, suggestion };
}
