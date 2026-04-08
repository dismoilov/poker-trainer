/**
 * localizePoker.ts — Phase 8F
 *
 * Central localization for all poker terminology.
 * Used across Drill, Explore, SpotSelector, Solver to ensure
 * a fully Russian, beginner-friendly experience.
 */

// ── Action Labels ──

const ACTION_MAP: Record<string, string> = {
  fold: 'Фолд',
  check: 'Чек',
  call: 'Колл',
  bet: 'Бет',
  raise: 'Рейз',
  'all-in': 'Олл-ин',
  allin: 'Олл-ин',
};

/**
 * Localize an action label from English to Russian.
 * Handles: "Fold", "Check", "Call", "Bet 33%", "Bet 50%",
 * "Bet 75%", "Bet 150%", "Raise", "Raise 2.5x", etc.
 */
export function localizeAction(label: string): string {
  if (!label) return label;

  const lower = label.toLowerCase().trim();

  // Exact match
  if (ACTION_MAP[lower]) return ACTION_MAP[lower];

  // "Bet X%", "Bet Xpot", "bet_50", "bet_67" etc.
  if (lower.startsWith('bet')) {
    let suffix = label.slice(3).trim();
    // Handle underscore format: bet_50 → "50", bet_67 → "67"
    if (suffix.startsWith('_')) {
      suffix = suffix.slice(1) + '%';
    }
    return suffix ? `Бет ${suffix}` : 'Бет';
  }

  // "Raise X" or "Raise 2.5x"
  if (lower.startsWith('raise')) {
    const suffix = label.slice(5).trim();
    return suffix ? `Рейз ${suffix}` : 'Рейз';
  }

  // "All-in" variants
  if (lower.includes('all') && lower.includes('in')) {
    return 'Олл-ин';
  }

  // Already Russian or unknown — return as-is
  return label;
}

/**
 * Localize a tree node label like "BB Check", "BTN Bet 33%", "BB bet 75%".
 * Keeps the position prefix and localizes the action part.
 */
export function localizeTreeLabel(label: string): string {
  if (!label) return label;

  // Known position prefixes
  const positions = ['BB', 'SB', 'BTN', 'CO', 'HJ', 'MP', 'UTG', 'EP'];

  for (const pos of positions) {
    if (label.startsWith(pos + ' ') || label.startsWith(pos.toLowerCase() + ' ')) {
      const actionPart = label.slice(pos.length + 1);
      return `${pos} ${localizeAction(actionPart)}`;
    }
  }

  // No position prefix — just localize as action
  return localizeAction(label);
}

// ── Position Labels ──

const POSITION_MAP: Record<string, string> = {
  BTN: 'Баттон',
  SB: 'Мал. блайнд',
  BB: 'Бол. блайнд',
  CO: 'Катофф',
  HJ: 'Хайджек',
  MP: 'Мидл',
  UTG: 'Андер-зе-ган',
  EP: 'Ранняя поз.',
};

const POSITION_SHORT: Record<string, string> = {
  BTN: 'BTN',
  SB: 'SB',
  BB: 'BB',
  CO: 'CO',
  HJ: 'HJ',
  MP: 'MP',
  UTG: 'UTG',
  EP: 'EP',
};

/**
 * Full Russian position name.
 */
export function localizePosition(pos: string): string {
  return POSITION_MAP[pos.toUpperCase()] || pos;
}

/**
 * Position with Russian name + short code.
 * Example: "Баттон (BTN)"
 */
export function localizePositionFull(pos: string): string {
  const upper = pos.toUpperCase();
  const ru = POSITION_MAP[upper];
  return ru ? `${ru} (${POSITION_SHORT[upper] || upper})` : pos;
}

// ── Format Labels ──

const FORMAT_MAP: Record<string, string> = {
  SRP: 'Один рейз',
  '3bet': 'Три-бет',
  '4bet': 'Четыре-бет',
  squeeze: 'Сквиз',
};

const FORMAT_DESCRIPTION: Record<string, string> = {
  SRP: 'Обычный банк после одного рейза',
  '3bet': 'Банк после ре-рейза (3-бет)',
  '4bet': 'Банк после 4-бета',
  squeeze: 'Банк после сквиза',
};

/**
 * Localize a format code to Russian.
 */
export function localizeFormat(fmt: string): string {
  return FORMAT_MAP[fmt] || fmt;
}

/**
 * Get a longer format description.
 */
export function localizeFormatDescription(fmt: string): string {
  return FORMAT_DESCRIPTION[fmt] || fmt;
}

// ── Street Labels ──

