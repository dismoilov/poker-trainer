import React, { memo, useCallback } from 'react';
import { RANKS, getHandLabel } from '@/lib/constants';
import { StrategyMatrix } from '@/types';
import { cn } from '@/lib/utils';

interface HandMatrixProps {
  strategy?: StrategyMatrix;
  highlightHand?: string;
  selectedAction?: string;
  onHandClick?: (hand: string) => void;
  compact?: boolean;
  className?: string;
}

const ACTION_COLORS: Record<string, string> = {
  fold: 'var(--action-fold)',
  check: 'var(--action-check)',
  call: 'var(--action-call)',
  bet33: 'var(--action-bet)',
  bet75: 'var(--action-raise)',
  raise: 'var(--action-raise)',
};

const Cell = memo(function Cell({
  hand,
  isHighlighted,
  bgColor,
  opacity,
  onClick,
  compact,
}: {
  hand: string;
  isHighlighted: boolean;
  bgColor?: string;
  opacity: number;
  onClick?: () => void;
  compact?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'text-[9px] sm:text-[10px] leading-none font-mono flex items-center justify-center transition-all',
        compact ? 'w-5 h-5 sm:w-6 sm:h-6' : 'w-6 h-6 sm:w-8 sm:h-8',
        isHighlighted && 'ring-2 ring-accent z-10 relative',
        !bgColor && 'bg-secondary/40 text-muted-foreground',
        bgColor && 'text-foreground'
      )}
      style={
        bgColor
          ? {
            backgroundColor: bgColor,
            opacity: Math.max(opacity, 0.2),
          }
          : undefined
      }
      aria-label={hand}
      tabIndex={-1}
    >
      {hand}
    </button>
  );
});

export const HandMatrix = memo(function HandMatrix({
  strategy,
  highlightHand,
  selectedAction,
  onHandClick,
  compact,
  className,
}: HandMatrixProps) {
  const getColor = useCallback(
    (hand: string) => {
      if (!strategy || !strategy[hand])
        return { bgColor: undefined, opacity: 0.3 };

      const freqs = strategy[hand];

      if (selectedAction && freqs[selectedAction] !== undefined) {
        const cssVar = ACTION_COLORS[selectedAction] || ACTION_COLORS['call'];
        return {
          bgColor: `hsl(${cssVar})`,
          opacity: freqs[selectedAction],
        };
      }

      let maxFreq = 0;
      let maxAction = '';
      for (const [action, freq] of Object.entries(freqs)) {
        if (freq > maxFreq) {
          maxFreq = freq;
          maxAction = action;
        }
      }
      const cssVar = ACTION_COLORS[maxAction] || ACTION_COLORS['call'];
      return {
        bgColor: `hsl(${cssVar})`,
        opacity: maxFreq,
      };
    },
    [strategy, selectedAction]
  );

  return (
    <div
      className={cn(
        'inline-grid grid-cols-13 gap-0 rounded-lg overflow-hidden border border-border',
        className
      )}
    >
      {RANKS.map((_, row) =>
        RANKS.map((_, col) => {
          const hand = getHandLabel(row, col);
          const { bgColor, opacity } = getColor(hand);
          return (
            <Cell
              key={hand}
              hand={hand}
              isHighlighted={hand === highlightHand}
              bgColor={bgColor}
              opacity={opacity}
              onClick={onHandClick ? () => onHandClick(hand) : undefined}
              compact={compact}
            />
          );
        })
      )}
    </div>
  );
});
