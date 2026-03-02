import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useAppStore } from '@/store/useAppStore';
import { cn } from '@/lib/utils';
import { Search, Target, GitBranch, Cpu, Filter, Plus, Trash2, X } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';

const FORMATS = [
  { value: 'SRP', label: 'SRP' },
  { value: '3bet', label: '3-Bet' },
  { value: '4bet', label: '4-Bet' },
  { value: 'squeeze', label: 'Squeeze' },
];

const POSITIONS = ['UTG', 'HJ', 'MP', 'CO', 'BTN', 'SB', 'BB'];
const STREETS = [
  { value: 'flop', label: 'Flop' },
  { value: 'turn', label: 'Turn' },
  { value: 'river', label: 'River' },
];

function CreateSpotDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [format, setFormat] = useState('SRP');
  const [posIP, setPosIP] = useState('BTN');
  const [posOOP, setPosOOP] = useState('BB');
  const [street, setStreet] = useState('flop');
  const [stack, setStack] = useState(100);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (posIP === posOOP) {
      toast.error('Позиции IP и OOP должны быть разными');
      return;
    }
    setLoading(true);
    try {
      const spot = await api.createSpot({
        format,
        positions: [posIP, posOOP],
        street,
        stack,
      });
      toast.success('Спот создан', { description: spot.name });

      // Auto-solve the new spot
      await api.createJob(spot.id);
      toast.info('Задача добавлена в очередь');

      onCreated();
      onClose();
    } catch (e: any) {
      toast.error(e.message || 'Ошибка создания спота');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-2xl w-full max-w-md p-6 space-y-5 shadow-2xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-foreground">Создать спот</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-secondary transition-colors">
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Format */}
          <div>
            <label className="text-xs text-muted-foreground uppercase tracking-wider mb-1.5 block">Формат</label>
            <div className="flex gap-2">
              {FORMATS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setFormat(f.value)}
                  className={cn(
                    'flex-1 px-3 py-2 rounded-xl text-xs font-medium transition-colors border',
                    format === f.value
                      ? 'bg-primary/10 border-primary text-primary'
                      : 'bg-secondary border-border text-muted-foreground hover:text-foreground'
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Positions */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-1.5 block">IP позиция</label>
              <Select value={posIP} onValueChange={setPosIP}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {POSITIONS.map((p) => (
                    <SelectItem key={p} value={p}>{p}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-1.5 block">OOP позиция</label>
              <Select value={posOOP} onValueChange={setPosOOP}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {POSITIONS.map((p) => (
                    <SelectItem key={p} value={p}>{p}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Street */}
          <div>
            <label className="text-xs text-muted-foreground uppercase tracking-wider mb-1.5 block">Улица</label>
            <div className="flex gap-2">
              {STREETS.map((s) => (
                <button
                  key={s.value}
                  onClick={() => setStreet(s.value)}
                  className={cn(
                    'flex-1 px-3 py-2 rounded-xl text-xs font-medium transition-colors border',
                    street === s.value
                      ? 'bg-primary/10 border-primary text-primary'
                      : 'bg-secondary border-border text-muted-foreground hover:text-foreground'
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Stack */}
          <div>
            <label className="text-xs text-muted-foreground uppercase tracking-wider mb-1.5 block">
              Стек (bb)
            </label>
            <input
              type="number"
              value={stack}
              onChange={(e) => setStack(Math.max(10, Math.min(500, Number(e.target.value))))}
              className="w-full bg-secondary border border-border rounded-xl px-4 py-2.5 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring"
              min={10}
              max={500}
            />
          </div>
        </div>

        {/* Preview */}
        <div className="bg-secondary/50 rounded-xl p-3 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Предпросмотр:</span>{' '}
          {format === 'squeeze' ? 'Squeeze' : format === '3bet' ? '3Bet' : format === '4bet' ? '4Bet' : 'SRP'}{' '}
          {posIP} vs {posOOP} {street.charAt(0).toUpperCase() + street.slice(1)} • {stack}bb
        </div>

        <button
          onClick={handleSubmit}
          disabled={loading || posIP === posOOP}
          className={cn(
            'w-full px-4 py-2.5 rounded-xl text-sm font-medium transition-colors',
            loading || posIP === posOOP
              ? 'bg-secondary text-muted-foreground cursor-not-allowed'
              : 'bg-primary text-primary-foreground hover:bg-primary/90'
          )}
        >
          {loading ? 'Создание...' : 'Создать и рассчитать'}
        </button>
      </div>
    </div>
  );
}

const Library = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setSelectedSpot = useAppStore((s) => s.setSelectedSpot);

  const [search, setSearch] = useState('');
  const [formatFilter, setFormatFilter] = useState<string>('all');
  const [solvedFilter, setSolvedFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  const { data: spots, isLoading } = useQuery({
    queryKey: ['spots'],
    queryFn: api.getSpots,
  });

  const filtered = useMemo(() => {
    if (!spots) return [];
    return spots.filter((spot) => {
      if (search && !spot.name.toLowerCase().includes(search.toLowerCase()))
        return false;
      if (formatFilter !== 'all' && spot.format !== formatFilter) return false;
      if (solvedFilter === 'solved' && !spot.solved) return false;
      if (solvedFilter === 'unsolved' && spot.solved) return false;
      if (typeFilter === 'custom' && !spot.isCustom) return false;
      if (typeFilter === 'base' && spot.isCustom) return false;
      return true;
    });
  }, [spots, search, formatFilter, solvedFilter, typeFilter]);

  const handleDrill = (spotId: string) => {
    setSelectedSpot(spotId);
    navigate('/drill');
  };

  const handleExplore = (spotId: string) => {
    setSelectedSpot(spotId);
    navigate('/explore');
  };

  const handleSolve = (spotId: string) => {
    api.createJob(spotId).then(() => {
      toast.success('Задача добавлена в очередь');
    });
  };

  const handleDelete = async (spotId: string, spotName: string) => {
    if (!confirm(`Удалить спот "${spotName}"?`)) return;
    try {
      await api.deleteSpot(spotId);
      toast.success('Спот удалён');
      queryClient.invalidateQueries({ queryKey: ['spots'] });
    } catch (e: any) {
      toast.error(e.message || 'Ошибка удаления');
    }
  };

  return (
    <div className="p-6 lg:p-10 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Библиотека спотов
        </h1>
        <button
          onClick={() => setShowCreateDialog(true)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" /> Создать спот
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск спотов..."
            className="w-full bg-card border border-border rounded-xl pl-9 pr-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <Select value={formatFilter} onValueChange={setFormatFilter}>
          <SelectTrigger className="w-36">
            <Filter className="w-3.5 h-3.5 mr-1.5" />
            <SelectValue placeholder="Формат" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все</SelectItem>
            <SelectItem value="SRP">SRP</SelectItem>
            <SelectItem value="3bet">3-Bet</SelectItem>
            <SelectItem value="4bet">4-Bet</SelectItem>
            <SelectItem value="squeeze">Squeeze</SelectItem>
          </SelectContent>
        </Select>
        <Select value={solvedFilter} onValueChange={setSolvedFilter}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Статус" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все</SelectItem>
            <SelectItem value="solved">Solved</SelectItem>
            <SelectItem value="unsolved">Unsolved</SelectItem>
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Тип" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все</SelectItem>
            <SelectItem value="base">Base</SelectItem>
            <SelectItem value="custom">Custom</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Spots grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="bg-card border border-border rounded-2xl p-5 h-36 animate-pulse"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {filtered.map((spot) => (
            <div
              key={spot.id}
              className="bg-card border border-border rounded-2xl p-5 space-y-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-medium text-foreground">{spot.name}</h3>
                  <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                    <span className="text-xs bg-secondary px-2 py-0.5 rounded-md text-secondary-foreground">
                      {spot.format}
                    </span>
                    <span className="text-xs bg-secondary px-2 py-0.5 rounded-md text-secondary-foreground">
                      {spot.positions.join(' vs ')}
                    </span>
                    <span className="text-xs bg-secondary px-2 py-0.5 rounded-md text-secondary-foreground">
                      {spot.stack}bb
                    </span>
                    {spot.solved ? (
                      <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-md">
                        Solved
                      </span>
                    ) : (
                      <span className="text-xs bg-accent/10 text-accent px-2 py-0.5 rounded-md">
                        Unsolved
                      </span>
                    )}
                    {spot.isCustom && (
                      <span className="text-xs bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded-md">
                        Custom
                      </span>
                    )}
                  </div>
                </div>
                <span className="text-xs text-muted-foreground">
                  {spot.nodeCount} узлов
                </span>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={() => handleDrill(spot.id)}
                  disabled={!spot.solved}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                    spot.solved
                      ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                      : 'bg-secondary text-muted-foreground cursor-not-allowed'
                  )}
                >
                  <Target className="w-3.5 h-3.5" /> Drill
                </button>
                <button
                  onClick={() => handleExplore(spot.id)}
                  disabled={!spot.solved}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                    spot.solved
                      ? 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                      : 'bg-secondary text-muted-foreground cursor-not-allowed'
                  )}
                >
                  <GitBranch className="w-3.5 h-3.5" /> Explore
                </button>
                {!spot.solved && (
                  <button
                    onClick={() => handleSolve(spot.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
                  >
                    <Cpu className="w-3.5 h-3.5" /> Solve
                  </button>
                )}
                {spot.isCustom && (
                  <button
                    onClick={() => handleDelete(spot.id, spot.name)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-action-fold hover:bg-action-fold/10 transition-colors ml-auto"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="col-span-full text-center text-muted-foreground py-12">
              Споты не найдены
            </div>
          )}
        </div>
      )}

      {showCreateDialog && (
        <CreateSpotDialog
          onClose={() => setShowCreateDialog(false)}
          onCreated={() => queryClient.invalidateQueries({ queryKey: ['spots'] })}
        />
      )}
    </div>
  );
};

export default Library;
