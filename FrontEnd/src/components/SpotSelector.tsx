import { useState, useMemo, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { cn } from '@/lib/utils';
import { Search, ChevronUp, ChevronDown, Replace } from 'lucide-react';
import type { Spot } from '@/types';
import { TooltipHint, HINTS } from '@/components/TooltipHint';
import { localizeSpotName, localizeFormat } from '@/lib/localizePoker';

const FORMAT_COLORS: Record<string, string> = {
    SRP: 'text-green-400',
    '3bet': 'text-orange-400',
    '4bet': 'text-red-400',
    squeeze: 'text-purple-400',
};

const FORMAT_ORDER = ['SRP', '3bet', '4bet', 'squeeze'];

function spotDisplayName(s: Spot): string {
    return localizeSpotName(s.name, s.format, s.positions, s.streets);
}

export function SpotSelector({
    selectedSpotId,
    onSelect,
    className,
}: {
    selectedSpotId: string;
    onSelect: (id: string) => void;
    className?: string;
}) {
    const [open, setOpen] = useState(false);
    const [search, setSearch] = useState('');
    const ref = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const { data: spots } = useQuery({
        queryKey: ['spots'],
        queryFn: api.getSpots,
    });

    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, []);

    useEffect(() => {
        if (open && inputRef.current) inputRef.current.focus();
    }, [open]);

    const currentSpot = spots?.find((s) => s.id === selectedSpotId);

    const filtered = useMemo(() => {
        const solved = (spots || []).filter((s) => s.solved);
        if (!search) return solved;
        const q = search.toLowerCase();
        return solved.filter(
            (s) =>
                s.name.toLowerCase().includes(q) ||
                s.format.toLowerCase().includes(q) ||
                s.positions.join(' ').toLowerCase().includes(q) ||
                spotDisplayName(s).toLowerCase().includes(q)
        );
    }, [spots, search]);

    const grouped = useMemo(() => {
        const groups: Record<string, Spot[]> = {};
        for (const s of filtered) {
            if (!groups[s.format]) groups[s.format] = [];
            groups[s.format].push(s);
        }
        return groups;
    }, [filtered]);

    if (!spots) return null;

    return (
        <div ref={ref} className={cn('relative', className)}>
            <button
                onClick={() => { setOpen(!open); setSearch(''); }}
                className={cn(
                    'w-full flex items-center gap-2 px-2.5 py-2 rounded-xl text-left transition-colors border',
                    open
                        ? 'border-primary bg-primary/5'
                        : 'border-border bg-secondary/50 hover:bg-secondary'
                )}
            >
                <Replace className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-foreground truncate">
                        {currentSpot ? spotDisplayName(currentSpot) : 'Выберите спот'}
                    </div>
                    {currentSpot && (
                        <div className="text-[10px] text-muted-foreground">
                            {currentSpot.name}
                        </div>
                    )}
                </div>
                {open ? (
                    <ChevronUp className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                ) : (
                    <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                )}
            </button>

            {open && (
                <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-card border border-border rounded-xl shadow-xl max-h-[400px] flex flex-col overflow-hidden min-w-[280px]">
                    <div className="p-2 border-b border-border">
                        <div className="relative">
                            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
                            <input
                                ref={inputRef}
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="Поиск..."
                                className="w-full bg-secondary border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:ring-1 focus:ring-ring"
                            />
                        </div>
                    </div>

                    <div className="overflow-auto flex-1 p-1.5">
                        {FORMAT_ORDER.map((fmt) => {
                            const items = grouped[fmt];
                            if (!items?.length) return null;
                            return (
                                <div key={fmt} className="mb-2">
                                    <div className={cn('text-[10px] font-bold uppercase tracking-wider px-2 py-1', FORMAT_COLORS[fmt] || 'text-muted-foreground')}>
                                        <TooltipHint content={HINTS[fmt as keyof typeof HINTS] || 'Формат игры'} className="border-b-0 group-hover:border-b">
                                            <span>
                                                {localizeFormat(fmt)}
                                            </span>
                                        </TooltipHint>
                                        <span className="text-muted-foreground font-normal ml-1">({items.length})</span>
                                    </div>
                                    {items.map((s) => (
                                        <button
                                            key={s.id}
                                            onClick={() => {
                                                onSelect(s.id);
                                                setOpen(false);
                                            }}
                                            className={cn(
                                                'w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition-colors',
                                                s.id === selectedSpotId
                                                    ? 'bg-primary/10 text-primary'
                                                    : 'text-foreground hover:bg-secondary'
                                            )}
                                        >
                                            <div className="truncate">{spotDisplayName(s)}</div>
                                            <div className="text-[9px] text-muted-foreground truncate mt-0.5">
                                                {s.name}
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            );
                        })}
                        {filtered.length === 0 && (
                            <div className="text-xs text-muted-foreground text-center py-4">
                                Споты не найдены
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
