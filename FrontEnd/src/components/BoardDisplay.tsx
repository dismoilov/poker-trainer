import { SUIT_SYMBOLS, SUIT_COLORS } from '@/lib/constants';
import { cn } from '@/lib/utils';

function CardDisplay({ card }: { card: string }) {
  const rank = card[0];
  const suit = card[1];
  const colorClass = SUIT_COLORS[suit] || 'text-foreground';

  return (
    <div
      className={cn(
        'inline-flex items-center justify-center w-10 h-14 rounded-lg bg-card border border-border font-bold text-base',
        colorClass
      )}
    >
      <span>
        {rank}
        {SUIT_SYMBOLS[suit]}
      </span>
    </div>
  );
}

export function BoardDisplay({
  board,
  label,
}: {
  board: string[];
  label?: string;
}) {
  return (
    <div>
      {label && (
        <div className="text-xs text-muted-foreground mb-1.5">{label}</div>
      )}
      <div className="flex gap-1.5">
        {board.map((card, i) => (
          <CardDisplay key={i} card={card} />
        ))}
      </div>
    </div>
  );
}

export function HandBadge({
  hand,
  cards,
}: {
  hand: string;
  cards?: [string, string];
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xl font-bold text-foreground">{hand}</span>
      {cards && (
        <div className="flex gap-1">
          {cards.map((c, i) => (
            <span
              key={i}
              className={cn(
                'text-sm font-mono',
                SUIT_COLORS[c[1]] || 'text-foreground'
              )}
            >
              {c[0]}
              {SUIT_SYMBOLS[c[1]]}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
