/**
 * Simple Solver Report Generator — Phase 8D
 *
 * Generates beginner-friendly Russian text from raw solver results.
 * This is the first thing a user sees after a solve completes.
 */

export interface SimpleReport {
  /** Main recommendation: "Чаще всего: чек (72%)" */
  mainRecommendation: string;
  /** Strategy type explanation */
  strategyType: 'pure' | 'mixed' | 'even';
  strategyLabel: string;
  strategyExplanation: string;
  /** Trust level in plain Russian */
  trustLevel: 'high' | 'medium' | 'low';
  trustLabel: string;
  trustReason: string;
  /** One-liner scope note */
  scopeNote: string;
  /** Action breakdown for visual display */
  actions: Array<{ name: string; nameRu: string; frequency: number }>;
}

const ACTION_NAMES_RU: Record<string, string> = {
  check: 'Чек',
  fold: 'Фолд',
  call: 'Колл',
  bet25: 'Бет 25%',
  bet_25: 'Бет 25%',
  bet33: 'Бет 33%',
  bet_33: 'Бет 33%',
  bet50: 'Бет 50%',
  bet_50: 'Бет 50%',
  bet67: 'Бет 67%',
  bet_67: 'Бет 67%',
  bet75: 'Бет 75%',
  bet_75: 'Бет 75%',
  bet100: 'Бет 100%',
  bet_100: 'Бет 100%',
  bet150: 'Бет 150%',
  bet_150: 'Бет 150%',
  raise: 'Рейз',
  allin: 'Олл-ин',
};

function actionRu(name: string): string {
  return ACTION_NAMES_RU[name] || name.replace(/_/g, ' ');
}

/** Generate a simple report from solver result data */
export function generateSimpleReport(
  rootStrategy: Record<string, number> | null | undefined,
  result: {
    converged?: boolean;
    iterations?: number;
    convergence_metric?: number;
    exploitability?: Record<string, any>;
    trust_grade?: Record<string, any>;
    metadata?: Record<string, any>;
  } | null,
): SimpleReport {
  // Default / empty state
  if (!rootStrategy || Object.keys(rootStrategy).length === 0) {
    return {
      mainRecommendation: 'Нет данных для рекомендации',
      strategyType: 'even',
      strategyLabel: 'Неизвестно',
      strategyExplanation: 'Запустите расчёт, чтобы получить рекомендацию.',
      trustLevel: 'low',
      trustLabel: 'Нет данных',
      trustReason: 'Расчёт не выполнен.',
      scopeNote: 'Запустите солвер для получения результата.',
      actions: [],
    };
  }

  // Sort actions by frequency
  const sorted = Object.entries(rootStrategy)
    .sort(([, a], [, b]) => b - a);
  const [topAction, topFreq] = sorted[0];
  const topRu = actionRu(topAction);

  // Build actions list
  const actions = sorted
    .filter(([, f]) => f >= 0.01)
    .map(([name, frequency]) => ({
      name,
      nameRu: actionRu(name),
      frequency,
    }));

  // Main recommendation
  let mainRecommendation: string;
  if (topFreq >= 0.85) {
    mainRecommendation = `Чаще всего: ${topRu} (${(topFreq * 100).toFixed(0)}%)`;
  } else if (topFreq >= 0.60) {
    mainRecommendation = `Обычно лучше: ${topRu} (${(topFreq * 100).toFixed(0)}%)`;
  } else {
    const topTwo = sorted.slice(0, 2).map(([a, f]) => `${actionRu(a)} ${(f * 100).toFixed(0)}%`);
    mainRecommendation = `Смешанная стратегия: ${topTwo.join(' и ')}`;
  }

  // Strategy type
  let strategyType: SimpleReport['strategyType'];
  let strategyLabel: string;
  let strategyExplanation: string;
  if (topFreq >= 0.85) {
    strategyType = 'pure';
    strategyLabel = 'Чистая стратегия';
    strategyExplanation = `Солвер рекомендует почти всегда ${topRu.toLowerCase()}. Небольшие отклонения допустимы.`;
  } else if (topFreq >= 0.55) {
    strategyType = 'mixed';
    strategyLabel = 'Смешанная стратегия';
    const secondary = sorted.length > 1 ? `Часть рук играет через ${actionRu(sorted[1][0]).toLowerCase()}.` : '';
    strategyExplanation = `Основная линия — ${topRu.toLowerCase()}, но это не единственный вариант. ${secondary} Небольшие отклонения нормальны.`;
  } else {
    strategyType = 'even';
    strategyLabel = 'Сильно смешанная стратегия';
    strategyExplanation = `Нет одного доминирующего действия. Нужно выбирать в зависимости от конкретной руки. Солвер распределяет частоты между несколькими вариантами.`;
  }

  // Trust level
  let trustLevel: SimpleReport['trustLevel'];
  let trustLabel: string;
  let trustReason: string;

  const exploitMbb = result?.exploitability?.exploitability_mbb_per_hand;
  const gradeStr = result?.trust_grade?.grade || '';
  const converged = result?.converged;

  if (gradeStr === 'VALIDATED_LIMITED_SCOPE' && converged && exploitMbb != null && exploitMbb < 20) {
    trustLevel = 'high';
    trustLabel = 'Высокая надёжность';
    trustReason = 'Расчёт сошёлся, прошёл проверку и имеет низкую эксплоитабельность.';
  } else if (converged && (gradeStr.includes('DEMO') || gradeStr.includes('VALIDATED'))) {
    trustLevel = 'medium';
    trustLabel = 'Средняя надёжность';
    trustReason = 'Расчёт сошёлся, но сделан в упрощённой модели с ограниченными диапазонами.';
  } else {
    trustLevel = 'low';
    trustLabel = 'Низкая надёжность';
    trustReason = converged
      ? 'Расчёт завершён, но не все проверки пройдены. Результат ориентировочный.'
      : 'Расчёт не полностью сошёлся. Результат может быть неточным.';
  }

  // Scope note — Phase 18B: added turn+river depth
  const streetDepth = result?.metadata?.street_depth;
  const scopeNote = streetDepth === 'flop_plus_turn_plus_river'
    ? 'Расчёт включает флоп, тёрн и ривер с ограниченными диапазонами.'
    : streetDepth === 'flop_plus_turn'
    ? 'Расчёт включает флоп и ограниченный тёрн. Ривер не рассчитан.'
    : 'Расчёт только для флопа с маленькими диапазонами (~50 комбо/сторону).';

  return {
    mainRecommendation,
    strategyType,
    strategyLabel,
    strategyExplanation,
    trustLevel,
    trustLabel,
    trustReason,
    scopeNote,
    actions,
  };
}
