/**
 * humanizeError.ts — Translate raw solver errors into structured Russian recovery UX.
 *
 * The backend returns English technical errors like:
 *   "IP range too large (55 combos, max 50)"
 *   "Tree too large (2500 nodes, max 2000)"
 *   "OOP range has 0 valid combos"
 *
 * This module converts those into user-friendly Russian messages with:
 *   - title: short headline
 *   - description: plain-language explanation
 *   - suggestion: what the user can do
 *   - action?: { label, handler } for one-click fix
 */

export interface HumanizedError {
  title: string;
  description: string;
  suggestion: string;
  icon: string;
  action?: {
    label: string;
    type: 'reduce_range' | 'reduce_iterations' | 'disable_turn' | 'general';
  };
}

interface ErrorPattern {
  test: (msg: string) => boolean;
  humanize: (msg: string) => HumanizedError;
}

function extractNumbers(msg: string): { current?: number; max?: number } {
  const match = msg.match(/(\d+)\s*combos?,\s*max\s*(\d+)/i);
  if (match) return { current: parseInt(match[1]), max: parseInt(match[2]) };
  const matchNodes = msg.match(/(\d+)\s*nodes?,\s*max\s*(\d+)/i);
  if (matchNodes) return { current: parseInt(matchNodes[1]), max: parseInt(matchNodes[2]) };
  return {};
}

const ERROR_PATTERNS: ErrorPattern[] = [
  // IP range too large
  {
    test: (msg) => /IP range too large/i.test(msg),
    humanize: (msg) => {
      const { current, max } = extractNumbers(msg);
      return {
        title: 'Диапазон IP слишком широкий',
        description: current && max
          ? `В диапазоне IP ${current} комбинаций, а максимум — ${max}. Солвер не справится с таким объёмом.`
          : 'Диапазон IP содержит слишком много рук для расчёта.',
        suggestion: 'Уберите несколько рук из диапазона или выберите более узкий пресет.',
        icon: '📊',
        action: { label: 'Сузить диапазон', type: 'reduce_range' },
      };
    },
  },
  // OOP range too large
  {
    test: (msg) => /OOP range too large/i.test(msg),
    humanize: (msg) => {
      const { current, max } = extractNumbers(msg);
      return {
        title: 'Диапазон OOP слишком широкий',
        description: current && max
          ? `В диапазоне OOP ${current} комбинаций, а максимум — ${max}. Солвер не справится с таким объёмом.`
          : 'Диапазон OOP содержит слишком много рук для расчёта.',
        suggestion: 'Уберите несколько рук из диапазона или выберите более узкий пресет.',
        icon: '📊',
        action: { label: 'Сузить диапазон', type: 'reduce_range' },
      };
    },
  },
  // Tree too large
  {
    test: (msg) => /tree too large/i.test(msg) || /action tree too large/i.test(msg),
    humanize: (msg) => {
      const { current, max } = extractNumbers(msg);
      return {
        title: 'Дерево решений слишком большое',
        description: current && max
          ? `Дерево содержит ${current} узлов (лимит ${max}). Слишком много размеров бетов или рейзов.`
          : 'Структура дерева слишком сложная для расчёта.',
        suggestion: 'Уменьшите число размеров бетов или ограничьте макс. рейзов на улице.',
        icon: '🌳',
        action: { label: 'Упростить настройки', type: 'general' },
      };
    },
  },
  // Too many matchups
  {
    test: (msg) => /too many matchups/i.test(msg),
    humanize: (msg) => {
      const { current, max } = extractNumbers(msg);
      return {
        title: 'Слишком много пар рук',
        description: current && max
          ? `${current} комбинаций пар (лимит ${max}). Уменьшите оба диапазона.`
          : 'Комбинация двух диапазонов даёт слишком много пересечений.',
        suggestion: 'Сузьте один или оба диапазона — используйте только основные руки.',
        icon: '🔗',
        action: { label: 'Сузить диапазоны', type: 'reduce_range' },
      };
    },
  },
  // 0 valid combos
  {
    test: (msg) => /0 valid combos/i.test(msg),
    humanize: () => ({
      title: 'Нет подходящих рук',
      description: 'Все руки в диапазоне пересекаются с картами борда. Ни одна комбинация не может быть разыграна.',
      suggestion: 'Проверьте борд и диапазон — карты не должны совпадать.',
      icon: '🃏',
    }),
  },
  // No valid matchups
  {
    test: (msg) => /no valid matchups/i.test(msg),
    humanize: () => ({
      title: 'Нет возможных раздач',
      description: 'Все комбинации IP и OOP пересекаются между собой или с бордом.',
      suggestion: 'Измените диапазоны так, чтобы у игроков были разные руки.',
      icon: '⚠️',
    }),
  },
  // Duplicate board cards
  {
    test: (msg) => /duplicate board/i.test(msg),
    humanize: () => ({
      title: 'Дублирующиеся карты на борде',
      description: 'На борде не может быть двух одинаковых карт.',
      suggestion: 'Уберите дубликат и выберите другую карту.',
      icon: '🔄',
    }),
  },
  // Need at least 3 board cards
  {
    test: (msg) => /at least 3 board cards/i.test(msg) || /need at least 3/i.test(msg),
    humanize: () => ({
      title: 'Недостаточно карт на борде',
      description: 'Для расчёта нужно минимум 3 карты (флоп).',
      suggestion: 'Добавьте карты на борд — выберите 3 карты для флопа.',
      icon: '🃏',
    }),
  },
  // Turn-specific errors
  {
    test: (msg) => /turn.*too expensive/i.test(msg) || /max_turn_cards.*exceeds/i.test(msg),
    humanize: () => ({
      title: 'Расчёт тёрна слишком тяжёлый',
      description: 'Комбинация числа карт тёрна и итераций слишком затратна для расчёта.',
      suggestion: 'Уменьшите число карт тёрна до 3 или снизьте итерации до 500.',
      icon: '⏱️',
      action: { label: 'Отключить тёрн', type: 'disable_turn' },
    }),
  },
  // Cannot enable turn with >3 board cards
  {
    test: (msg) => /cannot enable turn/i.test(msg),
    humanize: () => ({
      title: 'Тёрн недоступен для этого борда',
      description: 'Тёрн можно включить только с 3 картами (флоп). У вас уже 4+ карт.',
      suggestion: 'Уберите лишние карты борда или отключите тёрн.',
      icon: '🚫',
      action: { label: 'Отключить тёрн', type: 'disable_turn' },
    }),
  },
  // Phase 18B: Concurrent solve rejection (429)
  {
    test: (msg) => /Уже выполняется/i.test(msg) || /already running/i.test(msg),
    humanize: (msg) => ({
      title: 'Расчёт уже запущен',
      description: 'Сейчас выполняется другой расчёт. Дождитесь его завершения или отмените.',
      suggestion: 'Нажмите «Отменить» на текущем расчёте, чтобы запустить новый.',
      icon: '⏳',
    }),
  },
];

/**
 * Translates a raw English solver error into structured Russian recovery UX.
 * Falls back to a generic message if no pattern matches.
 */
export function humanizeError(rawMessage: string): HumanizedError {
  for (const pattern of ERROR_PATTERNS) {
    if (pattern.test(rawMessage)) {
      return pattern.humanize(rawMessage);
    }
  }

  // Fallback: wrap unknown error in Russian context
  return {
    title: 'Ошибка расчёта',
    description: rawMessage,
    suggestion: 'Попробуйте упростить настройки или выбрать другие параметры.',
    icon: '❌',
  };
}
