import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  Cpu,
  PlayCircle,
  StopCircle,
  Loader2,
  CheckCircle2,
  XCircle,
  ChevronRight,
  ChevronDown,
  AlertTriangle,
  BarChart3,
  Info,
  History,
  Shield,
  ShieldCheck,
  ShieldAlert,
  Clock,
  GitCompare,
  RefreshCw,
  Settings2,
  Sparkles,
  Lightbulb,
  Target,
  Eye,
  EyeOff,
} from 'lucide-react';

import { useAuthStore } from '@/store/useAuthStore';
import { useAppStore } from '@/store/useAppStore';
import { RangeBuilder } from '@/components/RangeBuilder';
import { BoardPicker } from '@/components/BoardPicker';
import { generateSimpleReport } from '@/lib/simpleReport';
import { generateCoachingSummary } from '@/lib/coachingEngine';
import { humanizeError } from '@/lib/humanizeError';
import { POST_SOLVE_ACTIONS } from '@/lib/nextSteps';

const API_BASE = '/api/solver';
const EXPLORE_API = '/api/explore';

async function apiFetch(path: string, base = API_BASE, options?: RequestInit) {
  const token = useAuthStore.getState().token;
  const res = await fetch(`${base}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ── Types ──

interface SolveProgress {
  job_id: string;
  status: string;
  iteration: number;
  total_iterations: number;
  convergence_metric: number;
  elapsed_seconds: number;
  estimated_remaining_seconds: number;
  progress_pct: number;
  error: string;
  data_source: string;
}

interface SolveResult {
  job_id: string;
  status: string;
  iterations: number;
  convergence_metric: number;
  elapsed_seconds: number;
  tree_nodes: number;
  ip_combos: number;
  oop_combos: number;
  matchups: number;
  converged: boolean;
  node_count: number;
  metadata: Record<string, any>;
  validation: Record<string, any>;
  exploitability: Record<string, any>;
  trust_grade: Record<string, any>;
  error: string;
  full_strategies_available: boolean;
}

interface NodeStrategy {
  job_id: string;
  node_id: string;
  combos: Record<string, Record<string, number>>;
  action_summary: Record<string, number>;
  message: string;
}

interface HistoryItem {
  id: string;
  status: string;
  created_at: string;
  board: string[];
  ip_range: string;
  oop_range: string;
  iterations: number;
  convergence_metric: number;
  elapsed_seconds: number;
  converged: boolean;
  validation_passed: boolean;
  full_strategies_available: boolean;
  exploitability_mbb: number | null;
  trust_grade: string;
  street_depth?: string;
  stop_reason?: string;       // Phase 16B: why the solve stopped
  quality_class?: string;     // Phase 16B: quality classification
}

interface BenchmarkResult {
  total: number;
  passed: number;
  warned: number;
  failed: number;
  errored: number;
  overall_status: string;
  benchmarks: Array<{
    name: string;
    description: string;
    status: string;
    exploitability_mbb: number;
    checks: Array<{ name: string; passed: boolean; expected: string; actual: string }>;
  }>;
  elapsed_seconds: number;
}

interface CompareData {
  solver_strategy: { label: string; summary: Record<string, number>; trust_level: string };
  heuristic_strategy: { label: string; summary: Record<string, number>; trust_level: string };
  comparison_note: string;
}

type SolverTab = 'setup' | 'result' | 'history';

// ── Main Component ──

const Solver = () => {
  // ── Input state ──
  const [boardCards, setBoardCards] = useState<string[]>(['Ks', '7d', '2c']);
  const [ipRange, setIpRange] = useState('AA,KK,AKs');
  const [oopRange, setOopRange] = useState('QQ,JJ,AQs');
  const [pot, setPot] = useState(6.5);
  const [stack, setStack] = useState(97);
  const [betSizes, setBetSizes] = useState('0.33,0.5,0.67,1.0');
  const [raiseSizes, setRaiseSizes] = useState('2.5');
  const [maxIter, setMaxIter] = useState(200);
  const [maxRaises, setMaxRaises] = useState(2);
  const [includeTurn, setIncludeTurn] = useState(false);
  const [maxTurnCards, setMaxTurnCards] = useState(5);
  const [includeRiver, setIncludeRiver] = useState(false);
  const [maxRiverCards, setMaxRiverCards] = useState(2);
  const [boardTextFallback, setBoardTextFallback] = useState(false);
  const [boardTextValue, setBoardTextValue] = useState('');
  // Phase 10C: Preset state
  const [selectedPreset, setSelectedPreset] = useState<'fast' | 'standard' | 'deep'>('standard');

  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const setSolverContext = useAppStore((s) => s.setSolverContext);

  // ── Read ?board= URL param on mount ──
  useEffect(() => {
    const boardParam = searchParams.get('board');
    if (boardParam) {
      const cards = boardParam.trim().split(/\s+/).filter(c => /^[2-9TJQKA][shdc]$/i.test(c));
      if (cards.length >= 3) {
        setBoardCards(cards.slice(0, 5));
      }
      // Clean URL
      setSearchParams({}, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── UX state ──
  const [activeTab, setActiveTab] = useState<SolverTab>('setup');
  const [advancedMode, setAdvancedMode] = useState(false);
  const [showTechDetails, setShowTechDetails] = useState(false);

  // ── Job state ──
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<SolveProgress | null>(null);
  const [result, setResult] = useState<SolveResult | null>(null);
  const [nodeStrategy, setNodeStrategy] = useState<NodeStrategy | null>(null);
  const [inspectNodeId, setInspectNodeId] = useState('node_0');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [cancelRequested, setCancelRequested] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const sseRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── History state ──
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [historyDetail, setHistoryDetail] = useState<Record<string, any> | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // ── Compare state ──
  const [compareData, setCompareData] = useState<CompareData | null>(null);
  const [isComparing, setIsComparing] = useState(false);

  // ── Benchmark state ──
  const [benchmarkData, setBenchmarkData] = useState<BenchmarkResult | null>(null);
  const [isRunningBenchmarks, setIsRunningBenchmarks] = useState(false);

  // ── Load history ──
  const loadHistory = useCallback(async () => {
    try {
      const data = await apiFetch('/history');
      setHistory(data);
    } catch {
      // silently fail
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // ── Phase 15C: SSE-based progress with polling fallback ──
  useEffect(() => {
    const terminals = ['done', 'failed', 'timeout', 'cancelled'];
    if (!jobId || (progress && terminals.includes(progress.status))) {
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }

    const handleTerminal = async (jobIdVal: string) => {
      try {
        const r = await apiFetch(`/result/${jobIdVal}`);
        setResult(r);
        setActiveTab('result');
        try {
          const ns = await apiFetch(`/node/${jobIdVal}/node_0`);
          setNodeStrategy(ns);
        } catch { /* ok */ }
        loadHistory();
      } catch (e: any) {
        console.error('Result fetch error:', e);
      }
    };

    // Try SSE first
    const token = useAuthStore.getState().token;
    const sseUrl = `${API_BASE}/stream/${jobId}?token=${encodeURIComponent(token || '')}`;
    let sseWorking = false;

    try {
      const es = new EventSource(sseUrl);
      sseRef.current = es;

      const handleEvent = (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data);
          const p: SolveProgress = {
            job_id: data.job_id,
            status: data.status,
            iteration: data.iteration || 0,
            total_iterations: data.total_iterations || 0,
            convergence_metric: data.convergence_metric || 0,
            elapsed_seconds: data.elapsed_seconds || 0,
            estimated_remaining_seconds: data.estimated_remaining_seconds || 0,
            progress_pct: data.progress_pct || 0,
            error: data.error || '',
            data_source: 'sse',
          };
          setProgress(p);
          sseWorking = true;
          if (terminals.includes(p.status)) {
            es.close();
            sseRef.current = null;
            setCancelRequested(false);
            handleTerminal(jobId);
          }
        } catch { /* ignore parse errors */ }
      };

      es.addEventListener('progress', handleEvent);
      es.addEventListener('done', handleEvent);
      es.addEventListener('failed', handleEvent);
      es.addEventListener('timeout', handleEvent);
      es.addEventListener('cancelled', handleEvent);

      es.onerror = () => {
        // SSE failed — fall back to polling
        if (!sseWorking) {
          es.close();
          sseRef.current = null;
          startPolling();
        }
      };
    } catch {
      // SSE not supported — use polling
      startPolling();
    }

    function startPolling() {
      if (pollRef.current) return;
      pollRef.current = setInterval(async () => {
        try {
          const p = await apiFetch(`/job/${jobId}`);
          setProgress(p);
          if (terminals.includes(p.status)) {
            setCancelRequested(false);
            handleTerminal(jobId!);
            if (pollRef.current) clearInterval(pollRef.current);
          }
        } catch (e: any) {
          console.error('Poll error:', e);
        }
      }, 1500);
    }

    return () => {
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [jobId, progress?.status, loadHistory]);

  // ── Start solve ──
  const handleSolve = useCallback(async () => {
    setError('');
    setResult(null);
    setNodeStrategy(null);
    setProgress(null);
    setWarnings([]);
    setCompareData(null);
    setCancelRequested(false);
    setIsSubmitting(true);

    try {
      const bs = betSizes.split(',').map(Number).filter(n => n > 0);
      const rs = raiseSizes.split(',').map(Number).filter(n => n > 0);

      const data = await apiFetch('/solve', API_BASE, {
        method: 'POST',
        body: JSON.stringify({
          board: boardCards,
          ip_range: ipRange,
          oop_range: oopRange,
          pot,
          effective_stack: stack,
          bet_sizes: bs,
          raise_sizes: rs,
          max_iterations: maxIter,
          max_raises: maxRaises,
          include_turn: includeTurn,
          max_turn_cards: maxTurnCards,
          include_river: includeTurn && includeRiver,
          max_river_cards: maxRiverCards,
          river_bet_sizes: [0.33, 0.5, 1.0],
          river_raise_sizes: [2.5],
          river_max_raises: 2,
          preset: advancedMode ? null : selectedPreset,
        }),
      });

      setJobId(data.job_id);
      setWarnings(data.warnings || []);
      setProgress({ ...data, iteration: 0, total_iterations: maxIter, convergence_metric: 0, elapsed_seconds: 0, estimated_remaining_seconds: data.estimated_seconds || 0, progress_pct: 0 });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsSubmitting(false);
    }
  }, [boardCards, ipRange, oopRange, pot, stack, betSizes, raiseSizes, maxIter, maxRaises, includeTurn, maxTurnCards, includeRiver, maxRiverCards]);

  // ── Inspect node ──
  const handleInspect = useCallback(async () => {
    if (!jobId || !inspectNodeId) return;
    setError('');
    try {
      const data = await apiFetch(`/node/${jobId}/${inspectNodeId}`);
      setNodeStrategy(data);
    } catch (e: any) {
      setError(e.message);
    }
  }, [jobId, inspectNodeId]);

  // ── Compare with heuristic ──
  const handleCompare = useCallback(async () => {
    if (!jobId) return;
    setIsComparing(true);
    try {
      const data = await apiFetch(
        `/solver-compare?solve_id=${jobId}&node_id=${inspectNodeId}`,
        EXPLORE_API,
      );
      setCompareData(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsComparing(false);
    }
  }, [jobId, inspectNodeId]);

  // ── Run benchmarks ──
  const handleRunBenchmarks = useCallback(async () => {
    setIsRunningBenchmarks(true);
    try {
      const data = await apiFetch('/benchmarks', API_BASE, { method: 'POST' });
      setBenchmarkData(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsRunningBenchmarks(false);
    }
  }, []);

  const isRunning = progress?.status === 'running' || progress?.status === 'queued';
  const isDone = ['done', 'timeout', 'cancelled'].includes(progress?.status || '');
  const isFailed = progress?.status === 'failed';
  const isCancelled = progress?.status === 'cancelled';

  // ── Cancel handler ──
  const handleCancel = useCallback(async () => {
    if (!jobId) return;
    setCancelRequested(true);
    try {
      await apiFetch(`/cancel/${jobId}`, API_BASE, { method: 'POST' });
    } catch (e: any) {
      console.error('Cancel error:', e);
      setCancelRequested(false);
    }
  }, [jobId]);

  // ── Simple report ──
  const rootStrategyData = nodeStrategy?.action_summary || null;
  const simpleReport = generateSimpleReport(
    rootStrategyData,
    result,
  );
  const coaching = generateCoachingSummary(rootStrategyData, result);

  // ── Tab config ──
  const tabs: { id: SolverTab; label: string; icon: any }[] = [
    { id: 'setup', label: 'Настройка', icon: Settings2 },
    { id: 'result', label: 'Результат', icon: Target },
    { id: 'history', label: 'История', icon: History },
  ];

  return (
    <div className="space-y-4 p-2 max-w-5xl mx-auto">
      {/* ══════ Header ══════ */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-primary flex items-center justify-center">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-foreground">Солвер</h1>
            <p className="text-xs text-muted-foreground">Рассчитайте оптимальную стратегию для конкретной ситуации</p>
          </div>
        </div>
        {/* Simple / Advanced toggle */}
        <button
          onClick={() => setAdvancedMode(!advancedMode)}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors border',
            advancedMode
              ? 'bg-violet-500/15 border-violet-500/30 text-violet-400'
              : 'bg-secondary/50 border-border text-muted-foreground hover:text-foreground',
          )}
        >
          {advancedMode ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
          {advancedMode ? 'Расширенный' : 'Простой'}
        </button>
      </div>

      {/* ══════ Tabs ══════ */}
      <div className="flex gap-1 bg-secondary/30 rounded-xl p-1">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-all',
              activeTab === tab.id
                ? 'bg-card text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
            {tab.id === 'result' && isDone && (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            )}
          </button>
        ))}
      </div>

      {/* ══════ SETUP TAB ══════ */}
      {activeTab === 'setup' && (
        <div className="space-y-4">
          {/* Beginner intro (collapsible) */}
          <details className="group">
            <summary className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer hover:text-foreground transition-colors">
              <Lightbulb className="w-3.5 h-3.5 text-amber-400" />
              <span>Что такое солвер и когда его использовать?</span>
              <ChevronRight className="w-3 h-3 group-open:rotate-90 transition-transform" />
            </summary>
            <div className="mt-2 p-3 bg-amber-500/5 border border-amber-500/15 rounded-xl text-xs text-muted-foreground space-y-1.5">
              <p><strong>Солвер</strong> — инструмент, который рассчитывает математически оптимальную стратегию для покерной ситуации.</p>
              <p>Используйте его, когда хотите узнать, какое действие (чек, бет, рейз) было бы оптимальным в конкретной раздаче.</p>
              <p>Для быстрого обучения используйте <strong>Тренировку</strong> или <strong>Обзор</strong> — они проще и не требуют ручной настройки.</p>
            </div>
          </details>

          {/* Honesty banner */}
          <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-3 text-xs text-amber-200 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <span>
              <strong>Ограничения:</strong> Солвер рассчитывает реальный CFR+ (Tammelin 2014), но ограничен постфлоп-ситуациями с маленькими диапазонами (~80 комбо/сторону).
            </span>
          </div>

          {/* Phase 10C: Preset Selector */}
          {!advancedMode && (
            <div className="bg-card border border-border rounded-2xl p-4 space-y-3">
              <label className="text-xs font-medium text-foreground uppercase tracking-wide">Режим расчёта</label>
              <div className="grid grid-cols-3 gap-2">
                {([
                  { key: 'fast' as const, icon: '⚡', label: 'Быстрый', desc: '2 размера ставок', time: '2–10 сек.', color: 'emerald' },
                  { key: 'standard' as const, icon: '⚖️', label: 'Стандартный', desc: '4 размера + рейзы', time: '10–30 сек.', color: 'primary' },
                  { key: 'deep' as const, icon: '🔬', label: 'Глубокий', desc: 'тёрн + ривер, 3 ставки, 1 рейз', time: '30–120 сек.', color: 'violet' },
                ]).map(p => (
                  <button
                    key={p.key}
                    onClick={() => setSelectedPreset(p.key)}
                    className={cn(
                      'relative flex flex-col items-center gap-1.5 p-3 rounded-xl border text-xs transition-all',
                      selectedPreset === p.key
                        ? p.color === 'emerald'
                          ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400 shadow-sm shadow-emerald-500/10'
                          : p.color === 'violet'
                          ? 'bg-violet-500/10 border-violet-500/40 text-violet-400 shadow-sm shadow-violet-500/10'
                          : 'bg-primary/10 border-primary/40 text-primary shadow-sm shadow-primary/10'
                        : 'bg-secondary/30 border-border text-muted-foreground hover:text-foreground hover:border-muted-foreground/40',
                    )}
                  >
                    <span className="text-lg">{p.icon}</span>
                    <span className="font-semibold">{p.label}</span>
                    <span className="text-[10px] text-muted-foreground text-center leading-tight">{p.desc}</span>
                    <span className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded-full mt-0.5',
                      selectedPreset === p.key
                        ? 'bg-foreground/10 text-foreground/70'
                        : 'bg-secondary text-muted-foreground/60',
                    )}>
                      ⏱ {p.time}
                    </span>
                    {selectedPreset === p.key && (
                      <div className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-current" />
                    )}
                  </button>
                ))}
              </div>
              {selectedPreset === 'deep' && (
                <div className="bg-amber-500/5 border border-amber-500/15 rounded-lg p-2 text-[10px] text-amber-400 flex items-start gap-1.5">
                  <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <span>Глубокий расчёт занимает больше времени и включает тёрн + ривер. Рекомендуется для детального анализа конкретных ситуаций.</span>
                    <span className="block text-amber-400/70">Примечание: при расчёте тёрна все режимы дают одинаковый результат, так как солвер полностью сходится за ~50 итераций. Выбор режима влияет на флоп и ривер.</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Board ── */}
          <div className="bg-card border border-border rounded-2xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-foreground uppercase tracking-wide">Борд (3-5 карт)</label>
              <button
                onClick={() => setBoardTextFallback(!boardTextFallback)}
                className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              >
                {boardTextFallback ? '↩ Выбор картами' : '⌨ Ввод текстом'}
              </button>
            </div>
            {boardTextFallback ? (
              <div className="space-y-2">
                <input
                  value={boardTextValue || boardCards.join(' ')}
                  onChange={e => {
                    setBoardTextValue(e.target.value);
                    const cards = e.target.value.trim().split(/\s+/).filter(c => /^[2-9TJQKA][shdc]$/i.test(c));
                    if (cards.length >= 3) setBoardCards(cards.slice(0, 5));
                  }}
                  className="w-full bg-secondary border border-border rounded-xl px-3 py-2.5 text-sm text-foreground outline-none focus:border-primary transition-colors font-mono"
                  placeholder="As Kh 7d"
                />
                <p className="text-[10px] text-muted-foreground">Введите карты через пробел: As Kh 7d</p>
              </div>
            ) : (
              <BoardPicker value={boardCards} onChange={setBoardCards} maxCards={5} />
            )}
          </div>

          {/* ── Ranges ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-card border border-border rounded-2xl p-4">
              <RangeBuilder
                value={ipRange}
                onChange={setIpRange}
                label="Диапазон IP (в позиции)"
                hint="Игрок, действующий последним"
              />
            </div>
            <div className="bg-card border border-border rounded-2xl p-4">
              <RangeBuilder
                value={oopRange}
                onChange={setOopRange}
                label="Диапазон OOP (без позиции)"
                hint="Игрок, действующий первым"
              />
            </div>
          </div>

          {/* ── Pot & Stack ── */}
          <div className="bg-card border border-border rounded-2xl p-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-foreground uppercase tracking-wide">Банк (bb)</label>
                <input
                  type="number"
                  value={pot}
                  onChange={e => setPot(Number(e.target.value))}
                  className="w-full mt-1.5 bg-secondary border border-border rounded-xl px-3 py-2.5 text-sm text-foreground outline-none focus:border-primary transition-colors"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-foreground uppercase tracking-wide">Стек (bb)</label>
                <input
                  type="number"
                  value={stack}
                  onChange={e => setStack(Number(e.target.value))}
                  className="w-full mt-1.5 bg-secondary border border-border rounded-xl px-3 py-2.5 text-sm text-foreground outline-none focus:border-primary transition-colors"
                />
              </div>
            </div>
          </div>

          {/* ── Advanced Options ── */}
          {advancedMode && (
            <div className="bg-card border border-violet-500/20 rounded-2xl p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs font-medium text-violet-400">
                <Settings2 className="w-3.5 h-3.5" />
                Расширенные настройки
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-muted-foreground uppercase">Размеры бетов (доля банка)</label>
                  <input value={betSizes} onChange={e => setBetSizes(e.target.value)}
                    className="w-full mt-1 bg-secondary border border-border rounded-lg px-2.5 py-2 text-xs text-foreground outline-none focus:border-primary font-mono" />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground uppercase">Размеры рейзов (множитель)</label>
                  <input value={raiseSizes} onChange={e => setRaiseSizes(e.target.value)}
                    className="w-full mt-1 bg-secondary border border-border rounded-lg px-2.5 py-2 text-xs text-foreground outline-none focus:border-primary font-mono" />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground uppercase">Макс. итераций</label>
                  <input type="number" value={maxIter} onChange={e => setMaxIter(Number(e.target.value))}
                    className="w-full mt-1 bg-secondary border border-border rounded-lg px-2.5 py-2 text-xs text-foreground outline-none focus:border-primary" />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground uppercase">Макс. рейзов на улице</label>
                  <input type="number" value={maxRaises} onChange={e => setMaxRaises(Number(e.target.value))}
                    className="w-full mt-1 bg-secondary border border-border rounded-lg px-2.5 py-2 text-xs text-foreground outline-none focus:border-primary" />
                </div>
              </div>
              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                <input type="checkbox" checked={includeTurn} onChange={e => {
                  setIncludeTurn(e.target.checked);
                  if (!e.target.checked) setIncludeRiver(false);
                }}
                  className="rounded border-border" />
                Включить тёрн <span className="text-[10px] text-muted-foreground/60">(ограниченный)</span>
              </label>
              {includeTurn && (
                <div className="pl-6 space-y-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground uppercase">Макс. карт тёрна</label>
                    <input type="number" value={maxTurnCards} onChange={e => setMaxTurnCards(Number(e.target.value))}
                      className="w-32 mt-1 bg-secondary border border-border rounded-lg px-2.5 py-2 text-xs text-foreground outline-none focus:border-primary" />
                  </div>
                  <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                    <input type="checkbox" checked={includeRiver} onChange={e => setIncludeRiver(e.target.checked)}
                      className="rounded border-border" />
                    Включить ривер <span className="text-[10px] text-muted-foreground/60">(минимальная абстракция)</span>
                  </label>
                  {includeRiver && (
                    <div className="pl-6 space-y-2">
                      <div>
                        <label className="text-[10px] text-muted-foreground uppercase">Макс. карт ривера</label>
                        <input type="number" value={maxRiverCards} onChange={e => setMaxRiverCards(Math.min(10, Math.max(1, Number(e.target.value))))}
                          className="w-32 mt-1 bg-secondary border border-border rounded-lg px-2.5 py-2 text-xs text-foreground outline-none focus:border-primary" />
                      </div>
                      <div className="bg-amber-500/5 border border-amber-500/15 rounded-lg p-2 text-[10px] text-amber-400 flex items-start gap-1.5">
                        <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
                        <span>Ривер добавляет значительное время расчёта. Абстракция: 3 размера ставок (33%, 50%, 100%), 1 рейз. Максимум 15 комбо/сторону. Для маленьких диапазонов.</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── Error ── */}
          {error && (() => {
            const he = humanizeError(error);
            return (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-base">{he.icon}</span>
                  <span className="text-sm font-medium text-red-400">{he.title}</span>
                </div>
                <p className="text-xs text-red-400/80">{he.description}</p>
                <p className="text-[10px] text-muted-foreground">💡 {he.suggestion}</p>
                {he.action && (
                  <button
                    onClick={() => {
                      if (he.action!.type === 'reduce_range') {
                        setIpRange('AA,KK,AKs');
                        setOopRange('QQ,JJ,AQs');
                        setError('');
                      } else if (he.action!.type === 'disable_turn') {
                        setIncludeTurn(false);
                        setError('');
                      } else {
                        setError('');
                      }
                    }}
                    className="text-xs text-primary hover:underline"
                  >
                    {he.action.label} →
                  </button>
                )}
              </div>
            );
          })()}

          {/* ── Warnings ── */}
          {warnings.length > 0 && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-3 text-xs text-amber-400 space-y-1">
              {warnings.map((w, i) => <div key={i}>⚠️ {w}</div>)}
            </div>
          )}

          {/* ── Solve Button with runtime guidance ── */}
          {!advancedMode && (
            <div className="flex items-center gap-2 justify-center text-[10px] text-muted-foreground">
              <Clock className="w-3 h-3" />
              <span>
                {selectedPreset === 'fast' ? 'Примерно 2–10 сек.' :
                 selectedPreset === 'standard' ? 'Примерно 10–30 сек.' :
                 'Примерно 30–120 сек. (включает тёрн + ривер)'}
              </span>
              <span className={cn(
                'px-1.5 py-0.5 rounded-full text-[9px] font-medium',
                selectedPreset === 'fast' ? 'bg-emerald-500/15 text-emerald-400' :
                selectedPreset === 'standard' ? 'bg-primary/15 text-primary' :
                'bg-violet-500/15 text-violet-400',
              )}>
                {selectedPreset === 'fast' ? 'Лёгкий' :
                 selectedPreset === 'standard' ? 'Средний' :
                 'Тяжёлый'}
              </span>
            </div>
          )}
          <button
            onClick={handleSolve}
            disabled={isSubmitting || isRunning}
            className={cn(
              'w-full py-3.5 rounded-2xl text-sm font-semibold flex items-center justify-center gap-2 transition-all shadow-lg',
              isSubmitting || isRunning
                ? 'bg-secondary text-muted-foreground cursor-wait'
                : 'bg-gradient-to-r from-emerald-500 to-primary text-white hover:brightness-110 active:scale-[0.99]',
            )}
          >
            {isSubmitting ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Отправляем...</>
            ) : isRunning ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Расчёт идёт...</>
            ) : (
              <><PlayCircle className="w-4 h-4" /> Запустить солвер</>
            )}
          </button>

          {/* ── Progress (inline) with cancel ── */}
          {progress && isRunning && (
            <div className="bg-card border border-border rounded-2xl p-4 space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-amber-400 font-medium">
                  {cancelRequested ? '⏳ Отмена запрошена...' : 'Расчёт...'}
                </span>
                <span className="text-muted-foreground">{progress.iteration}/{progress.total_iterations}</span>
              </div>
              <div className="w-full bg-secondary rounded-full h-2.5 overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-500',
                    cancelRequested ? 'bg-amber-500' : 'bg-primary',
                  )}
                  style={{ width: `${Math.min(100, (progress.iteration / Math.max(progress.total_iterations, 1)) * 100)}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-muted-foreground">
                <span>Сходимость: {progress.convergence_metric.toFixed(6)}</span>
                <span>{progress.elapsed_seconds.toFixed(1)} сек.</span>
                {progress.estimated_remaining_seconds > 0 && (
                  <span className="text-amber-400">~{progress.estimated_remaining_seconds.toFixed(0)} сек. осталось</span>
                )}
              </div>
              {/* Cancel button */}
              <button
                onClick={handleCancel}
                disabled={cancelRequested}
                className={cn(
                  'w-full py-2.5 rounded-xl text-xs font-medium flex items-center justify-center gap-2 transition-all border',
                  cancelRequested
                    ? 'bg-amber-500/10 border-amber-500/30 text-amber-400 cursor-wait'
                    : 'bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20 hover:border-red-500/50',
                )}
              >
                {cancelRequested ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Ожидание завершения чанка...</>
                ) : (
                  <><StopCircle className="w-3.5 h-3.5" /> Отменить расчёт</>
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {/* ══════ RESULT TAB ══════ */}
      {activeTab === 'result' && (
        <div className="space-y-4">
          {!result && !progress && (
            <div className="text-center py-16 space-y-3">
              <Cpu className="w-10 h-10 text-muted-foreground/30 mx-auto" />
              <p className="text-sm text-muted-foreground">Нет результатов</p>
              <p className="text-xs text-muted-foreground/60">Перейдите в «Настройка» и запустите расчёт</p>
              <button onClick={() => setActiveTab('setup')} className="text-xs text-primary hover:underline">
                → Настроить расчёт
              </button>
            </div>
          )}

          {progress && isRunning && (
            <div className="bg-card border border-border rounded-2xl p-6 text-center space-y-3">
              <Loader2 className="w-8 h-8 text-primary animate-spin mx-auto" />
              <p className="text-sm text-foreground">
                {cancelRequested ? 'Отмена запрошена...' : 'Расчёт выполняется...'}
              </p>
              <div className="w-full max-w-xs mx-auto bg-secondary rounded-full h-2.5 overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-500',
                    cancelRequested ? 'bg-amber-500' : 'bg-primary',
                  )}
                  style={{ width: `${Math.min(100, (progress.iteration / Math.max(progress.total_iterations, 1)) * 100)}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Итерация {progress.iteration}/{progress.total_iterations} • {progress.elapsed_seconds.toFixed(1)} сек.
              </p>
              <button
                onClick={handleCancel}
                disabled={cancelRequested}
                className={cn(
                  'px-4 py-2 rounded-xl text-xs font-medium flex items-center justify-center gap-2 mx-auto transition-all border',
                  cancelRequested
                    ? 'bg-amber-500/10 border-amber-500/30 text-amber-400 cursor-wait'
                    : 'bg-red-500/10 border-red-500/30 text-red-400 hover:bg-red-500/20',
                )}
              >
                {cancelRequested ? (
                  <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Отменяем...</>
                ) : (
                  <><StopCircle className="w-3.5 h-3.5" /> Отменить</>
                )}
              </button>
            </div>
          )}

          {isFailed && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-4 text-center space-y-2">
              <XCircle className="w-8 h-8 text-red-400 mx-auto" />
              <p className="text-sm text-red-400">Расчёт не удался</p>
              <p className="text-xs text-muted-foreground">{progress?.error || 'Произошла ошибка'}</p>
            </div>
          )}

          {/* Cancelled state */}
          {isCancelled && result && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 space-y-2">
              <div className="flex items-center justify-center gap-2">
                <StopCircle className="w-5 h-5 text-amber-400" />
                <p className="text-sm text-amber-400 font-medium">Расчёт отменён</p>
              </div>
              <p className="text-xs text-muted-foreground text-center">
                Выполнено {result.iterations} из {progress?.total_iterations || '?'} итераций.
                Частичные результаты сохранены и показаны ниже.
              </p>
            </div>
          )}

          {/* ── Simple Report Card ── */}
          {result && isDone && (
            <div className="space-y-4">
              {/* Main recommendation card */}
              <div className="bg-card border border-border rounded-2xl p-5 space-y-4">
                {/* Primary recommendation */}
                <div className="text-center space-y-2">
                  <div className="text-2xl font-bold text-foreground">
                    {simpleReport.mainRecommendation}
                  </div>
                  <div className={cn(
                    'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium',
                    simpleReport.strategyType === 'pure'
                      ? 'bg-emerald-500/15 text-emerald-400'
                      : simpleReport.strategyType === 'mixed'
                      ? 'bg-amber-500/15 text-amber-400'
                      : 'bg-sky-500/15 text-sky-400',
                  )}>
                    <Sparkles className="w-3 h-3" />
                    {simpleReport.strategyLabel}
                  </div>
                </div>

                {/* Explanation */}
                <p className="text-xs text-muted-foreground text-center leading-relaxed">
                  {simpleReport.strategyExplanation}
                </p>

                {/* Action bars */}
                {simpleReport.actions.length > 0 && (
                  <div className="space-y-1.5">
                    {simpleReport.actions.map(a => (
                      <div key={a.name} className="flex items-center gap-2">
                        <span className="text-xs text-foreground w-20 text-right">{a.nameRu}</span>
                        <div className="flex-1 h-5 bg-secondary/50 rounded overflow-hidden">
                          <div
                            className={cn(
                              'h-full rounded transition-all',
                              a.frequency >= 0.5 ? 'bg-emerald-500/70' : a.frequency >= 0.2 ? 'bg-primary/60' : 'bg-muted-foreground/30',
                            )}
                            style={{ width: `${a.frequency * 100}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono text-muted-foreground w-12 text-right">
                          {(a.frequency * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Trust & scope + preset badge */}
                <div className="flex flex-wrap gap-2 pt-2 border-t border-border">
                  {/* Phase 18B: Only show old trust badge if backend quality is NOT available */}
                  {!result.metadata?.solve_quality?.quality_class && (
                  <div className={cn(
                    'flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-medium border',
                    simpleReport.trustLevel === 'high'
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : simpleReport.trustLevel === 'medium'
                      ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      : 'bg-red-500/10 border-red-500/30 text-red-400',
                  )}>
                    <ShieldCheck className="w-3 h-3" />
                    {simpleReport.trustLabel}
                  </div>
                  )}
                  {result.converged && (
                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-medium bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                      <CheckCircle2 className="w-3 h-3" /> Сошёлся
                    </div>
                  )}
                  {result.metadata?.street_depth && (
                    <div className={cn(
                      'flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-medium border',
                      result.metadata.street_depth === 'flop_plus_turn_plus_river'
                        ? 'bg-violet-500/10 border-violet-500/30 text-violet-400'
                        : result.metadata.street_depth === 'flop_plus_turn'
                        ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400'
                        : 'bg-slate-500/10 border-slate-500/30 text-slate-400',
                    )}>
                      {result.metadata.street_depth === 'flop_plus_turn_plus_river' ? 'Флоп+тёрн+ривер'
                       : result.metadata.street_depth === 'flop_plus_turn' ? 'Флоп+тёрн' : 'Только флоп'}
                    </div>
                  )}
                  {/* Phase 10C: Preset badge */}
                  {result.metadata?.action_abstraction && (
                    <div className={cn(
                      'flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-medium border',
                      result.metadata.action_abstraction?.includes('7 bet')
                        ? 'bg-violet-500/10 border-violet-500/30 text-violet-400'
                        : result.metadata.action_abstraction?.includes('4 bet') || result.metadata.action_abstraction?.includes('3 bet')
                        ? 'bg-primary/10 border-primary/30 text-primary'
                        : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
                    )}>
                      <Settings2 className="w-3 h-3" />
                      {result.metadata.action_abstraction?.includes('7 bet') ? 'Глубокий'
                       : result.metadata.action_abstraction?.includes('4 bet') || result.metadata.action_abstraction?.includes('3 bet') ? 'Стандартный'
                       : 'Быстрый'}
                    </div>
                  )}
                  {/* Phase 16A: Stop reason badge */}
                  {result.metadata?.stop_reason && (
                    <div className={cn(
                      'flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-medium border',
                      result.metadata.stop_reason === 'converged'
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                        : result.metadata.stop_reason === 'plateau'
                        ? 'bg-sky-500/10 border-sky-500/30 text-sky-400'
                        : result.metadata.stop_reason === 'cancelled'
                        ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                        : 'bg-slate-500/10 border-slate-500/30 text-slate-400',
                    )}>
                      {result.metadata.stop_reason_icon || '🔢'} {result.metadata.stop_reason_label || result.metadata.stop_reason}
                    </div>
                  )}
                  {/* Phase 16A: Quality badge */}
                  {result.metadata?.solve_quality?.quality_class && (
                    <div className={cn(
                      'flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-medium border',
                      result.metadata.solve_quality.quality_class === 'good'
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                        : result.metadata.solve_quality.quality_class === 'acceptable'
                        ? 'bg-sky-500/10 border-sky-500/30 text-sky-400'
                        : result.metadata.solve_quality.quality_class === 'weak'
                        ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                        : 'bg-red-500/10 border-red-500/30 text-red-400',
                    )}>
                      {result.metadata.solve_quality.quality_label_ru}
                    </div>
                  )}
                </div>

                {/* Phase 16B: Stop reason explanation for user understanding */}
                <div className="text-[10px] text-muted-foreground/70 space-y-0.5">
                  <p>{simpleReport.trustReason}</p>
                  <p>{simpleReport.scopeNote}</p>
                  {/* Phase 16C: Use backend quality_explanation_ru if available */}
                  {result.metadata?.solve_quality?.quality_explanation_ru && (
                    <p className="mt-1">{result.metadata.solve_quality.quality_explanation_ru}</p>
                  )}
                  {!result.metadata?.solve_quality?.quality_explanation_ru && result.metadata?.stop_reason && (
                    <p className="mt-1">
                      {result.metadata.stop_reason === 'converged'
                        ? 'Стратегия стабилизировалась. Результат можно использовать для изучения.'
                        : result.metadata.stop_reason === 'plateau'
                        ? 'Расчёт замедлился. Стратегия приблизительная, но дополнительные итерации дадут минимальное улучшение.'
                        : result.metadata.stop_reason === 'max_iterations'
                        ? 'Выполнены все запланированные итерации. Для более точного результата попробуйте пресет «Глубокий».'
                        : result.metadata.stop_reason === 'cancelled'
                        ? 'Расчёт был прерван. Результат может быть неточным.'
                        : ''}
                    </p>
                  )}
                </div>
              </div>

              {/* ── Coaching Insights ── */}
              <div className="bg-card border border-violet-500/20 rounded-2xl p-5 space-y-3">
                <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-violet-400" />
                  Тренер рекомендует
                </h3>

                {/* Main Idea */}
                <div className="p-3 bg-secondary/50 rounded-xl">
                  <div className="text-[10px] font-medium text-muted-foreground mb-1">💡 Главная идея</div>
                  <p className="text-xs text-foreground leading-relaxed">{coaching.mainIdea}</p>
                </div>

                {/* Key Takeaway */}
                <div className="p-3 bg-primary/5 border border-primary/10 rounded-xl">
                  <div className="text-[10px] font-medium text-muted-foreground mb-1">📝 Что запомнить</div>
                  <p className="text-xs text-foreground leading-relaxed">{coaching.keyTakeaway}</p>
                </div>

                {/* Strictness */}
                <div className="flex items-center gap-2">
                  <div className={cn(
                    'px-2.5 py-1 rounded-lg text-[10px] font-medium border',
                    coaching.strictness === 'strict'
                      ? 'bg-red-500/10 border-red-500/20 text-red-400'
                      : coaching.strictness === 'flexible'
                      ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                      : 'bg-sky-500/10 border-sky-500/20 text-sky-400',
                  )}>{coaching.strictnessLabel}</div>
                  <span className="text-[10px] text-muted-foreground">{coaching.strictnessExplanation}</span>
                </div>

                {/* Next Step */}
                <div className="text-[10px] text-muted-foreground italic">
                  👉 {coaching.nextStepAdvice}
                </div>

                {/* Source disclosure */}
                <div className="text-[9px] text-muted-foreground/50 pt-1 border-t border-border">
                  ⚡ Рекомендации основаны на интерпретации частот солвера. Не являются математически точной стратегией.
                </div>
              </div>

              {/* ── What's Next? ── */}
              <div className="bg-card border border-border rounded-2xl p-4 space-y-3">
                <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Lightbulb className="w-4 h-4 text-amber-400" />
                  Что дальше?
                </h3>
                <p className="text-xs text-muted-foreground">Используйте результат для углубления знаний:</p>
                <div className="grid grid-cols-3 gap-2">
                  {POST_SOLVE_ACTIONS.map(action => (
                    <button
                      key={action.id}
                      onClick={() => {
                        const boardDisplay = boardCards.join(' ');
                        setSolverContext({
                          source: 'solver',
                          solveId: jobId || null,
                          board: boardCards,
                          boardDisplay: boardDisplay,
                          spotLabel: `Флоп ${boardDisplay}`,
                          coachingNote: coaching.keyTakeaway || '',
                          mainIdea: coaching.mainIdea,
                          keyTakeaway: coaching.keyTakeaway,
                          strictness: coaching.strictness,
                          strictnessLabel: coaching.strictnessLabel,
                          rootStrategy: rootStrategyData || undefined,
                          // Session progression
                          currentStep: action.id === 'drill' ? 2 : action.id === 'explore' ? 3 : 4,
                          completedSteps: [1],
                          drillsInSession: 0,
                          drillsCorrectInSession: 0,
                        });
                        navigate(action.route);
                      }}
                      className="flex flex-col items-center gap-1.5 p-3 rounded-xl bg-secondary/50 border border-border hover:bg-secondary hover:border-muted-foreground/30 transition-all text-center group"
                    >
                      <span className="text-xl">{action.emoji}</span>
                      <span className="text-xs font-medium text-foreground">{action.title}</span>
                      <span className="text-[9px] text-muted-foreground">{action.description}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* ── Technical Details (expandable) ── */}
              <div className="bg-card border border-border rounded-2xl overflow-hidden">
                <button
                  onClick={() => setShowTechDetails(!showTechDetails)}
                  className="w-full flex items-center justify-between p-4 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <BarChart3 className="w-3.5 h-3.5" />
                    Подробности и технические данные
                  </span>
                  <ChevronDown className={cn('w-4 h-4 transition-transform', showTechDetails && 'rotate-180')} />
                </button>

                {showTechDetails && (
                  <div className="px-4 pb-4 space-y-4 border-t border-border pt-4">
                    {/* Stats grid */}
                    <div className="grid grid-cols-2 gap-y-1.5 text-xs">
                      {[
                        ['Итерации', result.iterations],
                        ['Сходимость', result.convergence_metric.toFixed(6)],
                        ['Время', `${result.elapsed_seconds.toFixed(1)} сек.`],
                        ['Узлов дерева', result.tree_nodes],
                        ['IP комбо', result.ip_combos],
                        ['OOP комбо', result.oop_combos],
                        ['Сопоставлений', result.matchups],
                        ['Рассчитано узлов', result.node_count],
                        ...(result.metadata?.include_river ? [
                          ['Глубина', result.metadata.street_depth === 'flop_plus_turn_plus_river' ? 'Флоп+тёрн+ривер' : result.metadata.street_depth],
                          ['Карт тёрна', result.metadata.turn_cards_explored ?? '—'],
                          ['Карт ривера', result.metadata.river_cards_explored ?? '—'],
                          ['Ривер ставки', result.metadata.river_bet_sizes?.join(', ') ?? '—'],
                        ] : []),
                      ].map(([label, val]) => (
                        <div key={label as string} className="flex justify-between pr-4">
                          <span className="text-muted-foreground">{label}</span>
                          <span className="text-foreground font-mono">{val}</span>
                        </div>
                      ))}
                    </div>

                    {/* Validation */}
                    {result.validation && Object.keys(result.validation).length > 0 && (
                      <div className="border-t border-border pt-3 space-y-1">
                        <h4 className="text-xs font-medium text-foreground flex items-center gap-1.5">
                          <Shield className="w-3.5 h-3.5 text-primary" />
                          Отчёт о валидации
                        </h4>
                        <div className="text-[10px] text-muted-foreground">
                          Проверки: {result.validation.checks_passed}/{result.validation.checks_run} пройдено
                        </div>
                        {result.validation.issues?.length > 0 && (
                          <div className="text-[10px] text-red-400">Проблемы: {result.validation.issues.join('; ')}</div>
                        )}
                      </div>
                    )}

                    {/* Exploitability */}
                    {result.exploitability && Object.keys(result.exploitability).length > 0 && (
                      <div className="border-t border-border pt-3 space-y-1.5">
                        <h4 className="text-xs font-medium text-foreground flex items-center gap-1.5">
                          <BarChart3 className="w-3.5 h-3.5 text-violet-400" />
                          Эксплоитабельность
                        </h4>
                        <div className="grid grid-cols-2 gap-y-1 text-[10px]">
                          <div className="flex justify-between pr-4">
                            <span className="text-muted-foreground">Значение:</span>
                            <span className="text-foreground font-mono font-bold">
                              {result.exploitability.exploitability_mbb_per_hand?.toFixed(2)} mbb/разд.
                            </span>
                          </div>
                          <div className="flex justify-between pr-4">
                            <span className="text-muted-foreground">Значение IP BR:</span>
                            <span className="text-foreground font-mono">{result.exploitability.ip_br_value_bb?.toFixed(4)} bb</span>
                          </div>
                        </div>
                        {result.exploitability.quality_label && (
                          <div className={cn(
                            'text-[10px] font-medium px-2 py-1 rounded inline-block',
                            result.exploitability.exploitability_mbb_per_hand < 10 ? 'bg-emerald-500/10 text-emerald-400' :
                            result.exploitability.exploitability_mbb_per_hand < 50 ? 'bg-amber-500/10 text-amber-400' :
                            'bg-red-500/10 text-red-400',
                          )}>
                            {result.exploitability.quality_label}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Trust grade */}
                    {result.trust_grade && result.trust_grade.grade && (
                      <div className="border-t border-border pt-3 space-y-1">
                        <h4 className="text-xs font-medium text-foreground flex items-center gap-1.5">
                          <ShieldCheck className="w-3.5 h-3.5 text-primary" />
                          Оценка надёжности
                        </h4>
                        <div className="text-[10px] text-muted-foreground">{result.trust_grade.explanation}</div>
                        {result.trust_grade.honest_note && (
                          <div className="text-[9px] text-muted-foreground/50">{result.trust_grade.honest_note}</div>
                        )}
                      </div>
                    )}

                    {/* Node inspector */}
                    <div className="border-t border-border pt-3 space-y-2">
                      <h4 className="text-xs font-medium text-foreground">Просмотр узла</h4>
                      <div className="flex gap-2">
                        <input
                          value={inspectNodeId}
                          onChange={e => setInspectNodeId(e.target.value)}
                          className="flex-1 bg-secondary border border-border rounded-lg px-2 py-1.5 text-xs text-foreground outline-none focus:border-primary"
                          placeholder="node_0"
                        />
                        <button onClick={handleInspect}
                          className="px-3 py-1.5 bg-primary/20 border border-primary/30 text-primary text-xs rounded-lg hover:bg-primary/30 transition-colors">
                          Показать
                        </button>
                        <button onClick={handleCompare} disabled={isComparing}
                          className="px-3 py-1.5 bg-violet-500/20 border border-violet-500/30 text-violet-400 text-xs rounded-lg hover:bg-violet-500/30 transition-colors flex items-center gap-1 disabled:opacity-50">
                          {isComparing ? <Loader2 className="w-3 h-3 animate-spin" /> : <GitCompare className="w-3 h-3" />}
                          Сравнить
                        </button>
                      </div>
                    </div>

                    {/* Node strategy display */}
                    {nodeStrategy && (
                      <div className="space-y-2">
                        <div className="flex rounded-lg overflow-hidden h-6 border border-border">
                          {Object.entries(nodeStrategy.action_summary).map(([action, freq], idx) => {
                            const colors = ['bg-emerald-500', 'bg-blue-500', 'bg-amber-500', 'bg-red-500', 'bg-purple-500'];
                            return (
                              <div
                                key={action}
                                className={cn(colors[idx % colors.length], 'flex items-center justify-center')}
                                style={{ width: `${freq * 100}%` }}
                                title={`${action}: ${(freq * 100).toFixed(1)}%`}
                              >
                                {freq > 0.08 && (
                                  <span className="text-[9px] text-white font-medium truncate px-1">
                                    {action} {(freq * 100).toFixed(0)}%
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                        <div className="max-h-48 overflow-auto space-y-0.5">
                          {Object.entries(nodeStrategy.combos).slice(0, 20).map(([combo, freqs]) => (
                            <div key={combo} className="flex items-center gap-2 text-[10px] py-0.5">
                              <span className="w-10 font-mono text-foreground font-medium">{combo}</span>
                              <div className="flex-1 flex rounded overflow-hidden h-3">
                                {Object.entries(freqs).map(([action, freq], idx) => {
                                  const colors = ['bg-emerald-500/80', 'bg-blue-500/80', 'bg-amber-500/80', 'bg-red-500/80'];
                                  return freq > 0.001 ? (
                                    <div key={action} className={colors[idx % colors.length]}
                                      style={{ width: `${freq * 100}%` }}
                                      title={`${combo}: ${action} ${(freq * 100).toFixed(1)}%`} />
                                  ) : null;
                                })}
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="text-[10px] text-muted-foreground/50">
                          Показано до 20 комбо. Всего: {Object.keys(nodeStrategy.combos).length}
                        </div>
                      </div>
                    )}

                    {/* Compare data */}
                    {compareData && (
                      <div className="space-y-2 bg-violet-500/5 border border-violet-500/20 rounded-xl p-3">
                        <h4 className="text-xs font-medium text-violet-300 flex items-center gap-1.5">
                          <GitCompare className="w-3.5 h-3.5" />
                          Эвристика вс солвер
                        </h4>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-1.5">
                            <div className="text-[10px] font-medium text-emerald-400">{compareData.solver_strategy.label}</div>
                            {Object.entries(compareData.solver_strategy.summary).map(([action, freq]) => (
                              <div key={action} className="flex items-center gap-1.5 text-[10px]">
                                <div className="flex-1 bg-secondary rounded h-3 overflow-hidden">
                                  <div className="bg-emerald-500/70 h-full rounded" style={{ width: `${(freq as number) * 100}%` }} />
                                </div>
                                <span className="text-muted-foreground w-24 text-right">
                                  {action}: {((freq as number) * 100).toFixed(1)}%
                                </span>
                              </div>
                            ))}
                          </div>
                          <div className="space-y-1.5">
                            <div className="text-[10px] font-medium text-amber-400">{compareData.heuristic_strategy.label}</div>
                            {Object.entries(compareData.heuristic_strategy.summary).map(([action, freq]) => (
                              <div key={action} className="flex items-center gap-1.5 text-[10px]">
                                <div className="flex-1 bg-secondary rounded h-3 overflow-hidden">
                                  <div className="bg-amber-500/70 h-full rounded" style={{ width: `${(freq as number) * 100}%` }} />
                                </div>
                                <span className="text-muted-foreground w-24 text-right">
                                  {action}: {((freq as number) * 100).toFixed(1)}%
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                        <div className="text-[9px] text-muted-foreground/50 flex items-start gap-1">
                          <Info className="w-3 h-3 mt-0.5 shrink-0" />
                          {compareData.comparison_note}
                        </div>
                      </div>
                    )}

                    {/* Benchmarks */}
                    <div className="border-t border-border pt-3 space-y-2">
                      <button onClick={handleRunBenchmarks} disabled={isRunningBenchmarks}
                        className="px-3 py-1.5 bg-violet-500/20 border border-violet-500/30 text-violet-400 text-xs rounded-lg hover:bg-violet-500/30 transition-colors flex items-center gap-1.5 disabled:opacity-50">
                        {isRunningBenchmarks ? (
                          <><Loader2 className="w-3 h-3 animate-spin" /> Тесты корректности...</>
                        ) : (
                          <><RefreshCw className="w-3 h-3" /> Запустить тесты</>
                        )}
                      </button>
                      {benchmarkData && (
                        <div className="space-y-1.5">
                          <div className={cn(
                            'text-[10px] font-medium px-2 py-1 rounded',
                            benchmarkData.overall_status === 'PASS' ? 'bg-emerald-500/10 text-emerald-400' :
                            benchmarkData.overall_status === 'PASS_WITH_WARNINGS' ? 'bg-amber-500/10 text-amber-400' :
                            'bg-red-500/10 text-red-400',
                          )}>
                            {benchmarkData.passed}/{benchmarkData.total} пройдено, {benchmarkData.failed} провалено ({benchmarkData.elapsed_seconds.toFixed(1)} сек.)
                          </div>
                        </div>
                      )}
                    </div>

                    {result.metadata?.honest_note && (
                      <div className="text-[10px] text-muted-foreground/60 flex items-start gap-1.5 pt-1">
                        <Info className="w-3 h-3 mt-0.5 shrink-0" />
                        {result.metadata.honest_note}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════ HISTORY TAB ══════ */}
      {activeTab === 'history' && (
        <div className="space-y-3">
          {history.length === 0 ? (
            <div className="text-center py-16 space-y-3">
              <History className="w-10 h-10 text-muted-foreground/30 mx-auto" />
              <p className="text-sm text-muted-foreground">Нет сохранённых расчётов</p>
              <p className="text-xs text-muted-foreground/60">Запустите расчёт в разделе «Настройка»</p>
            </div>
          ) : (
            history.map(h => (
              <button
                key={h.id}
                onClick={async () => {
                  setSelectedHistoryId(h.id);
                  setLoadingDetail(true);
                  try {
                    const d = await apiFetch(`/result/${h.id}`);
                    setHistoryDetail(d);
                  } catch { /* */ }
                  setLoadingDetail(false);
                }}
                className={cn(
                  'w-full text-left bg-card border rounded-xl p-3 space-y-1 transition-colors',
                  selectedHistoryId === h.id ? 'border-primary' : 'border-border hover:border-muted-foreground/30',
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-foreground font-mono">
                    {h.board?.join(' ') || '—'}
                  </span>
                  {/* Phase 16B: show stop reason in history card, not just generic status */}
                  <span className={cn(
                    'text-[10px] px-1.5 py-0.5 rounded font-medium',
                    h.status === 'cancelled' ? 'bg-amber-500/15 text-amber-400' :
                    h.status === 'failed' ? 'bg-red-500/15 text-red-400' :
                    h.status === 'timeout' ? 'bg-orange-500/15 text-orange-400' :
                    h.stop_reason === 'converged' ? 'bg-emerald-500/15 text-emerald-400' :
                    h.stop_reason === 'plateau' ? 'bg-sky-500/15 text-sky-400' :
                    h.converged ? 'bg-emerald-500/15 text-emerald-400' :
                    'bg-slate-500/15 text-slate-400',
                  )}>
                    {h.status === 'cancelled' ? '⚠️ Отменён' :
                     h.status === 'failed' ? '❌ Ошибка' :
                     h.status === 'timeout' ? '⏱ Таймаут' :
                     h.stop_reason === 'converged' ? '✅ Сошёлся' :
                     h.stop_reason === 'plateau' ? '📊 Плато' :
                     h.stop_reason === 'max_iterations' ? '🔢 Лимит' :
                     h.converged ? '✅ Завершён' : '✅ Готово'}
                  </span>
                </div>
                <div className="flex gap-3 text-[10px] text-muted-foreground">
                  <span>IP: {h.ip_range?.slice(0, 20)}{(h.ip_range?.length || 0) > 20 ? '...' : ''}</span>
                  <span>OOP: {h.oop_range?.slice(0, 20)}{(h.oop_range?.length || 0) > 20 ? '...' : ''}</span>
                </div>
                <div className="flex gap-3 text-[10px] text-muted-foreground/60">
                  <span>{h.iterations} итер.</span>
                  <span>{h.elapsed_seconds.toFixed(1)} сек.</span>
                  {h.exploitability_mbb != null && <span>{h.exploitability_mbb.toFixed(1)} mbb</span>}
                  {/* Phase 16B: show quality class in history */}
                  {h.quality_class && (
                    <span className={cn(
                      h.quality_class === 'good' ? 'text-emerald-400' :
                      h.quality_class === 'acceptable' ? 'text-sky-400' :
                      h.quality_class === 'weak' ? 'text-amber-400' :
                      'text-red-400',
                    )}>
                      {h.quality_class === 'good' ? '● надёжный' :
                       h.quality_class === 'acceptable' ? '● рабочий' :
                       h.quality_class === 'weak' ? '● прибл.' :
                       '● неполный'}
                    </span>
                  )}
                  {h.street_depth === 'flop_plus_turn_plus_river' && (
                    <span className="text-violet-400">🃏 ривер</span>
                  )}
                  {h.street_depth === 'flop_plus_turn' && !h.street_depth?.includes('river') && (
                    <span className="text-cyan-400">тёрн</span>
                  )}
                  <span className="ml-auto">{new Date(h.created_at).toLocaleString('ru-RU')}</span>
                </div>
              </button>
            ))
          )}

          {/* History detail */}
          {selectedHistoryId && historyDetail && (
            <div className="bg-card border border-primary/30 rounded-xl p-4 space-y-2">
              <h4 className="text-xs font-medium text-foreground">Детали расчёта</h4>
              {loadingDetail ? (
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
              ) : (
                <div className="grid grid-cols-2 gap-y-1 text-[10px]">
                  {[
                    ['Итерации', historyDetail.iterations],
                    ['Сходимость', historyDetail.convergence_metric?.toFixed(6)],
                    ['Время', `${historyDetail.elapsed_seconds?.toFixed(1)} сек.`],
                    ['IP комбо', historyDetail.ip_combos],
                    ['OOP комбо', historyDetail.oop_combos],
                    ...(historyDetail.metadata?.difficulty_grade ? [['Сложность', {
                      trivial: 'Тривиальная', light: 'Лёгкая', moderate: 'Средняя',
                      heavy: 'Тяжёлая', extreme: 'Экстремальная'
                    }[historyDetail.metadata.difficulty_grade] || historyDetail.metadata.difficulty_grade]] : []),
                    ...(historyDetail.metadata?.stop_reason ? [['Остановка', {
                      converged: '✅ Сходимость', plateau: '📊 Плато',
                      max_iterations: '🔢 Лимит итераций', cancelled: '⚠️ Отменён'
                    }[historyDetail.metadata.stop_reason] || historyDetail.metadata.stop_reason]] : []),
                    ...(historyDetail.metadata?.solve_quality?.quality_label_ru
                      ? [['Качество', historyDetail.metadata.solve_quality.quality_label_ru]] : []),
                  ].map(([l, v]) => (
                    <div key={l as string} className="flex justify-between pr-4">
                      <span className="text-muted-foreground">{l}</span>
                      <span className="text-foreground font-mono">{v}</span>
                    </div>
                  ))}
                </div>
              )}
              <button
                onClick={() => {
                  // Load this solve into active state
                  setJobId(selectedHistoryId);
                  setResult(historyDetail as any);
                  setProgress({ status: 'done', iteration: historyDetail.iterations, total_iterations: historyDetail.iterations } as any);
                  setActiveTab('result');
                  // Try to load root strategy
                  apiFetch(`/node/${selectedHistoryId}/node_0`).then(ns => setNodeStrategy(ns)).catch(() => {});
                }}
                className="text-xs text-primary hover:underline"
              >
                → Открыть результат
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Solver;
