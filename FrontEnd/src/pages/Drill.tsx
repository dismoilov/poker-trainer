import { useState, useCallback, useEffect, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/api/client';
import { useAppStore } from '@/store/useAppStore';
import { useHotkey } from '@/lib/useHotkeys';
import { formatBB, formatPercent } from '@/lib/formatters';
import { BoardDisplay, HandBadge } from '@/components/BoardDisplay';
import { HandMatrix } from '@/components/HandMatrix';
import { SpotSelector } from '@/components/SpotSelector';
import { TooltipHint, HINTS } from '@/components/TooltipHint';
import { SolvePickerModal } from '@/components/SolvePickerModal';
import { StudySessionBar, StudyMilestone } from '@/components/StudySessionBar';
import { cn } from '@/lib/utils';
import { localizeAction, describeStrategy, localizeSpotName, localizeStreet } from '@/lib/localizePoker';
import { generateDrillCoaching } from '@/lib/coachingEngine';
import type { DrillQuestion, DrillFeedback, Action } from '@/types';
import {
  ChevronRight,
  Eye,
  EyeOff,
  BookOpen,
  SkipForward,
  Beaker,
  Shield,
  AlertTriangle,
  Sparkles,
  X,
} from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';

type DrillPhase = 'loading' | 'question' | 'feedback';

const Drill = () => {
  const navigate = useNavigate();
  const selectedSpotId = useAppStore((s) => s.selectedSpotId);
  const setSelectedSpot = useAppStore((s) => s.setSelectedSpot);
  const showMatrix = useAppStore((s) => s.showMatrix);
  const toggleMatrix = useAppStore((s) => s.toggleMatrix);
  const incrementDrill = useAppStore((s) => s.incrementDrill);
  const studyContext = useAppStore((s) => s.studyContext);
  const clearStudyContext = useAppStore((s) => s.clearStudyContext);
  const recordDrillResult = useAppStore((s) => s.recordDrillResult);
  const markStepComplete = useAppStore((s) => s.markStepComplete);
  const advanceStep = useAppStore((s) => s.advanceStep);
  const hasSession = !!studyContext.source;
  const [showMilestone, setShowMilestone] = useState(false);

  // Show milestone after ≥3 drills in a session
  useEffect(() => {
    if (hasSession && studyContext.drillsInSession >= 3 && !showMilestone) {
      setShowMilestone(true);
    }
  }, [studyContext.drillsInSession, hasSession, showMilestone]);

  const [phase, setPhase] = useState<DrillPhase>('loading');
  const [question, setQuestion] = useState<DrillQuestion | null>(null);
  const [feedback, setFeedback] = useState<DrillFeedback | null>(null);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [questionCount, setQuestionCount] = useState(0);
  const hasFetched = useRef(false);

  // Solver drill state
  const [solverDrillQ, setSolverDrillQ] = useState<any>(null);
  const [solverDrillFb, setSolverDrillFb] = useState<any>(null);
  const [solverDrillLoading, setSolverDrillLoading] = useState(false);
  const [solverDrillPickerOpen, setSolverDrillPickerOpen] = useState(false);
  const [solverDrillSolveId, setSolverDrillSolveId] = useState<string | null>(null);
  const [solverDrillCount, setSolverDrillCount] = useState(0);
  const [solverDrillCorrect, setSolverDrillCorrect] = useState(0);

  const spotId = selectedSpotId || 'srp-btn-bb-flop';

  const { data: spot } = useQuery({
    queryKey: ['spot', spotId],
    queryFn: () => api.getSpot(spotId),
  });

  const fetchQuestion = useCallback(async () => {
    setPhase('loading');
    setFeedback(null);
    setSelectedActionId(null);
    const q = await api.getDrillQuestion(spotId);
    setQuestion(q);
    setPhase('question');
    setQuestionCount((c) => c + 1);
  }, [spotId]);

  // Load first question on mount (not via useQuery to avoid caching issues)
  useEffect(() => {
    hasFetched.current = false;
  }, [spotId]);

  useEffect(() => {
    if (!hasFetched.current) {
      hasFetched.current = true;
      fetchQuestion();
    }
  }, [fetchQuestion]);

  const handleSpotChange = (newSpotId: string) => {
    setSelectedSpot(newSpotId);
    setQuestionCount(0);
    setFeedback(null);
    setSelectedActionId(null);
  };

  const answerMutation = useMutation({
    mutationFn: async (actionId: string) => {
      if (!question) throw new Error('No question');
      return api.submitDrillAnswer(question.nodeId, question.hand, actionId, question.questionId);
    },
    onSuccess: (fb) => {
      setFeedback(fb);
      setPhase('feedback');
      incrementDrill();
      // Track session drill result
      if (hasSession) {
        recordDrillResult(fb.accuracy >= 0.8);
      }
    },
  });

  const handleAction = useCallback(
    (action: Action) => {
      if (phase !== 'question' || answerMutation.isPending) return;
      setSelectedActionId(action.id);
      answerMutation.mutate(action.id);
    },
    [phase, answerMutation]
  );

  const handleNext = useCallback(() => {
    if (phase === 'feedback') {
      fetchQuestion();
    }
  }, [phase, fetchQuestion]);

  // Hotkeys
  const actions = question?.actions || [];
  useHotkey('1', () => actions[0] && handleAction(actions[0]), phase === 'question');
  useHotkey('2', () => actions[1] && handleAction(actions[1]), phase === 'question');
  useHotkey('3', () => actions[2] && handleAction(actions[2]), phase === 'question');
  useHotkey('4', () => actions[3] && handleAction(actions[3]), phase === 'question');
  useHotkey('Space', handleNext, phase === 'feedback');
  useHotkey('Enter', handleNext, phase === 'feedback');
  useHotkey('h', toggleMatrix);
  useHotkey('f', () => {
    if (phase === 'question') {
      const firstActionBtn = document.querySelector('[data-action-btn]') as HTMLButtonElement | null;
      firstActionBtn?.focus();
    }
  }, phase === 'question');

  const { data: strategy } = useQuery({
    queryKey: ['strategy', question?.nodeId],
    queryFn: () => api.getStrategy(question!.nodeId),
    enabled: !!question?.nodeId,
  });

  if (phase === 'loading') {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!question) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-muted-foreground">Выберите спот для тренировки</p>
        <button
          onClick={() => navigate('/library')}
          className="text-primary hover:underline flex items-center gap-1"
        >
          <BookOpen className="w-4 h-4" /> Библиотека спотов
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 lg:p-6 max-w-6xl mx-auto">
      {/* Purpose hint */}
      <div className="mb-4 p-3 bg-primary/5 border border-primary/10 rounded-xl flex items-center gap-2">
        <span className="text-lg">🎯</span>
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Тренировка GTO-решений.</span> Выберите ситуацию, посмотрите борд и вашу руку, затем выберите оптимальное действие.
        </p>
      </div>
      {/* Study session stepper */}
      {hasSession && (
        <StudySessionBar className="mb-4" />
      )}

      {/* Milestone: suggest next step after ≥3 drills */}
      {showMilestone && hasSession && (
        <StudyMilestone
          title="Отличная тренировка!"
          description={`Вы ответили на ${studyContext.drillsInSession} вопросов (${studyContext.drillsCorrectInSession} верно). Теперь изучите полную стратегию, чтобы лучше понять GTO-решения.`}
          actionLabel="Изучить стратегию"
          actionEmoji="📊"
          onAction={() => {
            markStepComplete(2);
            advanceStep(3);
            navigate('/explore');
          }}
          secondaryLabel="Продолжить тренировку"
          onSecondary={() => setShowMilestone(false)}
          variant="emerald"
        />
      )}

      {/* Auto-open solver drill prompt (when arriving from solver with solve_id) */}
      {hasSession && studyContext.solveId && !solverDrillSolveId && !showMilestone && (
        <div className="mb-4 p-3 bg-violet-500/10 border border-violet-500/20 rounded-xl">
          <button
            onClick={async () => {
              setSolverDrillSolveId(studyContext.solveId);
              setSolverDrillLoading(true);
              setSolverDrillFb(null);
              try {
                const token = useAuthStore.getState().token;
                const res = await fetch('/api/drill/solver-drill', {
                  method: 'POST',
                  headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                  body: JSON.stringify({ solve_id: studyContext.solveId }),
                });
                if (res.ok) setSolverDrillQ(await res.json());
              } catch {}
              setSolverDrillLoading(false);
            }}
            className="text-xs text-primary hover:text-primary/80 flex items-center gap-2"
          >
            <Beaker className="w-3.5 h-3.5" />
            Начать тренировку по расчёту солвера →
          </button>
        </div>
      )}
      {/* Top bar */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3 text-sm text-muted-foreground flex-1 min-w-0">
          <SpotSelector
            selectedSpotId={spotId}
            onSelect={handleSpotChange}
            className="w-64"
          />
          <ChevronRight className="w-4 h-4 shrink-0" />
          <span className="shrink-0">Вопрос #{questionCount}</span>
        </div>
        <button
          onClick={toggleMatrix}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors shrink-0 ml-3"
          aria-label="Переключить матрицу"
        >
          {showMatrix ? (
            <EyeOff className="w-4 h-4" />
          ) : (
            <Eye className="w-4 h-4" />
          )}
          <span className="hidden sm:inline">Матрица</span>
        </button>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left: question area */}
        <div className="flex-1 space-y-5">
          {/* Spot summary */}
          <div className="bg-card border border-border rounded-2xl p-4 space-y-3">
            <div className="flex items-center gap-3 flex-wrap text-sm">
              <TooltipHint content={HINTS[question.position as keyof typeof HINTS] || 'Позиция игрока за столом'}>
                <span className="bg-secondary px-2.5 py-1 rounded-lg text-secondary-foreground cursor-help">
                  {question.position}
                </span>
              </TooltipHint>
              <TooltipHint content="Размер банка в больших блайндах">
                <span className="text-muted-foreground cursor-help border-b border-dashed border-primary/50">
                  Банк: {formatBB(question.potSize)}
                </span>
              </TooltipHint>
              <TooltipHint content="Эффективный стек в больших блайндах (чаще всего 100bb)">
                <span className="text-muted-foreground cursor-help border-b border-dashed border-primary/50">
                  Стек: {question.stackSize}bb
                </span>
              </TooltipHint>
              <TooltipHint content="Текущая улица торговли">
                <span className="text-muted-foreground capitalize cursor-help border-b border-dashed border-primary/50">
                  {localizeStreet(question.street)}
                </span>
              </TooltipHint>
            </div>
            <TooltipHint content="Линия розыгрыша — последовательность действий, которая привела к текущей ситуации">
              <div className="text-xs text-muted-foreground cursor-help inline-block border-b border-dashed border-primary/50">
                {question.lineDescription}
              </div>
            </TooltipHint>
          </div>

          {/* Board */}
          <BoardDisplay board={question.board} label="Борд" />

          {/* Hand */}
          <div className="bg-card border border-border rounded-2xl p-4">
            <div className="text-xs text-muted-foreground mb-2">Ваша рука</div>
            <HandBadge hand={question.hand} cards={question.handCards} />
          </div>

          {/* Action buttons */}
          <div className="space-y-2">
            <div className="text-xs text-muted-foreground">
              Выберите действие:
            </div>
            <div className="flex flex-wrap gap-2">
              {question.actions.map((action, idx) => (
                <button
                  key={action.id}
                  onClick={() => handleAction(action)}
                  disabled={phase !== 'question' || answerMutation.isPending}
                  className={cn(
                    'px-5 py-2.5 rounded-xl text-sm font-medium transition-all border',
                    phase === 'question'
                      ? 'border-border hover:border-primary/40 bg-card hover:bg-secondary cursor-pointer focus:ring-2 focus:ring-primary focus:outline-none'
                      : 'border-border bg-card opacity-50 cursor-default',
                    selectedActionId === action.id &&
                    phase === 'feedback' &&
                    'ring-2 ring-accent'
                  )}
                  aria-label={`${action.label} (${idx + 1})`}
                  data-action-btn
                >
                  <span className="text-muted-foreground text-xs mr-1.5">
                    {idx + 1}
                  </span>
                  {localizeAction(action.label)}
                </button>
              ))}
            </div>
          </div>

          {/* Feedback */}
          {phase === 'feedback' && feedback && (
            <div className="bg-card border border-border rounded-2xl p-5 space-y-4 animate-slide-in-right">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-foreground">Результат</h3>
                <div className="flex items-center gap-4 text-sm mt-3 pt-3 border-t">
                  <TooltipHint content={HINTS.EVLoss}>
                    <span className="font-medium text-foreground cursor-help">
                      EV loss: {formatBB(feedback.evLoss)}
                    </span>
                  </TooltipHint>
                  <TooltipHint content={HINTS.Accuracy}>
                    <span className="font-medium text-foreground cursor-help">
                      Точность: {formatPercent(feedback.accuracy)}
                    </span>
                  </TooltipHint>
                </div>
              </div>

              {/* Phase 8B: Quality Label Badge */}
              <div className={cn(
                'rounded-lg p-3 border flex items-start gap-2',
                feedback.accuracy >= 1.0 ? 'bg-emerald-500/10 border-emerald-500/20' :
                feedback.accuracy >= 0.7 ? 'bg-green-500/10 border-green-500/20' :
                feedback.accuracy >= 0.3 ? 'bg-amber-500/10 border-amber-500/20' :
                'bg-red-500/10 border-red-500/20',
              )}>
                <span className="text-base shrink-0">
                  {feedback.accuracy >= 1.0 ? '🎯' :
                   feedback.accuracy >= 0.7 ? '✅' :
                   feedback.accuracy >= 0.3 ? '⚠️' : '❌'}
                </span>
                <div>
                  <span className={cn(
                    'font-semibold text-xs',
                    feedback.accuracy >= 1.0 ? 'text-emerald-400' :
                    feedback.accuracy >= 0.7 ? 'text-green-400' :
                    feedback.accuracy >= 0.3 ? 'text-amber-400' :
                    'text-red-400',
                  )}>
                    {feedback.accuracy >= 1.0 ? 'Отлично!' :
                     feedback.accuracy >= 0.7 ? 'Близко к солверу' :
                     feedback.accuracy >= 0.3 ? 'Приемлемое отклонение' :
                     'Значительное отклонение'}
                  </span>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {feedback.chosenAction === feedback.correctAction
                      ? `Вы выбрали лучшее действие: ${localizeAction(feedback.correctAction)}`
                      : `Лучшее действие: ${localizeAction(feedback.correctAction)}. Вы выбрали: ${localizeAction(feedback.chosenAction)}`}
                  </p>
                </div>
              </div>

              {/* Frequencies */}
              <div className="space-y-2">
                <div className="text-xs text-muted-foreground">
                  Правильные частоты:
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(feedback.frequencies).map(([actionId, freq]) => {
                    const action = question.actions.find(
                      (a) => a.id === actionId
                    );
                    return (
                      <div
                        key={actionId}
                        className={cn(
                          'px-3 py-1.5 rounded-lg text-sm flex items-center gap-2',
                          actionId === feedback.correctAction
                            ? 'bg-primary/10 text-primary border border-primary/20'
                            : 'bg-secondary text-secondary-foreground'
                        )}
                      >
                        <span>{localizeAction(action?.label || actionId)}</span>
                        <span className="font-mono font-medium">
                          {formatPercent(freq)}
                        </span>
                      </div>
                    );
                  })}
                </div>
                {/* Phase 8B: Recommendation summary */}
                {Object.keys(feedback.frequencies).length > 0 && (() => {
                  const actionLabels: Record<string, string> = {};
                  question.actions.forEach(a => { actionLabels[a.id] = a.label; });
                  const stratInfo = describeStrategy(feedback.frequencies, actionLabels);
                  return (
                    <div className="mt-2 p-2.5 bg-secondary/50 rounded-lg">
                      <div className="text-[10px] font-medium text-foreground mb-0.5">{stratInfo.typeLabel}</div>
                      <div className="text-[10px] text-muted-foreground">
                        💡 {stratInfo.summary}
                      </div>
                    </div>
                  );
                })()}
              </div>

              {/* Explanation */}
              <div className="space-y-1.5">
                <div className="text-xs text-muted-foreground">Объяснение:</div>
                <ul className="space-y-1">
                  {feedback.explanation.map((point, i) => (
                    <li
                      key={i}
                      className="text-sm text-muted-foreground flex items-start gap-2"
                    >
                      <span className="text-primary mt-0.5">•</span>
                      {point}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Data source indicator */}
              <div className="text-[9px] text-muted-foreground/50 italic">
                📊 Эвристика GTO • на основе предрассчитанных таблиц
              </div>

              {/* Coaching Feedback */}
              {feedback && question && (() => {
                const drillCoaching = generateDrillCoaching(
                  feedback.chosenAction,
                  feedback.correctAction,
                  feedback.frequencies,
                  feedback.accuracy,
                );
                return (
                  <div className={cn(
                    'rounded-xl p-3 border space-y-2',
                    drillCoaching.severityColor === 'emerald' ? 'bg-emerald-500/5 border-emerald-500/15'
                    : drillCoaching.severityColor === 'green' ? 'bg-green-500/5 border-green-500/15'
                    : drillCoaching.severityColor === 'amber' ? 'bg-amber-500/5 border-amber-500/15'
                    : 'bg-red-500/5 border-red-500/15',
                  )}>
                    <div className="flex items-center gap-2">
                      <span className="text-sm">{drillCoaching.severityEmoji}</span>
                      <span className={cn(
                        'text-xs font-semibold',
                        drillCoaching.severityColor === 'emerald' ? 'text-emerald-400'
                        : drillCoaching.severityColor === 'green' ? 'text-green-400'
                        : drillCoaching.severityColor === 'amber' ? 'text-amber-400'
                        : 'text-red-400',
                      )}>{drillCoaching.severityLabel}</span>
                    </div>
                    <p className="text-[11px] text-foreground leading-relaxed">
                      {drillCoaching.learningInsight}
                    </p>
                    {drillCoaching.mixedStrategyNote && (
                      <p className="text-[10px] text-muted-foreground italic">
                        🔀 {drillCoaching.mixedStrategyNote}
                      </p>
                    )}
                    <p className="text-[10px] text-muted-foreground">
                      👉 {drillCoaching.practiceAdvice}
                    </p>
                  </div>
                );
              })()}

              {/* Next button */}
              <button
                onClick={handleNext}
                className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                <SkipForward className="w-4 h-4" />
                Следующий
                <kbd className="ml-2 px-1.5 py-0.5 bg-primary-foreground/10 rounded text-xs">
                  Space
                </kbd>
              </button>
            </div>
          )}
        </div>

        {/* Right: matrix */}
        {showMatrix && (
          <div className="shrink-0 animate-fade-in">
            <div className="text-xs text-muted-foreground mb-2">
              Матрица рук
            </div>
            <HandMatrix
              strategy={strategy}
              highlightHand={question.hand}
              selectedAction={selectedActionId || undefined}
              compact
            />
            {/* Legend */}
            {strategy && (
              <div className="mt-3 flex flex-wrap gap-2">
                {question.actions.map((action) => (
                  <button
                    key={action.id}
                    onClick={() =>
                      setSelectedActionId(
                        selectedActionId === action.id ? null : action.id
                      )
                    }
                    className={cn(
                      'text-[10px] px-2 py-1 rounded-md border transition-colors',
                      selectedActionId === action.id
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:text-foreground'
                    )}
                  >
                    {localizeAction(action.label)}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Solver Drill Section */}
      <div className="mt-8 bg-card border border-border rounded-2xl p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Beaker className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">Тренировка по солверу</h3>
          <span className="text-[9px] bg-amber-500/15 border border-amber-500/30 text-amber-400 px-1.5 py-0.5 rounded">БЕТА</span>
          {solverDrillCount > 0 && (
            <span className="text-[10px] text-muted-foreground ml-auto">
              {solverDrillCount} вопр. • {solverDrillCorrect}/{solverDrillCount} верно
            </span>
          )}
        </div>
        <div className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 flex items-center gap-2">
          <AlertTriangle className="w-3 h-3 shrink-0" />
          Реальные данные CFR+, ограничены флоп-задачами хедз-ап с фиксированными ставками.
        </div>

        {!solverDrillQ && !solverDrillLoading && (
          <div className="flex gap-2">
            <button
              onClick={() => setSolverDrillPickerOpen(true)}
              className="flex-1 py-2.5 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg text-sm transition-colors flex items-center justify-center gap-2"
            >
              <Beaker className="w-4 h-4" />
              {solverDrillSolveId ? 'Сменить расчёт' : 'Выбрать расчёт для тренировки'}
            </button>
            {solverDrillSolveId && (
              <button
                onClick={async () => {
                  setSolverDrillLoading(true);
                  setSolverDrillFb(null);
                  try {
                    const token = useAuthStore.getState().token;
                    const res = await fetch('/api/drill/solver-drill', {
                      method: 'POST',
                      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                      body: JSON.stringify({ solve_id: solverDrillSolveId }),
                    });
                    if (res.ok) setSolverDrillQ(await res.json());
                  } catch {}
                  setSolverDrillLoading(false);
                }}
                className="px-4 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                Начать тренировку
              </button>
            )}
          </div>
        )}

        {solverDrillLoading && (
          <div className="flex items-center gap-2 py-3">
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span className="text-xs text-muted-foreground">Загрузка солвер-дрила...</span>
          </div>
        )}

        {solverDrillQ && !solverDrillFb && (
          <div className="space-y-3">
            {/* Context bar */}
            <div className="flex items-center gap-2 flex-wrap text-[10px]">
              <span className="font-mono bg-secondary px-2 py-1 rounded">
                Борд: {solverDrillQ.board?.join(' ')}
              </span>
              <span className="bg-secondary px-2 py-1 rounded">
                IP: {solverDrillQ.ip_range}
              </span>
              <span className="bg-secondary px-2 py-1 rounded">
                OOP: {solverDrillQ.oop_range}
              </span>
              {solverDrillQ.pot > 0 && (
                <span className="bg-secondary px-2 py-1 rounded">
                  Банк: {solverDrillQ.pot}bb
                </span>
              )}
              <span className="bg-secondary px-2 py-1 rounded">
                {solverDrillQ.node_label}
              </span>
              {solverDrillQ.trust_grade && (
                <span className="bg-amber-500/15 text-amber-400 px-1.5 py-0.5 rounded border border-amber-500/30">
                  <Shield className="w-3 h-3 inline mr-0.5" />{solverDrillQ.trust_grade.replace(/_/g, ' ')}
                </span>
              )}
              {solverDrillQ.street_depth && (
                <span className={`px-1.5 py-0.5 rounded border font-medium ${
                  solverDrillQ.street_depth === 'flop_plus_turn'
                    ? 'bg-cyan-500/15 border-cyan-500/30 text-cyan-400'
                    : 'bg-slate-500/15 border-slate-500/30 text-slate-400'
                }`}>
                  {solverDrillQ.street_depth === 'flop_plus_turn' ? 'Флоп+тёрн' : 'Только флоп'}
                </span>
              )}
            </div>

            {/* Combo display */}
            <div className="bg-secondary/50 rounded-xl p-4 flex items-center gap-4">
              <div>
                <div className="text-[10px] text-muted-foreground mb-1">Ваша комбинация</div>
                <span className="font-mono text-xl font-bold text-foreground">{solverDrillQ.combo}</span>
              </div>
              <div className="text-[10px] text-muted-foreground">
                <p>{solverDrillQ.data_depth}</p>
                {solverDrillQ.iterations && <p>{solverDrillQ.iterations} итераций</p>}
              </div>
            </div>

            <p className="text-sm text-foreground font-medium">Какое действие вы выберете?</p>
            <div className="flex gap-2 flex-wrap">
              {solverDrillQ.actions?.map((a: string, i: number) => (
                <button
                  key={a}
                  onClick={async () => {
                    try {
                      const token = useAuthStore.getState().token;
                      const res = await fetch('/api/drill/solver-drill/answer', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          solve_id: solverDrillQ.solve_id,
                          node_id: solverDrillQ.node_id,
                          combo: solverDrillQ.combo,
                          chosen_action: a,
                        }),
                      });
                      if (res.ok) {
                        const fb = await res.json();
                        setSolverDrillFb(fb);
                        setSolverDrillCount(c => c + 1);
                        if (fb.correct) setSolverDrillCorrect(c => c + 1);
                      }
                    } catch {}
                  }}
                  className="px-5 py-2.5 bg-secondary hover:bg-secondary/80 text-foreground rounded-xl text-sm font-medium transition-all border border-border hover:border-primary/40 focus:ring-2 focus:ring-primary focus:outline-none"
                >
                  <span className="text-muted-foreground text-xs mr-1.5">{i + 1}</span>
                  {a}
                </button>
              ))}
            </div>
          </div>
        )}

        {solverDrillFb && (
          <div className="space-y-3">
            {/* Verdict */}
            <div className={cn(
              'p-4 rounded-xl border text-sm',
              solverDrillFb.correct
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : solverDrillFb.acceptable
                  ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                  : 'bg-red-500/10 border-red-500/30 text-red-400'
            )}>
              <div className="font-semibold mb-1">
                {solverDrillFb.correct ? '✓ Верно!' : solverDrillFb.acceptable ? '~ Допустимо' : '✗ Неверно'}
              </div>
              <div className="text-foreground/80">{solverDrillFb.feedback}</div>
            </div>

            {/* Accuracy meter */}
            {solverDrillFb.accuracy_pct != null && (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground w-20">Точность</span>
                <div className="flex-1 h-2 bg-secondary/50 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full',
                      solverDrillFb.accuracy_pct >= 80 ? 'bg-emerald-400' :
                      solverDrillFb.accuracy_pct >= 40 ? 'bg-amber-400' : 'bg-red-400'
                    )}
                    style={{ width: `${Math.min(solverDrillFb.accuracy_pct, 100)}%` }}
                  />
                </div>
                <span className="font-mono w-12 text-right">{solverDrillFb.accuracy_pct.toFixed(0)}%</span>
              </div>
            )}

            {/* Frequency bars */}
            <div className="space-y-1">
              <div className="text-[10px] text-muted-foreground">Частоты солвера:</div>
              {Object.entries(solverDrillFb.solver_frequencies || {})
                .sort(([,a]: any, [,b]: any) => b - a)
                .map(([a, f]: [string, any]) => (
                  <div key={a} className="flex items-center gap-2 text-xs">
                    <span className={cn(
                      'w-20 font-medium',
                      a === solverDrillFb.best_action ? 'text-primary' : 'text-foreground'
                    )}>{a}</span>
                    <div className="flex-1 h-2 bg-secondary/50 rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-primary/60" style={{ width: `${f * 100}%` }} />
                    </div>
                    <span className="font-mono w-10 text-right text-muted-foreground">{(f * 100).toFixed(0)}%</span>
                  </div>
                ))}
            </div>

            {/* Explanation */}
            {solverDrillFb.explanation && solverDrillFb.explanation.length > 0 && (
              <div className="space-y-1">
                <div className="text-[10px] text-muted-foreground">Пояснение:</div>
                {solverDrillFb.explanation.map((line: string, i: number) => (
                  <p key={i} className="text-xs text-foreground/80">{line}</p>
                ))}
              </div>
            )}

            {/* Data depth note */}
            {solverDrillFb.data_depth_note && (
              <div className="text-[9px] text-muted-foreground/50 italic">{solverDrillFb.data_depth_note}</div>
            )}

            <button
              onClick={() => {
                setSolverDrillQ(null);
                setSolverDrillFb(null);
                // Auto-fetch next question
                if (solverDrillSolveId) {
                  setSolverDrillLoading(true);
                  const token = useAuthStore.getState().token;
                  fetch('/api/drill/solver-drill', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ solve_id: solverDrillSolveId }),
                  })
                    .then(r => r.ok ? r.json() : null)
                    .then(q => { if (q) setSolverDrillQ(q); })
                    .finally(() => setSolverDrillLoading(false));
                }
              }}
              className="flex items-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Следующий вопрос →
            </button>
          </div>
        )}
      </div>

      {/* Solver Drill Picker Modal */}
      <SolvePickerModal
        open={solverDrillPickerOpen}
        onClose={() => setSolverDrillPickerOpen(false)}
        title="Выберите расчёт для тренировки"
        onSelect={(solveId) => {
          setSolverDrillPickerOpen(false);
          setSolverDrillSolveId(solveId);
          setSolverDrillCount(0);
          setSolverDrillCorrect(0);
        }}
      />
    </div>
  );
};

export default Drill;
