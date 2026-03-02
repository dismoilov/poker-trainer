import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { formatDateTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import {
  Cpu,
  Check,
  Loader2,
  Clock,
  AlertCircle,
  RotateCw,
} from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';

const statusConfig = {
  pending: {
    label: 'В очереди',
    icon: Clock,
    className: 'text-muted-foreground',
  },
  running: {
    label: 'Выполняется',
    icon: Loader2,
    className: 'text-action-bet',
  },
  done: { label: 'Готово', icon: Check, className: 'text-action-call' },
  failed: {
    label: 'Ошибка',
    icon: AlertCircle,
    className: 'text-action-fold',
  },
};

const Jobs = () => {
  const { data: jobs, isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: api.getJobs,
    refetchInterval: 5000,
  });

  const handleRetry = (jobId: string) => {
    toast.info('Задача перезапущена (мок)');
  };

  return (
    <div className="p-6 lg:p-10 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Задачи
        </h1>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Cpu className="w-4 h-4" />
          {jobs?.length || 0} задач
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-card border border-border rounded-2xl p-5 h-28 animate-pulse"
            />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {jobs?.map((job) => {
            const status = statusConfig[job.status];
            const StatusIcon = status.icon;

            return (
              <div
                key={job.id}
                className="bg-card border border-border rounded-2xl p-5 space-y-3"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <StatusIcon
                        className={cn(
                          'w-4 h-4',
                          status.className,
                          job.status === 'running' && 'animate-spin'
                        )}
                      />
                      <span className="font-medium text-foreground">
                        {job.spotName || job.type}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {job.type === 'solve' ? 'Расчёт' : 'Импорт'} •{' '}
                      {formatDateTime(job.createdAt)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={cn('text-xs font-medium', status.className)}>
                      {status.label}
                    </span>
                    {job.status === 'failed' && (
                      <button
                        onClick={() => handleRetry(job.id)}
                        className="p-1.5 rounded-lg hover:bg-secondary transition-colors"
                        aria-label="Повторить"
                      >
                        <RotateCw className="w-3.5 h-3.5 text-muted-foreground" />
                      </button>
                    )}
                  </div>
                </div>

                {(job.status === 'running' || job.status === 'pending') && (
                  <Progress value={job.progress} className="h-1.5" />
                )}

                {job.log.length > 0 && (
                  <div className="text-xs text-muted-foreground font-mono bg-secondary/50 rounded-lg p-2.5 max-h-20 overflow-auto">
                    {job.log.map((line, i) => (
                      <div key={i}>{line}</div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {(!jobs || jobs.length === 0) && (
            <div className="text-center text-muted-foreground py-12">
              Нет задач. Перейдите в библиотеку, чтобы создать расчёт.
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Jobs;
