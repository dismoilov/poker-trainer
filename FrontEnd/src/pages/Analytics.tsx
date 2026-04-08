import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { formatBB, formatPercent, formatDate } from '@/lib/formatters';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import {
  Target,
  TrendingDown,
  Percent,
  Zap,
  X,
  ChevronRight,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { SUIT_SYMBOLS, SUIT_COLORS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import type { GameDetail } from '@/types';
import { TooltipHint, HINTS } from '@/components/TooltipHint';

const ACTION_LABELS: Record<string, string> = {
  fold: 'Fold',
  check: 'Check',
  call: 'Call',
  bet33: 'Bet 33%',
  bet50: 'Bet 50%',
  bet75: 'Bet 75%',
  bet150: 'Bet 150%',
  raise: 'Raise',
};

const ACTION_COLORS: Record<string, string> = {
  fold: 'text-action-fold',
  check: 'text-action-check',
  call: 'text-action-call',
  bet33: 'text-action-bet',
  bet50: 'text-action-bet',
  bet75: 'text-action-raise',
  bet150: 'text-action-raise',
  raise: 'text-action-raise',
};

function CardDisplay({ card }: { card: string }) {
  const rank = card[0];
  const suit = card[1];
  return (
    <span
      className={cn(
        'inline-flex items-center font-mono text-sm',
        SUIT_COLORS[suit] || 'text-foreground'
      )}
    >
      {rank}
      {SUIT_SYMBOLS[suit] || suit}
    </span>
  );
}

function GameDetailModal({
  gameId,
  onClose,
}: {
  gameId: string;
  onClose: () => void;
}) {
  const { data: detail, isLoading } = useQuery({
    queryKey: ['game-detail', gameId],
    queryFn: () => api.getGameDetail(gameId),
    enabled: !!gameId,
  });

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
        <div className="bg-card border border-border rounded-2xl p-8 max-w-lg w-full mx-4">
          <div className="animate-pulse text-muted-foreground text-center">
            Загрузка...
          </div>
        </div>
      </div>
    );
  }

  if (!detail) return null;

  const isCorrect = detail.chosenAction === detail.correctAction;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-2xl p-6 max-w-2xl w-full mx-4 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-lg font-bold text-foreground">
              {detail.spotName}
            </h3>
            <div className="text-xs text-muted-foreground mt-0.5">
              {detail.lineDescription}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-secondary transition-colors"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        {/* Board + Hand */}
        <div className="flex items-center gap-6 mb-5">
          <div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
              Board
            </div>
            <div className="flex gap-1.5">
              {detail.board.map((card, i) => (
                <div
                  key={i}
                  className="bg-secondary rounded-lg px-2 py-1.5 text-sm font-mono font-bold"
                >
                  <CardDisplay card={card} />
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
              Hand
            </div>
            <div className="bg-secondary rounded-lg px-3 py-1.5 text-lg font-mono font-bold text-foreground">
              {detail.hand}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
              Position
            </div>
            <div className="bg-primary/10 text-primary rounded-lg px-3 py-1.5 text-sm font-bold">
              {detail.position}
            </div>
          </div>
        </div>

        {/* Result */}
        <div
          className={cn(
            'rounded-xl p-4 mb-5 border',
            isCorrect
              ? 'bg-green-500/5 border-green-500/20'
              : 'bg-red-500/5 border-red-500/20'
          )}
        >
          <div className="flex items-center gap-3">
            {isCorrect ? (
              <CheckCircle className="w-5 h-5 text-green-500" />
            ) : (
              <XCircle className="w-5 h-5 text-red-500" />
            )}
            <div className="flex-1">
              <div className="flex items-center gap-3 text-sm">
                <span className="text-muted-foreground">Ваш выбор:</span>
                <span
                  className={cn(
                    'font-bold',
                    ACTION_COLORS[detail.chosenAction]
                  )}
                >
                  {ACTION_LABELS[detail.chosenAction] || detail.chosenAction}
                </span>
                {!isCorrect && (
                  <>
                    <ChevronRight className="w-3 h-3 text-muted-foreground" />
                    <span className="text-muted-foreground">Верно:</span>
                    <span
                      className={cn(
                        'font-bold',
                        ACTION_COLORS[detail.correctAction]
                      )}
                    >
                      {ACTION_LABELS[detail.correctAction] ||
                        detail.correctAction}
                    </span>
                  </>
                )}
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-muted-foreground">EV Loss</div>
              <div className="font-mono font-bold text-foreground">
                {formatBB(detail.evLoss)}
              </div>
            </div>
          </div>
        </div>

        {/* Frequencies */}
        <div className="mb-5">
          <h4 className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
            GTO Частоты
          </h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(detail.frequencies)
              .sort(([, a], [, b]) => b - a)
              .map(([action, freq]) => (
                <div
                  key={action}
                  className={cn(
                    'bg-secondary/50 rounded-xl p-3 border transition-colors',
                    action === detail.correctAction
                      ? 'border-primary/30 bg-primary/5'
                      : 'border-border'
                  )}
                >
                  <div
                    className={cn(
                      'text-sm font-bold',
                      ACTION_COLORS[action] || 'text-foreground'
                    )}
                  >
                    {ACTION_LABELS[action] || action}
                  </div>
                  <div className="text-xl font-mono font-bold text-foreground mt-1">
                    {formatPercent(freq)}
                  </div>
                  {/* Bar */}
                  <div className="w-full h-1.5 bg-secondary rounded-full mt-2 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary/60"
                      style={{ width: `${freq * 100}%` }}
                    />
                  </div>
                </div>
              ))}
          </div>
        </div>

        {/* Explanations */}
        <div>
          <h4 className="text-xs text-muted-foreground uppercase tracking-wider mb-2">
            Анализ
          </h4>
          <div className="space-y-2">
            {detail.explanation.map((line, i) => (
              <div
                key={i}
                className="text-sm text-foreground/80 bg-secondary/30 rounded-xl p-3 border border-border/50"
              >
                <span className="text-primary font-bold mr-1.5">
                  {i + 1}.
                </span>
                {line}
              </div>
            ))}
          </div>
        </div>

        {/* Date */}
        <div className="text-xs text-muted-foreground mt-4 text-right">
          {formatDate(detail.date)}
        </div>
      </div>
    </div>
  );
}

const Analytics = () => {
  const [period, setPeriod] = useState('30');
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);

  const { data: summary } = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: api.getAnalyticsSummary,
  });

  const { data: history } = useQuery({
    queryKey: ['analytics-history'],
    queryFn: api.getAnalyticsHistory,
  });

  const { data: recent } = useQuery({
    queryKey: ['analytics-recent'],
    queryFn: api.getRecentQuestions,
  });

  const filteredHistory = history?.slice(-Number(period)) || [];

  const stats = summary
    ? [
      { label: 'Сессий', value: summary.totalSessions, icon: Zap },
      {
        label: 'Вопросов',
        value: summary.totalQuestions.toLocaleString(),
        icon: Target,
      },
      {
        label: (
          <TooltipHint content={HINTS.EVLoss}>
            <span>Средний EV loss</span>
          </TooltipHint>
        ),
        value: summary ? formatBB(summary.avgEvLoss) : '-',
        icon: TrendingDown,
      },
      {
        label: (
          <TooltipHint content={HINTS.Accuracy}>
            <span>Точность</span>
          </TooltipHint>
        ),
        value: summary ? formatPercent(summary.accuracy) : '-',
        icon: Percent,
      },
    ]
    : [];

  return (
    <div className="p-6 lg:p-10 max-w-5xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Аналитика
        </h1>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">7 дней</SelectItem>
            <SelectItem value="30">30 дней</SelectItem>
            <SelectItem value="90">90 дней</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-card border border-border rounded-2xl p-4"
          >
            <div className="flex items-center gap-2 text-muted-foreground mb-2">
              <stat.icon className="w-4 h-4" />
              <span className="text-xs">{stat.label}</span>
            </div>
            <div className="text-2xl font-bold text-foreground">
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* EV loss chart */}
      {filteredHistory.length > 0 && (
        <div className="bg-card border border-border rounded-2xl p-5">
          <h2 className="text-sm font-medium text-foreground mb-4">
            EV loss по дням
          </h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={filteredHistory}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="hsl(var(--border))"
                />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                  tickFormatter={(v) => {
                    const d = new Date(v);
                    return `${d.getDate()}/${d.getMonth() + 1}`;
                  }}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                  tickFormatter={(v) => `${v}bb`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '12px',
                    fontSize: '12px',
                  }}
                  formatter={(value: number) => [formatBB(value), 'EV loss']}
                />
                <Line
                  type="monotone"
                  dataKey="evLoss"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Game History Table */}
      <div className="bg-card border border-border rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-border">
          <h2 className="text-sm font-medium text-foreground">
            История игр
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Нажмите на строку для подробностей
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-muted-foreground text-xs">
                <th className="text-left p-3">Спот</th>
                <th className="text-left p-3">Рука</th>
                <th className="text-left p-3">Board</th>
                <th className="text-left p-3">Позиция</th>
                <th className="text-left p-3">Выбор</th>
                <th className="text-left p-3">Ответ (Вы / GTO)</th>
                <th className="text-right p-3">
                  <TooltipHint content={HINTS.EVLoss}>
                    <span className="cursor-help border-b border-dashed border-primary/50">EV loss</span>
                  </TooltipHint>
                </th>
                <th className="text-right p-3">
                  <TooltipHint content={HINTS.Accuracy}>
                    <span className="cursor-help border-b border-dashed border-primary/50">Точность</span>
                  </TooltipHint>
                </th>
                <th className="text-right p-3">Дата</th>
              </tr>
            </thead>
            <tbody>
              {recent?.slice(0, 30).map((q) => {
                const isCorrect = q.chosenAction === q.correctAction;
                return (
                  <tr
                    key={q.id}
                    onClick={() => setSelectedGameId(q.id)}
                    className={cn(
                      'border-b border-border last:border-0 cursor-pointer transition-colors',
                      'hover:bg-primary/5'
                    )}
                  >
                    <td className="p-3 text-foreground text-xs">
                      {q.spotName}
                    </td>
                    <td className="p-3 font-mono font-bold text-foreground">
                      {q.hand}
                    </td>
                    <td className="p-3">
                      <div className="flex gap-0.5">
                        {q.board.map((card, i) => (
                          <CardDisplay key={i} card={card} />
                        ))}
                      </div>
                    </td>
                    <td className="p-3 text-xs">
                      <span className="bg-secondary px-1.5 py-0.5 rounded">
                        {q.position}
                      </span>
                    </td>
                    <td
                      className={cn(
                        'p-3 font-medium text-xs',
                        ACTION_COLORS[q.chosenAction]
                      )}
                    >
                      {ACTION_LABELS[q.chosenAction] || q.chosenAction}
                    </td>
                    <td
                      className={cn(
                        'p-3 font-medium text-xs',
                        ACTION_COLORS[q.correctAction]
                      )}
                    >
                      {ACTION_LABELS[q.correctAction] || q.correctAction}
                    </td>
                    <td className="p-3 text-right font-mono text-xs">
                      <span
                        className={
                          isCorrect ? 'text-green-500' : 'text-action-fold'
                        }
                      >
                        {formatBB(q.evLoss)}
                      </span>
                    </td>
                    <td className="p-3 text-right font-mono text-xs">
                      {formatPercent(q.accuracy)}
                    </td>
                    <td className="p-3 text-right text-muted-foreground text-xs">
                      {formatDate(q.date)}
                    </td>
                  </tr>
                );
              })}
              {(!recent || recent.length === 0) && (
                <tr>
                  <td
                    colSpan={9}
                    className="p-8 text-center text-muted-foreground"
                  >
                    Пока нет сыгранных раздач. Начните тренировку в Drill!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Game Detail Modal */}
      {selectedGameId && (
        <GameDetailModal
          gameId={selectedGameId}
          onClose={() => setSelectedGameId(null)}
        />
      )}
    </div>
  );
};

export default Analytics;
