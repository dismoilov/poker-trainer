import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Target,
  GitBranch,
  BarChart3,
  BookOpen,
  Cpu,
  ArrowRight,
  TrendingDown,
  Percent,
  Zap,
  Gamepad2,
  Lightbulb,
} from 'lucide-react';
import { api } from '@/api/client';
import { useAppStore } from '@/store/useAppStore';
import { formatBB, formatPercent } from '@/lib/formatters';
import { TooltipHint, HINTS } from '@/components/TooltipHint';
import { getLearningTip, LEARNING_PATHWAY } from '@/lib/nextSteps';
import { cn } from '@/lib/utils';

const STEP_ICONS: Record<string, any> = {
  target: Target,
  explore: GitBranch,
  play: Gamepad2,
  solver: Cpu,
};

const STEP_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400', dot: 'bg-emerald-500' },
  blue: { bg: 'bg-blue-500/10', border: 'border-blue-500/20', text: 'text-blue-400', dot: 'bg-blue-500' },
  amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400', dot: 'bg-amber-500' },
  violet: { bg: 'bg-violet-500/10', border: 'border-violet-500/20', text: 'text-violet-400', dot: 'bg-violet-500' },
};

const Dashboard = () => {
  const navigate = useNavigate();
  const setSelectedSpot = useAppStore((s) => s.setSelectedSpot);

  const { data: summary } = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: api.getAnalyticsSummary,
  });

  const { data: spots } = useQuery({
    queryKey: ['spots'],
    queryFn: api.getSpots,
  });

  const tip = getLearningTip(summary || null);

  return (
    <div className="p-6 lg:p-10 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          PokerTrainer
        </h1>
        <p className="text-muted-foreground mt-1">
          Тренируй GTO-решения, изучай стратегии, отслеживай прогресс
        </p>
      </div>

      {/* ── Contextual Learning Tip ── */}
      <div className="bg-primary/5 border border-primary/15 rounded-2xl p-4 flex items-start gap-3">
        <span className="text-2xl">{tip.emoji}</span>
        <div>
          <div className="text-xs font-medium text-primary mb-0.5">Совет</div>
          <p className="text-sm text-foreground/80">{tip.text}</p>
        </div>
      </div>

      {/* ── Stats ── */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { id: 'sessions', label: 'Сессий', value: summary.totalSessions, icon: Zap },
            { id: 'questions', label: 'Вопросов', value: summary.totalQuestions.toLocaleString(), icon: Target },
            {
              id: 'evloss',
              label: (
                <TooltipHint content={HINTS.EVLoss}>
                  <span>Средний EV loss</span>
                </TooltipHint>
              ),
              value: formatBB(summary.avgEvLoss),
              icon: TrendingDown,
            },
            {
              id: 'accuracy',
              label: (
                <TooltipHint content={HINTS.Accuracy}>
                  <span>Точность</span>
                </TooltipHint>
              ),
              value: formatPercent(summary.accuracy),
              icon: Percent,
            },
          ].map((stat) => (
            <div key={stat.id} className="bg-card border border-border rounded-2xl p-4">
              <div className="flex items-center gap-2 text-muted-foreground mb-2">
                <stat.icon className="w-4 h-4" />
                <span className="text-xs">{stat.label}</span>
              </div>
              <div className="text-2xl font-bold text-foreground">{stat.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Learning Pathway ── */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-1 flex items-center gap-2">
          <Lightbulb className="w-5 h-5 text-amber-400" />
          Путь обучения
        </h2>
        <p className="text-xs text-muted-foreground mb-4">Рекомендуемый порядок изучения — от простого к сложному</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {LEARNING_PATHWAY.map((step) => {
            const Icon = STEP_ICONS[step.icon];
            const colors = STEP_COLORS[step.color];
            return (
              <button
                key={step.id}
                onClick={() => {
                  if (step.id === 'drill' && spots?.[0]) setSelectedSpot(spots[0].id);
                  navigate(step.route);
                }}
                className={cn(
                  'relative text-left p-4 rounded-2xl border transition-all group hover:scale-[1.02]',
                  colors.bg, colors.border,
                )}
              >
                {/* Step number */}
                <div className={cn(
                  'absolute -top-2 -left-1 w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white',
                  colors.dot,
                )}>
                  {step.step}
                </div>
                <div className="flex items-center gap-2 mb-2">
                  <Icon className={cn('w-5 h-5', colors.text)} />
                  <div className="font-semibold text-sm text-foreground">{step.title}</div>
                </div>
                <div className={cn('text-[10px] font-medium mb-1', colors.text)}>{step.subtitle}</div>
                <div className="text-xs text-muted-foreground">{step.description}</div>
                <ArrowRight className="absolute bottom-3 right-3 w-3.5 h-3.5 text-muted-foreground/30 group-hover:text-muted-foreground transition-colors" />
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Quick Actions (secondary) ── */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-3">Инструменты</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[
            { label: 'Аналитика', icon: BarChart3, desc: 'Прогресс и ошибки', onClick: () => navigate('/analytics') },
            { label: 'Библиотека', icon: BookOpen, desc: 'Каталог спотов', onClick: () => navigate('/library') },
            { label: 'Задачи', icon: Cpu, desc: 'Очередь расчётов', onClick: () => navigate('/jobs') },
          ].map((action) => (
            <button
              key={action.label}
              onClick={action.onClick}
              className="flex items-center gap-3 p-4 rounded-2xl border border-border bg-card hover:bg-secondary transition-all text-left group"
            >
              <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center shrink-0">
                <action.icon className="w-4 h-4 text-muted-foreground" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium text-foreground">{action.label}</div>
                <div className="text-[10px] text-muted-foreground">{action.desc}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ── Recent spots ── */}
      {spots && spots.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Доступные споты
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {spots.slice(0, 4).map((spot) => (
              <div
                key={spot.id}
                className="bg-card border border-border rounded-2xl p-4 flex items-center justify-between"
              >
                <div>
                  <div className="font-medium text-sm text-foreground">{spot.name}</div>
                  <div className="text-xs text-muted-foreground mt-1 flex gap-2">
                    <TooltipHint content={HINTS[spot.format as keyof typeof HINTS] || 'Формат игры'}>
                      <span className="bg-secondary px-2 py-0.5 rounded-md cursor-help">{spot.format}</span>
                    </TooltipHint>
                    <TooltipHint content={
                      <div className="space-y-1">
                        <div><strong className="text-primary">{spot.positions[0]}</strong> - Рейзер</div>
                        <div><strong className="text-primary">{spot.positions[1]}</strong> - Коллер</div>
                      </div>
                    }>
                      <span className="bg-secondary px-2 py-0.5 rounded-md cursor-help">
                        {spot.positions.join(' vs ')}
                      </span>
                    </TooltipHint>
                    {spot.solved && (
                      <span className="bg-primary/10 text-primary px-2 py-0.5 rounded-md">Решён</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => {
                    setSelectedSpot(spot.id);
                    navigate('/drill');
                  }}
                  className="text-xs text-primary hover:underline shrink-0"
                >
                  Тренировка →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