const STREET_MAP: Record<string, string> = {
  preflop: 'Префлоп',
  flop: 'Флоп',
  turn: 'Тёрн',
  river: 'Ривер',
};

export function localizeStreet(street: string): string {
  return STREET_MAP[street.toLowerCase()] || street;
}

// ── Spot Name Humanization ──

/**
 * Generate a human-readable Russian spot name.
 *
 * Input: "SRP BTN vs BB Flop"
 * Output: "Один рейз: Баттон vs Бол. блайнд • Флоп"
 *
 * Input: "3Bet CO vs BB Turn"
 * Output: "Три-бет: Катофф vs Бол. блайнд • Тёрн"
 */
export function localizeSpotName(
  name: string,
  format?: string,
  positions?: [string, string],
  streets?: string[],
): string {
  // If we have structured data, build from it
  if (format && positions && positions.length >= 2) {
    const fmtRu = localizeFormat(format);
    const pos1 = localizePosition(positions[0]);
    const pos2 = localizePosition(positions[1]);

    // Determine street from streets array or parse from name
    let streetRu = '';
    if (streets && streets.length > 0) {
      const lastStreet = streets[streets.length - 1];
      streetRu = localizeStreet(lastStreet);
    } else {
      // Try to extract from name
      const lowerName = name.toLowerCase();
      if (lowerName.includes('river')) streetRu = 'Ривер';
      else if (lowerName.includes('turn')) streetRu = 'Тёрн';
      else if (lowerName.includes('flop')) streetRu = 'Флоп';
    }

    // Add parenthetical info if present (e.g., "check-check", "bet-call")
    let extra = '';
    const parenMatch = name.match(/\(([^)]+)\)/);
    if (parenMatch) {
      const rawExtra = parenMatch[1].toLowerCase();
      if (rawExtra.includes('check-check') || rawExtra === 'cc') {
        extra = ' (чек-чек)';
      } else if (rawExtra.includes('bet-call') || rawExtra === 'bc') {
        extra = ' (бет-колл)';
      } else if (rawExtra.includes('bet-raise') || rawExtra === 'br') {
        extra = ' (бет-рейз)';
      } else {
        extra = ` (${parenMatch[1]})`;
      }
    } else if (name.toLowerCase().includes('check-check') || name.includes('-cc')) {
      extra = ' (чек-чек)';
    } else if (name.toLowerCase().includes('bet-call') || name.includes('-bc')) {
      extra = ' (бет-колл)';
    }

    return streetRu
      ? `${fmtRu}: ${pos1} vs ${pos2} • ${streetRu}${extra}`
      : `${fmtRu}: ${pos1} vs ${pos2}${extra}`;
  }

  // Fallback: try to parse from the raw name string
  return name;
}

// ── Strategy Explanation Helpers ──

/**
 * Describe a strategy result for beginners.
 * Used in Drill feedback to explain pure vs mixed strategies.
 */
export function describeStrategy(
  frequencies: Record<string, number>,
  actionLabels?: Record<string, string>,
): {
  type: 'pure' | 'mixed';
  typeLabel: string;
  summary: string;
} {
  const entries = Object.entries(frequencies).sort(([, a], [, b]) => b - a);
  if (entries.length === 0) {
    return { type: 'pure', typeLabel: 'Нет данных', summary: 'Нет данных о стратегии.' };
  }

  const [topId, topFreq] = entries[0];
  const topLabel = (actionLabels?.[topId]) || localizeAction(topId);

  if (topFreq >= 0.95) {
    return {
      type: 'pure',
      typeLabel: 'Чистое действие',
      summary: `Солвер всегда выбирает ${topLabel.toLowerCase()} в этой ситуации.`,
    };
  }

  if (topFreq >= 0.80) {
    return {
      type: 'pure',
      typeLabel: 'Почти всегда',
      summary: `В основном ${topLabel.toLowerCase()} (${(topFreq * 100).toFixed(0)}%). Иногда другие действия для баланса.`,
    };
  }

  if (entries.length >= 2) {
    const [secId, secFreq] = entries[1];
    const secLabel = (actionLabels?.[secId]) || localizeAction(secId);
    return {
      type: 'mixed',
      typeLabel: 'Смешанная стратегия',
      summary: `Солвер чередует: ${topLabel.toLowerCase()} (${(topFreq * 100).toFixed(0)}%) и ${secLabel.toLowerCase()} (${(secFreq * 100).toFixed(0)}%). Это нормально — GTO использует разные действия для непредсказуемости.`,
    };
  }

  return {
    type: 'pure',
    typeLabel: 'Рекомендация',
    summary: `Рекомендуется ${topLabel.toLowerCase()} (${(topFreq * 100).toFixed(0)}%).`,
  };
}
