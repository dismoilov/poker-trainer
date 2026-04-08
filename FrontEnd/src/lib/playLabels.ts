/**
 * playLabels.ts — Russian localization for poker action labels, streets, and UI text.
 *
 * Used across the Play page to ensure zero English text in the game flow.
 */

/** Localize poker action type to Russian display label */
export function localizeAction(type: string): string {
  const map: Record<string, string> = {
    fold: 'Пас',
    check: 'Чек',
    call: 'Колл',
    bet: 'Ставка',
    raise: 'Рейз',
    allin: 'Олл-ин',
  };
  return map[type.toLowerCase()] || type;
}

/** Localize full action label like "Check", "Bet 6.5bb", "Call 4.3bb", "Raise 13.0bb", "Allin 100.0bb" */
export function localizeActionLabel(label: string): string {
  // Parse "ActionType Amount" pattern
  const match = label.match(/^(\w+)\s+([\d.]+)bb$/i);
  if (match) {
    const [, type, amount] = match;
    const ruType = localizeAction(type);
    return `${ruType} ${amount}ББ`;
  }
  // Plain action without amount
  return localizeAction(label);
}

/** Localize street name to Russian */
export function localizeStreet(street: string): string {
  const map: Record<string, string> = {
    flop: 'Флоп',
    turn: 'Тёрн',
    river: 'Ривер',
    preflop: 'Префлоп',
  };
  return map[street.toLowerCase()] || street;
}

/** Localize player name */
export function localizePlayer(player: string): string {
  if (player === 'IP') return 'Герой';
  if (player === 'OOP') return 'Оппонент';
  return player;
}

/** Localize hand result */
export function localizeResult(result: string): string {
  const map: Record<string, string> = {
    hero_win: 'Победа',
    villain_win: 'Проигрыш',
    split: 'Ничья',
    draw: 'Ничья',
  };
  return map[result] || result;
}
