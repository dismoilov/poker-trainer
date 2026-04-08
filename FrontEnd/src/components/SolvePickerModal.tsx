import { useState, useEffect } from 'react';
import { useAuthStore } from '@/store/useAuthStore';
import { cn } from '@/lib/utils';
import { Shield, X, Check, Clock, Database, Beaker } from 'lucide-react';

interface SolveEntry {
  id: string;
  board?: string[];
  ip_range?: string;
  oop_range?: string;
  trust_grade?: string;
  exploitability_mbb?: number;
  iterations?: number;
  converged?: boolean;
  elapsed_seconds?: number;
  status: string;
}

interface SolvePickerModalProps {
  open: boolean;
  onClose: () => void;
  onSelect: (solveId: string, solve: SolveEntry) => void;
  title?: string;
}

const TRUST_COLORS: Record<string, string> = {
  VALIDATED_LIMITED_SCOPE: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-400',
  INTERNAL_DEMO: 'bg-amber-500/15 border-amber-500/40 text-amber-400',
  UNTRUSTED: 'bg-red-500/15 border-red-500/40 text-red-400',
};

export function SolvePickerModal({ open, onClose, onSelect, title = 'Select a Solve' }: SolvePickerModalProps) {
  const [solves, setSolves] = useState<SolveEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    const token = useAuthStore.getState().token;
    fetch('/api/solver/history', {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    })
      .then((r) => r.json())
      .then((data) => {
        setSolves(data.filter((s: SolveEntry) => s.status === 'done'));
      })
      .catch(() => setSolves([]))
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold text-foreground">{title}</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-secondary transition-colors">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4 space-y-2">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!loading && solves.length === 0 && (
            <div className="text-center py-8 text-muted-foreground text-sm">
              <Beaker className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No completed solves found.</p>
              <p className="text-xs mt-1">Run a solve in the Solver page first.</p>
            </div>
          )}

          {solves.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelect(s.id, s)}
              className="w-full text-left bg-secondary/50 hover:bg-secondary border border-border rounded-xl p-3 transition-colors group"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-mono text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                  {s.board?.join(' ') || 'Unknown board'}
                </span>
                <div className="flex items-center gap-1.5">
                  {s.trust_grade && (
                    <span className={cn(
                      'text-[9px] px-1.5 py-0.5 rounded border font-medium',
                      TRUST_COLORS[s.trust_grade] || 'bg-gray-500/15 border-gray-500/40 text-gray-400',
                    )}>
                      <Shield className="w-3 h-3 inline mr-0.5" />
                      {s.trust_grade.replace(/_/g, ' ')}
                    </span>
                  )}
                  {s.converged && <Check className="w-3.5 h-3.5 text-emerald-400" />}
                </div>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                <span>IP: {s.ip_range || '—'}</span>
                <span>OOP: {s.oop_range || '—'}</span>
                {s.iterations && <span>{s.iterations} iter</span>}
                {s.exploitability_mbb != null && (
                  <span className="text-blue-400">{s.exploitability_mbb.toFixed(1)} mbb</span>
                )}
                {s.elapsed_seconds != null && (
                  <span className="flex items-center gap-0.5">
                    <Clock className="w-3 h-3" />
                    {s.elapsed_seconds.toFixed(0)}s
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-border text-[10px] text-muted-foreground">
          Showing {solves.length} completed solve{solves.length !== 1 ? 's' : ''} • Solver scope: flop-only, HU postflop
        </div>
      </div>
    </div>
  );
}
