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
import { cn } from '@/lib/utils';
import type { DrillQuestion, DrillFeedback, Action } from '@/types';
import {
  ChevronRight,
  Eye,
  EyeOff,
  BookOpen,
  SkipForward,
} from 'lucide-react';

type DrillPhase = 'loading' | 'question' | 'feedback';

const Drill = () => {
  const navigate = useNavigate();
  const selectedSpotId = useAppStore((s) => s.selectedSpotId);
  const setSelectedSpot = useAppStore((s) => s.setSelectedSpot);
  const showMatrix = useAppStore((s) => s.showMatrix);
  const toggleMatrix = useAppStore((s) => s.toggleMatrix);
  const incrementDrill = useAppStore((s) => s.incrementDrill);

  const [phase, setPhase] = useState<DrillPhase>('loading');
  const [question, setQuestion] = useState<DrillQuestion | null>(null);
  const [feedback, setFeedback] = useState<DrillFeedback | null>(null);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const [questionCount, setQuestionCount] = useState(0);
  const hasFetched = useRef(false);

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
              <span className="bg-secondary px-2.5 py-1 rounded-lg text-secondary-foreground">
                {question.position}
              </span>
              <span className="text-muted-foreground">
                Pot: {formatBB(question.potSize)}
              </span>
              <span className="text-muted-foreground">
                Stack: {question.stackSize}bb
              </span>
              <span className="text-muted-foreground capitalize">
                {question.street}
              </span>
            </div>
            <div className="text-xs text-muted-foreground">
              {question.lineDescription}
            </div>
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
                  {action.label}
                </button>
              ))}
            </div>
          </div>

          {/* Feedback */}
          {phase === 'feedback' && feedback && (
            <div className="bg-card border border-border rounded-2xl p-5 space-y-4 animate-slide-in-right">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-foreground">Результат</h3>
                <div className="flex items-center gap-3 text-sm">
                  <span
                    className={cn(
                      'font-medium',
                      feedback.evLoss <= 0.5
                        ? 'text-action-call'
                        : feedback.evLoss <= 2
                          ? 'text-action-check'
                          : 'text-action-fold'
                    )}
                  >
                    EV loss: {formatBB(feedback.evLoss)}
                  </span>
                  <span className="text-muted-foreground">
                    Точность: {formatPercent(feedback.accuracy)}
                  </span>
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
                        <span>{action?.label || actionId}</span>
                        <span className="font-mono font-medium">
                          {formatPercent(freq)}
                        </span>
                      </div>
                    );
                  })}
                </div>
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
                    {action.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Drill;
