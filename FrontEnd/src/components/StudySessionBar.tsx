/**
 * StudySessionBar — Phase 9C
 *
 * Horizontal stepper showing the user's position in a guided study session.
 * Renders only when a study session is active (studyContext.source is set).
 */
import { useNavigate } from 'react-router-dom';
import { useAppStore, STUDY_STEPS } from '@/store/useAppStore';
import { cn } from '@/lib/utils';
import { Check } from 'lucide-react';

interface StudySessionBarProps {
  className?: string;
}

export function StudySessionBar({ className }: StudySessionBarProps) {
  const navigate = useNavigate();
  const studyContext = useAppStore((s) => s.studyContext);
  const advanceStep = useAppStore((s) => s.advanceStep);
  const markStepComplete = useAppStore((s) => s.markStepComplete);

  // Don't render if no session
  if (!studyContext.source) return null;

  const { currentStep, completedSteps } = studyContext;

  const handleStepClick = (step: typeof STUDY_STEPS[number]) => {
    // Can navigate to completed or current step (not future)
    if (step.id > currentStep && !completedSteps.includes(step.id)) return;
    if (!step.route) return;

    // Mark current step as complete if advancing forward
    if (step.id > currentStep) {
      markStepComplete(currentStep);
    }
    advanceStep(step.id);
    navigate(step.route);
  };

  return (
    <div className={cn('bg-card/80 backdrop-blur-sm border border-border rounded-2xl p-3', className)}>
      {/* Session label */}
      <div className="flex items-center gap-2 mb-2.5">
        <span className="text-xs font-medium text-foreground">📚 Сессия обучения</span>
        {studyContext.spotLabel && (
          <span className="text-[10px] text-muted-foreground">• {studyContext.spotLabel}</span>
        )}
      </div>

      {/* Step indicators */}
      <div className="flex items-center gap-1">
        {STUDY_STEPS.map((step, idx) => {
          const isCompleted = completedSteps.includes(step.id);
          const isCurrent = currentStep === step.id;
          const isFuture = step.id > currentStep && !isCompleted;
          const isClickable = !isFuture && step.route;

          return (
            <div key={step.id} className="flex items-center flex-1">
              <button
                onClick={() => isClickable && handleStepClick(step)}
                disabled={!isClickable}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all w-full',
                  isCurrent && 'bg-primary/15 border border-primary/30 text-primary shadow-sm',
                  isCompleted && !isCurrent && 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/15 cursor-pointer',
                  isFuture && 'bg-secondary/30 text-muted-foreground/50 cursor-default',
                  !isCurrent && !isCompleted && !isFuture && 'bg-secondary/50 text-muted-foreground hover:bg-secondary cursor-pointer',
                )}
              >
                {isCompleted && !isCurrent ? (
                  <Check className="w-3 h-3 shrink-0" />
                ) : (
                  <span className="text-xs shrink-0">{step.emoji}</span>
                )}
                <span className="truncate">{step.label}</span>
              </button>
              {idx < STUDY_STEPS.length - 1 && (
                <div className={cn(
                  'w-3 h-px mx-0.5 shrink-0',
                  isCompleted ? 'bg-emerald-500/40' : 'bg-border',
                )} />
              )}
            </div>
          );
        })}
      </div>

      {/* Session stats */}
      {studyContext.drillsInSession > 0 && currentStep >= 2 && (
        <div className="flex items-center gap-3 mt-2 pl-1 text-[10px] text-muted-foreground">
          <span>🎯 {studyContext.drillsInSession} вопр.</span>
          <span>✓ {studyContext.drillsCorrectInSession} верно</span>
          {studyContext.drillsInSession > 0 && (
            <span>
              {Math.round((studyContext.drillsCorrectInSession / studyContext.drillsInSession) * 100)}% точность
            </span>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * StudyMilestone — shown after completing enough work in a step
 */
interface StudyMilestoneProps {
  title: string;
  description: string;
  actionLabel: string;
  actionEmoji: string;
  onAction: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
  variant?: 'emerald' | 'blue' | 'amber';
}

export function StudyMilestone({
  title,
  description,
  actionLabel,
  actionEmoji,
  onAction,
  secondaryLabel,
  onSecondary,
  variant = 'emerald',
}: StudyMilestoneProps) {
  const colors = {
    emerald: 'bg-emerald-500/10 border-emerald-500/20',
    blue: 'bg-blue-500/10 border-blue-500/20',
    amber: 'bg-amber-500/10 border-amber-500/20',
  };

  const btnColors = {
    emerald: 'bg-emerald-500 hover:bg-emerald-600 text-white',
    blue: 'bg-blue-500 hover:bg-blue-600 text-white',
    amber: 'bg-amber-500 hover:bg-amber-600 text-white',
  };

  return (
    <div className={cn('rounded-2xl border p-4 space-y-3 animate-fade-in', colors[variant])}>
      <div>
        <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
          🏆 {title}
        </h4>
        <p className="text-xs text-muted-foreground mt-1">{description}</p>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onAction}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors',
            btnColors[variant],
          )}
        >
          <span>{actionEmoji}</span>
          {actionLabel}
        </button>
        {secondaryLabel && onSecondary && (
          <button
            onClick={onSecondary}
            className="px-4 py-2 rounded-xl text-sm text-muted-foreground hover:text-foreground bg-secondary/50 hover:bg-secondary transition-colors"
          >
            {secondaryLabel}
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * StudyNextStep — compact next-step suggestion shown at the bottom of Explore
 */
interface StudyNextStepProps {
  label: string;
  emoji: string;
  hint: string;
  onClick: () => void;
}

export function StudyNextStep({ label, emoji, hint, onClick }: StudyNextStepProps) {
  return (
    <div className="bg-card border border-border rounded-2xl p-4 flex items-center justify-between">
      <div>
        <p className="text-xs text-muted-foreground">{hint}</p>
        <p className="text-sm font-medium text-foreground mt-0.5">{emoji} {label}</p>
      </div>
      <button
        onClick={onClick}
        className="px-4 py-2 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors"
      >
        Перейти →
      </button>
    </div>
  );
}
