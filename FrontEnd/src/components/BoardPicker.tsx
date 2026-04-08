/**
 * BoardPicker.tsx — Visual card selector for the Solver board.
 *
 * Renders a 4×13 grid of playing cards grouped by suit.
 * - Click a card to add it to the board (up to maxCards)
 * - Click a selected card to remove it
 * - Prevents duplicates
 * - Shows selected board as inline card faces
 * - Supports external control via value/onChange
 */

import { cn } from '@/lib/utils';
import { X, Trash2 } from 'lucide-react';

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
const SUITS = [
  { char: 's', symbol: '♠', color: 'text-slate-300', bg: 'bg-slate-500/10', border: 'border-slate-500/30', selectedBg: 'bg-slate-500/30' },
  { char: 'h', symbol: '♥', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', selectedBg: 'bg-red-500/30' },
  { char: 'd', symbol: '♦', color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30', selectedBg: 'bg-blue-500/30' },
  { char: 'c', symbol: '♣', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', selectedBg: 'bg-emerald-500/30' },
];

interface BoardPickerProps {
  value: string[];           // currently selected cards, e.g. ['Ks', '7d', '2c']
  onChange: (cards: string[]) => void;
  maxCards?: number;          // default 5
  className?: string;
}

export function BoardPicker({ value, onChange, maxCards = 5, className }: BoardPickerProps) {
  const selectedSet = new Set(value);

  const toggleCard = (card: string) => {
    if (selectedSet.has(card)) {
      // Remove
      onChange(value.filter(c => c !== card));
    } else if (value.length < maxCards) {
      // Add
      onChange([...value, card]);
    }
  };

  const clearAll = () => onChange([]);

  const streetLabel = value.length < 3 ? 'Выберите 3 карты для флопа'
    : value.length === 3 ? 'Флоп выбран'
    : value.length === 4 ? 'Флоп + Тёрн'
    : 'Флоп + Тёрн + Ривер';

  return (
    <div className={cn('space-y-3', className)}>
      {/* Selected board display */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          {value.length === 0 ? (
            <span className="text-xs text-muted-foreground italic">Нажмите на карты ниже</span>
          ) : (
            value.map((card, i) => {
              const rank = card[0] === 'T' ? '10' : card[0];
              const suitObj = SUITS.find(s => s.char === card[1]);
              return (
                <button
                  key={card}
                  onClick={() => toggleCard(card)}
                  className={cn(
                    'w-10 h-14 rounded-lg border bg-white shadow-md flex flex-col items-center justify-center gap-0 relative group transition-all hover:scale-105',
                    i < 3 ? 'border-primary/30' : 'border-amber-500/30',
                  )}
                  title={`Убрать ${card}`}
                >
                  <span className="font-bold text-sm text-slate-900 leading-none">{rank}</span>
                  <span className={cn('text-base leading-none', suitObj?.color || 'text-white')}>{suitObj?.symbol || '?'}</span>
                  <div className="absolute inset-0 rounded-lg bg-red-500/0 group-hover:bg-red-500/15 transition-colors flex items-center justify-center">
                    <X className="w-3.5 h-3.5 text-red-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </button>
              );
            })
          )}
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <span className={cn(
            'text-[10px] px-2 py-0.5 rounded-full',
            value.length >= 3 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-muted text-muted-foreground',
          )}>{streetLabel}</span>
          {value.length > 0 && (
            <button onClick={clearAll} className="text-muted-foreground hover:text-red-400 transition-colors" title="Очистить борд">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Card grid */}
      <div className="space-y-1">
        {SUITS.map(suit => (
          <div key={suit.char} className="flex gap-0.5">
            {RANKS.map(rank => {
              const card = `${rank}${suit.char}`;
              const isSelected = selectedSet.has(card);
              const isFull = value.length >= maxCards && !isSelected;

              return (
                <button
                  key={card}
                  onClick={() => !isFull && toggleCard(card)}
                  disabled={isFull}
                  className={cn(
                    'w-[2.15rem] h-8 rounded text-[11px] font-medium transition-all border',
                    isSelected
                      ? `${suit.selectedBg} ${suit.border} ${suit.color} ring-1 ring-primary/40 scale-105 shadow-sm`
                      : isFull
                        ? 'bg-secondary/30 border-transparent text-muted-foreground/30 cursor-not-allowed'
                        : `${suit.bg} ${suit.border} ${suit.color} hover:brightness-125 hover:scale-105 cursor-pointer`,
                  )}
                >
                  {rank === 'T' ? '10' : rank}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
