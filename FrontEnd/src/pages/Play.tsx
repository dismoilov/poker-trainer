import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useAuthStore } from '@/store/useAuthStore';
import type { SessionState, ActionEntry } from '@/types/play';
import { cn } from '@/lib/utils';
import { localizeAction, localizeActionLabel, localizeStreet, localizePlayer } from '@/lib/playLabels';
import PostHandReview from '@/components/PostHandReview';
import {
  Spade,
  RotateCcw,
  LogOut,
  ChevronRight,
  Trophy,
  Timer,
  TrendingUp,
  TrendingDown,
  Minus,
  Layers,
  BookOpen,
} from 'lucide-react';

/* ── Card rendering ── */
const SUIT_SYMBOLS: Record<string, { char: string; color: string }> = {
  s: { char: '♠', color: 'text-slate-200' },
  h: { char: '♥', color: 'text-red-400' },
  d: { char: '♦', color: 'text-blue-400' },
  c: { char: '♣', color: 'text-emerald-400' },
};

function CardFace({ card, faceDown = false, size = 'md' }: { card?: string; faceDown?: boolean; size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'w-10 h-14 text-sm',
    md: 'w-14 h-20 text-lg',
    lg: 'w-16 h-24 text-xl',
  };

  if (faceDown || !card) {
    return (
      <div className={cn(
        sizeClasses[size],
        'rounded-lg border-2 border-primary/30 bg-gradient-to-br from-primary/20 to-primary/5',
        'flex items-center justify-center shadow-lg shadow-black/20',
        'backdrop-blur-sm'
      )}>
        <div className="w-6 h-6 rounded-full border-2 border-primary/50 bg-primary/10" />
      </div>
    );
  }

  const rank = card[0];
  const suitChar = card[1];
  const suit = SUIT_SYMBOLS[suitChar] || { char: '?', color: 'text-white' };
  const displayRank = rank === 'T' ? '10' : rank;

  return (
    <div className={cn(
      sizeClasses[size],
      'rounded-lg border border-white/20 bg-white shadow-lg shadow-black/30',
      'flex flex-col items-center justify-center gap-0.5 relative overflow-hidden'
    )}>
      <span className={cn('font-bold leading-none text-slate-900', size === 'sm' ? 'text-sm' : 'text-lg')}>
        {displayRank}
      </span>
      <span className={cn(suit.color, 'leading-none', size === 'sm' ? 'text-base' : 'text-xl')}>
        {suit.char}
      </span>
    </div>
  );
}

/* ── Street progress bar ── */
const STREETS = ['flop', 'turn', 'river'];
const STREET_RU: Record<string, string> = { flop: 'Флоп', turn: 'Тёрн', river: 'Ривер' };

function StreetProgress({ current, isComplete }: { current: string; isComplete: boolean }) {
  const currentIdx = STREETS.indexOf(current.toLowerCase());

  return (
    <div className="flex items-center gap-1.5">
      {STREETS.map((s, i) => {
        const isActive = i <= currentIdx;
        const isCurrent = i === currentIdx && !isComplete;

        return (
          <div key={s} className="flex items-center gap-1.5">
            <div className={cn(
              'px-2.5 py-1 rounded-md text-[10px] font-semibold uppercase tracking-wider transition-all',
              isCurrent
                ? 'bg-primary/30 text-primary border border-primary/50 animate-pulse'
                : isActive
                  ? 'bg-primary/15 text-primary/80 border border-primary/20'
                  : 'bg-secondary/50 text-muted-foreground/50 border border-border/30',
            )}>
              {STREET_RU[s] || s}
            </div>
            {i < STREETS.length - 1 && (
              <div className={cn(
                'w-4 h-0.5 rounded-full',
                isActive ? 'bg-primary/40' : 'bg-border/30',
              )} />
            )}
          </div>
        );
      })}
      {isComplete && (
        <div className="px-2.5 py-1 rounded-md text-[10px] font-semibold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30 ml-1">
          Вскрытие
        </div>
      )}
    </div>
  );
}

