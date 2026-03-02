export const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'] as const;
export const SUITS = ['s', 'h', 'd', 'c'] as const;

export const SUIT_SYMBOLS: Record<string, string> = {
  s: '♠', h: '♥', d: '♦', c: '♣',
};

export const SUIT_COLORS: Record<string, string> = {
  s: 'text-foreground', h: 'text-suit-red', d: 'text-suit-red', c: 'text-foreground',
};

export const POSITIONS = ['UTG', 'UTG+1', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'] as const;

export function getHandLabel(row: number, col: number): string {
  if (row === col) return `${RANKS[row]}${RANKS[col]}`;
  if (row < col) return `${RANKS[row]}${RANKS[col]}s`;
  return `${RANKS[col]}${RANKS[row]}o`;
}

export const ALL_HANDS: string[] = [];
for (let i = 0; i < 13; i++) {
  for (let j = 0; j < 13; j++) {
    ALL_HANDS.push(getHandLabel(i, j));
  }
}

export const BOARDS: string[][] = [
  ['Ah', '7s', '2d'],
  ['Ks', 'Qh', '5c'],
  ['Jd', 'Ts', '3h'],
  ['9c', '8d', '7h'],
  ['As', 'Kd', 'Jc'],
  ['Qh', '9s', '4d'],
  ['Th', '6s', '2c'],
  ['Ah', 'Kh', '5h'],
];
