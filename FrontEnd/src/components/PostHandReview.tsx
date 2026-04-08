/**
 * PostHandReview — Phase 8J: full-width coach-led post-hand review card.
 *
 * Appears after showdown to teach the user about their decision.
 * Structure: hand context → verdict → user action vs solver → severity meter →
 * coaching → strategy bars → takeaway → next steps → trust footer.
 */
import { cn } from '@/lib/utils';
import { localizeAction } from '@/lib/playLabels';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/useAppStore';
import { BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';

// ── Types ──
interface SolverCompareData {
  match_quality: string;
  hand_narrative?: string;
  user_action_ru?: string;
  deviation?: {
    label: string;
    severity_level: number;
    description: string;
    coaching_message: string;
    accuracy_pct: number;
    user_freq: number;
    best_action: string;
    best_freq: number;
    is_mixed_spot: boolean;
  };
  quality_label?: { emoji: string; text: string; color: string };
  hero_combo_data?: Record<string, number>;
  hero_combo_key?: string;
  root_summary?: Record<string, number>;
  recommendation_summary?: string;
  learning_takeaway?: string;
  next_steps?: Array<{ id: string; label: string; icon: string; route: string }>;
  explanation?: string;
  board_for_solver?: string;
  // Trust metadata
  street_depth?: string;
  trust_grade?: string;
  exploitability_mbb?: number;
  iterations?: number;
  honest_note?: string;
}

interface PostHandReviewProps {
  data: SolverCompareData;
  winningSummary?: string;
  onClose: () => void;
}

// ── Severity Meter ──
const SEVERITY_DOTS = [
  { level: 1, label: 'Идеально', color: 'bg-emerald-400' },
  { level: 2, label: 'Хорошо', color: 'bg-green-400' },
  { level: 3, label: 'Небольшое', color: 'bg-amber-400' },
  { level: 4, label: 'Заметное', color: 'bg-orange-400' },
  { level: 5, label: 'Ошибка', color: 'bg-red-400' },
];

function SeverityMeter({ level }: { level: number }) {
  return (
    <div className="flex items-center gap-1.5">
      {SEVERITY_DOTS.map((dot) => (
        <div key={dot.level} className="flex flex-col items-center gap-0.5">
          <div
            className={cn(
              'w-3.5 h-3.5 rounded-full transition-all border-2',
              dot.level <= level
                ? `${dot.color} border-transparent shadow-sm`
                : 'bg-secondary/30 border-border/40',
              dot.level === level && 'ring-2 ring-offset-1 ring-offset-card ring-current scale-110',
            )}
          />
          {dot.level === level && (
            <span className="text-[8px] text-muted-foreground whitespace-nowrap">{dot.label}</span>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Verdict color helper ──
function verdictColor(color: string) {
  const map: Record<string, { bg: string; border: string; text: string }> = {
    emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/25', text: 'text-emerald-400' },
    green: { bg: 'bg-green-500/10', border: 'border-green-500/25', text: 'text-green-400' },
    amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/25', text: 'text-amber-400' },
    orange: { bg: 'bg-orange-500/10', border: 'border-orange-500/25', text: 'text-orange-400' },
    red: { bg: 'bg-red-500/10', border: 'border-red-500/25', text: 'text-red-400' },
  };
  return map[color] || map.amber;
}

// ── Main component ──
export default function PostHandReview({ data, winningSummary, onClose }: PostHandReviewProps) {
  const navigate = useNavigate();
  const setStudyContext = useAppStore((s) => s.setStudyContext);
  const [showDetails, setShowDetails] = useState(false);

  // ── Unavailable state ──
  if (data.match_quality === 'unsupported') {
    return (
      <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-primary" />
          Разбор раздачи
        </h3>
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4">
          <p className="font-medium text-sm text-amber-400 mb-1">📋 Расчёт для этого борда пока не готов</p>
          <p className="text-xs text-amber-400/70">
            {data.explanation || 'Чтобы сравнить свою игру с солвером, нужен расчёт именно для этого флопа.'}
          </p>
        </div>
        <div className="bg-secondary/30 rounded-lg p-3">
          <p className="text-xs text-muted-foreground">
            💡 Подсказка: откройте Солвер, запустите расчёт для этого борда, и разбор станет доступен.
          </p>
        </div>
        {data.board_for_solver && (
          <button
            onClick={() => navigate(`/solver?board=${encodeURIComponent(data.board_for_solver!!)}`)}
            className="w-full py-2.5 bg-primary/15 hover:bg-primary/25 text-primary text-sm rounded-xl transition-colors flex items-center justify-center gap-1.5 font-medium"
          >
            🧮 Открыть солвер с этим бордом →
          </button>
        )}
        <button onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
          Скрыть
        </button>
      </div>
    );
  }

  const deviation = data.deviation;
  const qualityLabel = data.quality_label;
  const colors = verdictColor(qualityLabel?.color || 'amber');
  const severityLevel = deviation?.severity_level || 0;

  // Strategy data: prefer hero combo, fallback to root summary
  const strategyData = data.hero_combo_data || data.root_summary;

  return (
    <div className="bg-card border border-border rounded-2xl overflow-hidden">

      {/* ── 1. Header + Hand Context ── */}
      <div className="bg-primary/5 border-b border-border px-5 py-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-primary" />
            Разбор раздачи
          </h3>
          <button onClick={onClose} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
            Скрыть
          </button>
        </div>
        {data.hand_narrative && (
          <p className="text-xs text-muted-foreground mt-1 font-mono">
            {data.hand_narrative}
          </p>
        )}
      </div>

      <div className="p-5 space-y-4">

        {/* ── 2. Main Verdict + Severity Meter ── */}
        {deviation && qualityLabel && (
          <div className={cn('rounded-xl p-4 border', colors.bg, colors.border)}>
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-center gap-2.5">
                <span className="text-2xl">{qualityLabel.emoji}</span>
                <div>
                  <div className={cn('font-semibold text-sm', colors.text)}>
                    {qualityLabel.text}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    Точность: {deviation.accuracy_pct?.toFixed(0)}%
                  </div>
                </div>
              </div>
              <SeverityMeter level={severityLevel} />
            </div>

            {/* User action vs solver preference — inline row */}
            {data.user_action_ru && (
              <div className="flex items-center gap-3 text-xs mb-3 bg-black/10 rounded-lg p-2.5">
                <div className="flex-1">
                  <span className="text-muted-foreground">Вы сделали:</span>{' '}
                  <span className="font-semibold text-foreground capitalize">{data.user_action_ru}</span>
                  {deviation.user_freq > 0 && (
                    <span className="text-muted-foreground ml-1">({(deviation.user_freq * 100).toFixed(0)}%)</span>
                  )}
                </div>
                <div className="w-px h-4 bg-border" />
                <div className="flex-1">
                  <span className="text-muted-foreground">Солвер:</span>{' '}
                  <span className="font-semibold text-foreground capitalize">{localizeAction(deviation.best_action)}</span>
                  <span className="text-muted-foreground ml-1">({(deviation.best_freq * 100).toFixed(0)}%)</span>
                </div>
              </div>
            )}

            {/* Coaching message */}
            {deviation.coaching_message && (
              <p className="text-xs text-foreground/80 leading-relaxed">
                {deviation.coaching_message}
              </p>
            )}

            {/* Mixed spot badge */}
            {deviation.is_mixed_spot && (
              <div className="mt-2 inline-flex items-center gap-1 text-[10px] text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full">
                🔀 Смешанный спот — оба варианта допустимы
              </div>
            )}
          </div>
        )}

        {/* ── 3. Strategy Bars ── */}
        {strategyData && Object.keys(strategyData).length > 0 && (
          <div className="space-y-1.5">
            <div className="text-xs text-muted-foreground font-medium flex items-center gap-1.5">
              {data.hero_combo_data ? '🃏 Стратегия для вашей руки' : '📊 Средняя стратегия солвера'}
              {data.hero_combo_key && (
                <span className="font-mono text-[10px] text-muted-foreground/70">({data.hero_combo_key})</span>
              )}
            </div>
            {Object.entries(strategyData)
              .sort(([, a], [, b]) => (b as number) - (a as number))
              .map(([action, freq]) => {
                const f = freq as number;
                const isUserAction = data.user_action_ru && localizeAction(action).toLowerCase() === data.user_action_ru.toLowerCase();
                return (
                  <div key={action} className="flex items-center gap-2 text-xs">
                    <span className={cn('w-16', isUserAction ? 'text-primary font-semibold' : 'text-foreground')}>
                      {localizeAction(action)}
                      {isUserAction && ' ←'}
                    </span>
                    <div className="flex-1 h-2 bg-secondary/40 rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          isUserAction ? 'bg-primary' : 'bg-primary/50',
                        )}
                        style={{ width: `${f * 100}%` }}
                      />
                    </div>
                    <span className="font-mono text-muted-foreground w-10 text-right">{(f * 100).toFixed(0)}%</span>
                  </div>
                );
              })}
          </div>
        )}

        {/* ── 4. Learning Takeaway ── */}
        {data.learning_takeaway && (
          <div className="bg-emerald-500/8 border border-emerald-500/20 rounded-xl p-3.5">
            <p className="text-xs text-emerald-400 font-medium leading-relaxed">
              📝 Запомнить: {data.learning_takeaway}
            </p>
          </div>
        )}

        {/* ── 5. Next Steps ── */}
        {data.next_steps && data.next_steps.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-xs text-muted-foreground font-medium mb-1">🚀 Что дальше</div>
            <div className="grid grid-cols-1 gap-1.5">
              {data.next_steps.map((step) => (
                <button
                  key={step.id}
                  onClick={() => {
                    // Set study context with session state for Drill/Explore pages
                    if (step.id === 'drill' || step.id === 'explore') {
                      const stepAny = step as any;
                      setStudyContext({
                        source: 'play',
                        solveId: stepAny.solve_id || null,
                        board: stepAny.board || [],
                        boardDisplay: stepAny.board_display || '',
                        spotLabel: stepAny.spot_label || '',
                        coachingNote: data.learning_takeaway || data.recommendation_summary || '',
                        mainIdea: data.recommendation_summary,
                        keyTakeaway: data.learning_takeaway,
                        // Session progression
                        currentStep: step.id === 'drill' ? 2 : 3,
                        completedSteps: [1], // Review is complete
                        drillsInSession: 0,
                        drillsCorrectInSession: 0,
                      });
                    }
                    navigate(step.route);
                  }}
                  className="flex items-center gap-2 px-3 py-2 bg-secondary/40 hover:bg-secondary/70 rounded-lg text-xs text-foreground transition-colors text-left"
                >
                  <span className="text-base">{step.icon}</span>
                  <span>{step.label}</span>
                  <span className="ml-auto text-muted-foreground text-[10px]">→</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── 6. Trust / Scope Badges (collapsible) ── */}
        <div>
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="flex items-center gap-1 text-[10px] text-muted-foreground/60 hover:text-muted-foreground transition-colors"
          >
            {showDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {showDetails ? 'Скрыть подробности' : 'Подробности расчёта'}
          </button>

          {showDetails && (
            <div className="mt-2 space-y-2">
              <div className="flex items-center gap-1.5 flex-wrap">
                {data.street_depth && (
                  <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded ${
                    data.street_depth === 'flop_plus_turn'
                      ? 'bg-cyan-500/15 text-cyan-400'
                      : 'bg-slate-500/15 text-slate-400'
                  }`}>
                    {data.street_depth === 'flop_plus_turn' ? 'Флоп+тёрн' : 'Только флоп'}
                  </span>
                )}
                {data.trust_grade && (
                  <span className="bg-amber-500/15 text-amber-400 px-1.5 py-0.5 rounded text-[9px]">
                    {data.trust_grade.replace(/_/g, ' ')}
                  </span>
                )}
                {data.exploitability_mbb != null && (
                  <span className="bg-blue-500/15 text-blue-400 px-1.5 py-0.5 rounded text-[9px]">
                    {data.exploitability_mbb.toFixed(1)} mbb
                  </span>
                )}
                {data.iterations && (
                  <span className="text-[9px] text-muted-foreground">{data.iterations} итер.</span>
                )}
              </div>
              {data.honest_note && (
                <p className="text-muted-foreground/50 text-[9px] leading-relaxed">{data.honest_note}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