/* ── Action button colors ── */
function getActionColor(type: string): string {
  switch (type) {
    case 'fold':
      return 'bg-red-600/80 hover:bg-red-500 border-red-500/50 text-white';
    case 'check':
      return 'bg-emerald-600/80 hover:bg-emerald-500 border-emerald-500/50 text-white';
    case 'call':
      return 'bg-blue-600/80 hover:bg-blue-500 border-blue-500/50 text-white';
    case 'bet':
    case 'raise':
      return 'bg-amber-600/80 hover:bg-amber-500 border-amber-500/50 text-white';
    case 'allin':
      return 'bg-purple-600/80 hover:bg-purple-500 border-purple-500/50 text-white font-bold';
    default:
      return 'bg-secondary hover:bg-secondary/80 border-border text-foreground';
  }
}

function getActionIcon(type: string): string {
  switch (type) {
    case 'fold': return '🚫';
    case 'check': return '✓';
    case 'call': return '📞';
    case 'bet': return '💰';
    case 'raise': return '⬆️';
    case 'allin': return '🔥';
    default: return '';
  }
}

/* ── P&L badge ── */
function PnlBadge({ heroStack, startingStack }: { heroStack: number; startingStack: number }) {
  const pnl = heroStack - startingStack;
  if (Math.abs(pnl) < 0.1) {
    return (
      <span className="inline-flex items-center gap-1 text-muted-foreground text-xs">
        <Minus className="w-3 h-3" /> Ровно
      </span>
    );
  }
  if (pnl > 0) {
    return (
      <span className="inline-flex items-center gap-1 text-emerald-400 text-xs">
        <TrendingUp className="w-3 h-3" /> +{pnl.toFixed(1)}ББ
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-red-400 text-xs">
      <TrendingDown className="w-3 h-3" /> {pnl.toFixed(1)}ББ
    </span>
  );
}

/* ── Main component ── */
const Play = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [startingStack, setStartingStack] = useState(100);
  const [solverCompare, setSolverCompare] = useState<any>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const prevHandCount = useRef(0);

  /* Create session */
  const createMutation = useMutation({
    mutationFn: () => api.createPlaySession(startingStack, 'IP'),
    onSuccess: (data) => {
      setSessionId(data.sessionId);
      queryClient.setQueryData(['playSession', data.sessionId], data);
    },
  });

  /* Get session state */
  const { data: state } = useQuery({
    queryKey: ['playSession', sessionId],
    queryFn: () => api.getPlaySession(sessionId!),
    enabled: !!sessionId,
    refetchInterval: false,
  });

  /* Get hand history */
  const { data: history } = useQuery({
    queryKey: ['playHistory', sessionId],
    queryFn: () => api.getPlayHistory(sessionId!),
    enabled: !!sessionId,
  });

  /* Take action */
  const actionMutation = useMutation({
    mutationFn: ({ actionType, amount }: { actionType: string; amount: number }) =>
      api.takePlayAction(sessionId!, actionType, amount),
    onSuccess: (data) => {
      queryClient.setQueryData(['playSession', sessionId], data);
      queryClient.invalidateQueries({ queryKey: ['playHistory', sessionId] });
    },
  });

  /* Next hand */
  const nextHandMutation = useMutation({
    mutationFn: () => api.nextPlayHand(sessionId!),
    onSuccess: (data) => {
      queryClient.setQueryData(['playSession', sessionId], data);
      queryClient.invalidateQueries({ queryKey: ['playHistory', sessionId] });
    },
  });

  const handleAction = useCallback((type: string, amount: number) => {
    actionMutation.mutate({ actionType: type, amount });
  }, [actionMutation]);

  /* ── Auto-compare on showdown ── */
  useEffect(() => {
    if (!state) return;
    const isHandDone = state.status === 'showdown' || state.status === 'hand_complete';
    const handNum = state.handsPlayed;
    // Only fire once per hand transition
    if (isHandDone && handNum !== prevHandCount.current && state.board.length >= 3) {
      prevHandCount.current = handNum;
      setSolverCompare(null);
      setCompareLoading(true);
      const flopActions = state.actionHistory.filter((a: ActionEntry) => a.street === 'flop' && a.player === 'IP');
      const lastUserAction = flopActions.length > 0 ? flopActions[flopActions.length - 1].type : '';
      fetch('/api/play/compare-to-solver', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${useAuthStore.getState().token || ''}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          board: state.board,
          hero_hand: state.heroHand,
          pot: state.pot,
          position: 'IP',
          user_action: lastUserAction,
        }),
      })
        .then(res => res.ok ? res.json() : null)
        .then(data => { if (data) setSolverCompare(data); })
        .catch(() => {})
        .finally(() => setCompareLoading(false));
    }
    // Reset compare on new hand
    if (!isHandDone && prevHandCount.current > 0 && handNum > prevHandCount.current) {
      setSolverCompare(null);
    }
  }, [state]);

  /* ── Lobby (no active session) ── */
  if (!sessionId || !state) {
    return (
      <div className="flex items-center justify-center h-full min-h-[80vh]">
        <div className="bg-card border border-border rounded-3xl p-8 max-w-md w-full space-y-6 shadow-2xl">
          <div className="text-center space-y-2">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-emerald-500 to-primary flex items-center justify-center mb-4">
              <Spade className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-foreground">Покерный стол</h1>
            <p className="text-sm text-muted-foreground">
              Хедз-ап постфлоп — Герой (IP) vs Оппонент (OOP)
            </p>
            <p className="text-[10px] text-muted-foreground/60 uppercase tracking-wider">
              Оппонент: эвристический ИИ, не GTO
            </p>
          </div>

          <div className="space-y-3">
            <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Начальный стек (ББ)
            </label>
            <div className="flex gap-2">
              {[50, 100, 150, 200].map((s) => (
                <button
                  key={s}
                  onClick={() => setStartingStack(s)}
                  className={cn(
                    'flex-1 py-2 rounded-xl text-sm font-medium border transition-all',
                    startingStack === s
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border bg-secondary text-muted-foreground hover:border-primary/50'
                  )}
                >
                  {s}ББ
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            className="w-full py-3 bg-gradient-to-r from-emerald-600 to-primary text-white font-semibold rounded-2xl hover:brightness-110 transition-all disabled:opacity-50 shadow-lg"
          >
            {createMutation.isPending ? 'Создаём...' : 'Сесть за стол'}
          </button>
        </div>
      </div>
    );
  }

  /* ── Active table ── */
  const isHandOver = state.status === 'showdown' || state.status === 'hand_complete';
  const isHeroTurn = state.currentPlayer === 'IP' && !isHandOver;
  const isFinished = (state.status as string) === 'finished';
  const showVillainCards = state.villainHand.length > 0;

  // Group actions by street for the history panel
  const actionsByStreet: Record<string, ActionEntry[]> = {};
  state.actionHistory.forEach((a: ActionEntry) => {
    const st = a.street || 'unknown';
    if (!actionsByStreet[st]) actionsByStreet[st] = [];
    actionsByStreet[st].push(a);
  });

  return (
    <div className="flex h-full gap-4 p-2">
      {/* Main table area */}
      <div className="flex-1 flex flex-col">
        {/* Street progress bar */}
        <div className="mb-2 flex items-center justify-between">
          <StreetProgress current={state.street} isComplete={isHandOver} />
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span>Раздача #{state.handsPlayed + (isHandOver ? 0 : 1)}</span>
            <PnlBadge heroStack={state.heroStack} startingStack={startingStack} />
          </div>
        </div>

        {/* Felt table */}
        <div className={cn(
          'flex-1 relative rounded-3xl bg-gradient-to-b from-[#1a5a3a] to-[#0d3d24] border-[6px] shadow-[inset_0_0_60px_rgba(0,0,0,0.4)] overflow-hidden min-h-[500px]',
          isHeroTurn
            ? 'border-emerald-700/80 shadow-[inset_0_0_60px_rgba(0,0,0,0.4),0_0_15px_rgba(16,185,129,0.2)]'
            : 'border-[#4a2810]',
        )}>

          {/* Villain seat (top) */}
          <div className="absolute top-4 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2">
            <div className={cn(
              'bg-black/40 backdrop-blur-sm rounded-2xl px-4 py-2 border transition-all',
              !isHandOver && state.currentPlayer === 'OOP'
                ? 'border-amber-500/50 shadow-[0_0_12px_rgba(245,158,11,0.15)]'
                : 'border-white/10',
            )}>
              <div className="text-xs text-white/60 text-center mb-1 flex items-center gap-1.5">
                Оппонент (OOP)
                {!isHandOver && state.currentPlayer === 'OOP' && (
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                )}
              </div>
              <div className="text-lg font-bold text-white text-center">
                {state.villainStack.toFixed(1)}ББ
              </div>
            </div>
            <div className="flex gap-1.5">
              {showVillainCards
                ? state.villainHand.map((c, i) => <CardFace key={i} card={c} />)
                : [0, 1].map((i) => <CardFace key={i} faceDown />)
              }
            </div>
          </div>

          {/* Board cards (center) */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-3">
            {/* Pot */}
            <div className="bg-black/50 backdrop-blur-sm rounded-full px-5 py-1.5 border border-amber-500/30">
              <span className="text-amber-400 font-bold text-base">Банк: {state.pot.toFixed(1)}ББ</span>
            </div>
            {/* Board */}
            <div className="flex gap-2">
              {state.board.map((card, i) => (
                <CardFace key={i} card={card} size="lg" />
              ))}
              {Array.from({ length: Math.max(0, 5 - state.board.length) }).map((_, i) => (
                <div key={`empty-${i}`} className="w-16 h-24 rounded-lg border-2 border-dashed border-white/10" />
              ))}
            </div>
          </div>

          {/* Hero seat (bottom) */}
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2">
            <div className="flex gap-1.5">
              {state.heroHand.map((c, i) => (
                <CardFace key={i} card={c} size="lg" />
              ))}
            </div>
            <div className={cn(
              'bg-black/40 backdrop-blur-sm rounded-2xl px-4 py-2 border transition-all',
              isHeroTurn
                ? 'border-emerald-500/50 shadow-[0_0_12px_rgba(16,185,129,0.15)]'
                : 'border-primary/30',
            )}>
              <div className="text-xs text-primary/80 text-center mb-1 flex items-center gap-1.5">
                Герой (IP)
                {isHeroTurn && (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                )}
              </div>
              <div className="text-lg font-bold text-white text-center">
                {state.heroStack.toFixed(1)}ББ
              </div>
            </div>
          </div>

          {/* Turn indicator */}
          {!isHandOver && (
            <div className="absolute top-1/2 right-4 -translate-y-1/2">
              <div className={cn(
                'px-3 py-2 rounded-xl text-xs font-medium border backdrop-blur-sm',
                isHeroTurn
                  ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                  : 'bg-amber-500/20 border-amber-500/40 text-amber-300'
              )}>
                <Timer className="w-3.5 h-3.5 inline mr-1" />
                {isHeroTurn ? 'Ваш ход' : 'Ожидание...'}
              </div>
            </div>
          )}

          {/* Result overlay */}
          {isHandOver && state.winningSummary && (
            <div className="absolute top-1/2 right-4 -translate-y-1/2 max-w-[200px]">
              <div className={cn(
                'px-4 py-3 rounded-2xl border backdrop-blur-sm text-center',
                state.lastResult === 'hero_win'
                  ? 'bg-emerald-500/20 border-emerald-500/40'
                  : state.lastResult === 'villain_win'
                    ? 'bg-red-500/20 border-red-500/40'
                    : 'bg-amber-500/20 border-amber-500/40',
              )}>
                <Trophy className={cn(
                  'w-5 h-5 mx-auto mb-1',
                  state.lastResult === 'hero_win' ? 'text-emerald-400' : 'text-amber-400'
                )} />
                <div className="text-xs text-white/90 leading-snug">
                  {state.winningSummary}
                </div>
              </div>
            </div>
          )}

          {/* Finished overlay */}
          {isFinished && (
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-10 rounded-3xl">
              <div className="text-center space-y-3 p-6">
                <Trophy className="w-10 h-10 mx-auto text-amber-400" />
                <h2 className="text-xl font-bold text-white">Сессия завершена</h2>
                <p className="text-sm text-white/70">
                  Итог: <PnlBadge heroStack={state.heroStack} startingStack={startingStack} />
                </p>
                <button
                  onClick={() => setSessionId(null)}
                  className="px-6 py-2 bg-primary text-white rounded-xl hover:brightness-110 transition-all"
                >
                  Новая сессия
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="mt-3 flex items-center gap-2 flex-wrap">
          {isHandOver && !isFinished ? (
            <button
              onClick={() => nextHandMutation.mutate()}
              disabled={nextHandMutation.isPending}
              className="flex-1 py-3 bg-gradient-to-r from-emerald-600 to-primary text-white font-semibold rounded-2xl hover:brightness-110 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <RotateCcw className="w-4 h-4" />
              {nextHandMutation.isPending ? 'Сдаём...' : 'Следующая раздача'}
            </button>
          ) : !isFinished ? (
            state.legalActions.map((action, i) => (
              <button
                key={i}
                onClick={() => handleAction(action.type, action.amount)}
                disabled={actionMutation.isPending || !isHeroTurn}
                className={cn(
                  'px-5 py-2.5 rounded-xl border text-sm font-medium transition-all',
                  isHeroTurn
                    ? getActionColor(action.type)
                    : 'bg-secondary/50 border-border/50 text-muted-foreground cursor-not-allowed',
                  'disabled:opacity-30',
                )}
              >
                <span className="mr-1">{getActionIcon(action.type)}</span>
                {localizeActionLabel(action.label)}
              </button>
            ))
          ) : null}

          <button
            onClick={() => setSessionId(null)}
            className="px-4 py-2.5 rounded-xl border border-border bg-secondary text-muted-foreground hover:text-foreground text-sm transition-colors"
            title="Покинуть стол"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Sidebar: Hand History */}
      <div className="w-72 shrink-0 bg-card border border-border rounded-2xl p-4 overflow-auto">
        <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
          <ChevronRight className="w-4 h-4 text-primary" />
          Информация
        </h3>
        <div className="space-y-2 text-xs text-muted-foreground mb-4">
          <div className="flex justify-between">
            <span>Раздач сыграно</span>
            <span className="text-foreground font-medium">{state.handsPlayed}</span>
          </div>
          <div className="flex justify-between">
            <span>Стек героя</span>
            <span className="text-foreground font-medium">{state.heroStack.toFixed(1)}ББ</span>
          </div>
          <div className="flex justify-between">
            <span>Стек оппонента</span>
            <span className="text-foreground font-medium">{state.villainStack.toFixed(1)}ББ</span>
          </div>
          <div className="flex justify-between">
            <span>Итог сессии</span>
            <PnlBadge heroStack={state.heroStack} startingStack={startingStack} />
          </div>
          <div className="pt-1 border-t border-border/50">
            <span className="text-[10px] text-muted-foreground/50 uppercase tracking-wider">
              Оппонент: Эвристический ИИ (не GTO)
            </span>
          </div>
        </div>

        {/* Current hand actions grouped by street */}
        <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
          <Layers className="w-4 h-4 text-primary" />
          История действий
        </h3>
        <div className="space-y-3 mb-4">
          {state.actionHistory.length === 0 && (
            <div className="text-xs text-muted-foreground italic">Пока нет действий</div>
          )}
          {Object.entries(actionsByStreet).map(([street, actions]) => (
            <div key={street}>
              <div className="text-[10px] text-muted-foreground/60 uppercase tracking-wider mb-1 font-medium">
                {localizeStreet(street)}
              </div>
              <div className="space-y-1 pl-2 border-l-2 border-border/30">
                {actions.map((a: ActionEntry, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className={cn(
                      'px-1.5 py-0.5 rounded text-[10px] font-medium min-w-[28px] text-center',
                      a.player === 'IP'
                        ? 'bg-primary/10 text-primary'
                        : 'bg-amber-500/10 text-amber-400'
                    )}>
                      {a.player === 'IP' ? 'Герой' : 'Опп.'}
                    </span>
                    <span className="text-foreground capitalize">{localizeAction(a.type)}</span>
                    {a.amount > 0 && (
                      <span className="text-muted-foreground">{a.amount.toFixed(1)}ББ</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Past hands */}
        {history && history.length > 0 && (
          <>
            <h3 className="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
              <ChevronRight className="w-4 h-4 text-primary" />
              Прошлые раздачи
            </h3>
            <div className="space-y-2">
              {history.slice(-8).reverse().map((h) => (
                <div key={h.id} className="bg-secondary/50 rounded-lg p-2.5 text-xs">
                  <div className="flex justify-between mb-1">
                    <span className="text-muted-foreground">Раздача #{h.handNumber}</span>
                    <span className={cn(
                      'font-medium',
                      h.result === 'hero_win' ? 'text-emerald-400' :
                      h.result === 'villain_win' ? 'text-red-400' : 'text-amber-400'
                    )}>
                      {h.result === 'hero_win' ? `+${h.heroWon.toFixed(1)}ББ` :
                       h.result === 'villain_win' ? `-${h.pot.toFixed(1)}ББ` :
                       'Ничья'}
                    </span>
                  </div>
                  <div className="text-muted-foreground flex gap-1">
                    <span className="text-muted-foreground/60">Борд:</span>
                    {h.board.map((c, ci) => (
                      <span key={ci} className="font-mono">{c}</span>
                    ))}
                  </div>
                  <div className="text-muted-foreground/60 mt-0.5">
                    Герой: {h.heroHand.join(' ')} vs Опп.: {h.villainHand.join(' ')}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
        {/* ── Post-Hand Review Panel ── */}
        {state && state.board.length >= 3 && (
          <div className="mt-3">
            {/* Manual trigger */}
            {!solverCompare && !compareLoading && (
              <button
                onClick={async () => {
                  setCompareLoading(true);
                  try {
                    const flopActions = state.actionHistory.filter((a: ActionEntry) => a.street === 'flop' && a.player === 'IP');
                    const lastUserAction = flopActions.length > 0 ? flopActions[flopActions.length - 1].type : '';
                    const res = await fetch('/api/play/compare-to-solver', {
                      method: 'POST',
                      headers: {
                        'Authorization': `Bearer ${useAuthStore.getState().token || ''}`,
                        'Content-Type': 'application/json',
                      },
                      body: JSON.stringify({
                        board: state.board,
                        hero_hand: state.heroHand,
                        pot: state.pot,
                        position: 'IP',
                        user_action: lastUserAction,
                      }),
                    });
                    if (res.ok) setSolverCompare(await res.json());
                  } catch {}
                  setCompareLoading(false);
                }}
                className="w-full py-2.5 bg-primary/15 hover:bg-primary/25 text-primary text-sm rounded-xl transition-colors font-medium"
              >
                📖 Разбор раздачи
              </button>
            )}

            {/* Loading */}
            {compareLoading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground py-3 justify-center">
                <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                Анализируем вашу игру...
              </div>
            )}

            {/* Full-width PostHandReview component */}
            {solverCompare && (
              <PostHandReview
                data={solverCompare}
                winningSummary={state.winningSummary}
                onClose={() => setSolverCompare(null)}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Play;
