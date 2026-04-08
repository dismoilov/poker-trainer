/**
 * Range Utility Library — Phase 8D
 *
 * 13×13 grid model for visual range selection.
 * Converts between grid state and text notation (AA,KK,AKs).
 */

export const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'] as const;

export type RangeGrid = boolean[][];

/** Create empty 13×13 grid */
export function emptyGrid(): RangeGrid {
  return Array.from({ length: 13 }, () => Array(13).fill(false));
}

/** Get hand label for grid position */
export function handLabel(row: number, col: number): string {
  if (row === col) return `${RANKS[row]}${RANKS[col]}`;  // pair
  if (row < col) return `${RANKS[row]}${RANKS[col]}s`;   // suited (above diagonal)
  return `${RANKS[col]}${RANKS[row]}o`;                   // offsuit (below diagonal)
}

/** Get hand type for grid position */
export function handType(row: number, col: number): 'pair' | 'suited' | 'offsuit' {
  if (row === col) return 'pair';
  if (row < col) return 'suited';
  return 'offsuit';
}

/** Convert range text notation to grid */
export function rangeToGrid(rangeStr: string): RangeGrid {
  const grid = emptyGrid();
  if (!rangeStr.trim()) return grid;

  const hands = rangeStr.split(',').map(h => h.trim()).filter(Boolean);

  for (const hand of hands) {
    // Find matching grid cell(s)
    const cells = handToCells(hand);
    for (const [r, c] of cells) {
      grid[r][c] = true;
    }
  }
  return grid;
}

/** Convert grid to range text notation */
export function gridToRange(grid: RangeGrid): string {
  const hands: string[] = [];
  for (let r = 0; r < 13; r++) {
    for (let c = 0; c < 13; c++) {
      if (grid[r][c]) {
        hands.push(handLabel(r, c));
      }
    }
  }
  return hands.join(',');
}

/** Parse a single hand notation to grid cell(s) */
function handToCells(hand: string): [number, number][] {
  const h = hand.trim().toUpperCase();

  // Pair: AA, KK, etc.
  if (h.length === 2 && h[0] === h[1]) {
    const idx = rankIndex(h[0]);
    if (idx >= 0) return [[idx, idx]];
  }

  // Pair with range: AA-JJ or TT+
  if (h.includes('+') && h.length <= 3) {
    const base = h.replace('+', '');
    if (base.length === 2 && base[0] === base[1]) {
      const idx = rankIndex(base[0]);
      if (idx >= 0) {
        const cells: [number, number][] = [];
        for (let i = 0; i <= idx; i++) cells.push([i, i]);
        return cells;
      }
    }
  }

  // Suited hand: AKs
  if (h.length === 3 && h[2] === 'S') {
    const r1 = rankIndex(h[0]);
    const r2 = rankIndex(h[1]);
    if (r1 >= 0 && r2 >= 0 && r1 !== r2) {
      const row = Math.min(r1, r2);
      const col = Math.max(r1, r2);
      return [[row, col]];
    }
  }

  // Offsuit hand: AKo
  if (h.length === 3 && h[2] === 'O') {
    const r1 = rankIndex(h[0]);
    const r2 = rankIndex(h[1]);
    if (r1 >= 0 && r2 >= 0 && r1 !== r2) {
      const row = Math.max(r1, r2);
      const col = Math.min(r1, r2);
      return [[row, col]];
    }
  }

  // Two-card hand without s/o suffix: AK → try both suited+offsuit
  if (h.length === 2 && h[0] !== h[1]) {
    const r1 = rankIndex(h[0]);
    const r2 = rankIndex(h[1]);
    if (r1 >= 0 && r2 >= 0) {
      const sRow = Math.min(r1, r2), sCol = Math.max(r1, r2);
      const oRow = Math.max(r1, r2), oCol = Math.min(r1, r2);
      return [[sRow, sCol], [oRow, oCol]];
    }
  }

  return [];
}

function rankIndex(rank: string): number {
  return RANKS.indexOf(rank as typeof RANKS[number]);
}

/** Count selected hands in grid */
export function countSelected(grid: RangeGrid): number {
  let count = 0;
  for (let r = 0; r < 13; r++) {
    for (let c = 0; c < 13; c++) {
      if (grid[r][c]) count++;
    }
  }
  return count;
}

/** Count combos (pairs=6, suited=4, offsuit=12) */
export function countCombos(grid: RangeGrid): number {
  let combos = 0;
  for (let r = 0; r < 13; r++) {
    for (let c = 0; c < 13; c++) {
      if (!grid[r][c]) continue;
      if (r === c) combos += 6;
      else if (r < c) combos += 4;
      else combos += 12;
    }
  }
  return combos;
}

// ── Presets ──

export const PRESETS = {
  premium: {
    label: 'Премиум',
    desc: 'AA-QQ, AKs, AKo',
    hands: 'AA,KK,QQ,AKs,AKo',
  },
  tight: {
    label: 'Плотный',
    desc: 'AA-TT, AKs-ATs, KQs, AKo-AQo',
    hands: 'AA,KK,QQ,JJ,TT,AKs,AQs,AJs,ATs,KQs,AKo,AQo',
  },
  medium: {
    label: 'Средний',
    desc: 'AA-77, AKs-A8s, KQs-KTs, QJs, AKo-ATo, KQo',
    hands: 'AA,KK,QQ,JJ,TT,99,88,77,AKs,AQs,AJs,ATs,A9s,A8s,KQs,KJs,KTs,QJs,AKo,AQo,AJo,ATo,KQo',
  },
  wide: {
    label: 'Широкий',
    desc: 'AA-22, все одномастные A-x, бродвей',
    hands: 'AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,KQs,KJs,KTs,K9s,QJs,QTs,JTs,T9s,98s,87s,76s,65s,54s,AKo,AQo,AJo,ATo,A9o,KQo,KJo,QJo',
  },
} as const;

export type PresetKey = keyof typeof PRESETS;

// ── Quick Actions ──

export function selectAllPairs(): RangeGrid {
  const grid = emptyGrid();
  for (let i = 0; i < 13; i++) grid[i][i] = true;
  return grid;
}

export function selectAll(): RangeGrid {
  return Array.from({ length: 13 }, () => Array(13).fill(true));
}

export function selectBroadways(): RangeGrid {
  const grid = emptyGrid();
  // Broadway = T, J, Q, K, A (indices 0-4)
  for (let r = 0; r <= 4; r++) {
    for (let c = 0; c <= 4; c++) {
      grid[r][c] = true;
    }
  }
  return grid;
}

export function selectSuitedConnectors(): RangeGrid {
  const grid = emptyGrid();
  // Suited connectors: above diagonal, adjacent ranks
  for (let r = 0; r < 12; r++) {
    grid[r][r + 1] = true;
  }
  return grid;
}
