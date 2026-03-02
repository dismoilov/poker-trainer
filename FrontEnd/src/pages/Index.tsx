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
} from 'lucide-react';
import { api } from '@/api/client';
import { useAppStore } from '@/store/useAppStore';
import { formatBB, formatPercent } from '@/lib/formatters';

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

  const quickActions = [
    {
      label: 'Начать Drill',
      icon: Target,
      desc: 'Тренировка GTO решений',
      onClick: () => {
        if (spots?.[0]) setSelectedSpot(spots[0].id);
        navigate('/drill');
      },
      primary: true,
    },
    {
      label: 'Explore',
      icon: GitBranch,
      desc: 'Изучение стратегий',
      onClick: () => navigate('/explore'),
    },
    {
      label: 'Аналитика',
      icon: BarChart3,
      desc: 'Прогресс и ошибки',
      onClick: () => navigate('/analytics'),
    },
    {
      label: 'Библиотека',
      icon: BookOpen,
      desc: 'Каталог спотов',
      onClick: () => navigate('/library'),
    },
    {
      label: 'Задачи',
      icon: Cpu,
      desc: 'Очередь расчётов',
      onClick: () => navigate('/jobs'),
    },
  ];

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

      {/* Stats */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            {
              label: 'Сессий',
              value: summary.totalSessions,
              icon: Zap,
            },
            {
              label: 'Вопросов',
              value: summary.totalQuestions.toLocaleString(),
              icon: Target,
            },
            {
              label: 'Средний EV loss',
              value: formatBB(summary.avgEvLoss),
              icon: TrendingDown,
            },
            {
              label: 'Точность',
              value: formatPercent(summary.accuracy),
              icon: Percent,
            },
          ].map((stat) => (
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
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {quickActions.map((action) => (
          <button
            key={action.label}
            onClick={action.onClick}
            className={`flex items-center gap-4 p-5 rounded-2xl border transition-all text-left group ${action.primary
                ? 'bg-primary/10 border-primary/20 hover:bg-primary/15'
                : 'bg-card border-border hover:bg-secondary'
              }`}
          >
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${action.primary
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-muted-foreground'
                }`}
            >
              <action.icon className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-medium text-foreground">{action.label}</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                {action.desc}
              </div>
            </div>
            <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
          </button>
        ))}
      </div>

      {/* Recent spots */}
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
                  <div className="font-medium text-sm text-foreground">
                    {spot.name}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1 flex gap-2">
                    <span className="bg-secondary px-2 py-0.5 rounded-md">
                      {spot.format}
                    </span>
                    <span className="bg-secondary px-2 py-0.5 rounded-md">
                      {spot.positions.join(' vs ')}
                    </span>
                    {spot.solved && (
                      <span className="bg-primary/10 text-primary px-2 py-0.5 rounded-md">
                        Solved
                      </span>
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
                  Drill →
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
