import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useAppStore } from '@/store/useAppStore';
import { HandMatrix } from '@/components/HandMatrix';
import { SpotSelector } from '@/components/SpotSelector';
import { formatPercent } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { ChevronRight, ChevronDown, GitBranch, X, Layers, BarChart3 } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import type { TreeNode, HandDetail } from '@/types';

const ACTION_COLORS: Record<string, string> = {
  fold: 'text-action-fold',
  check: 'text-action-check',
  call: 'text-action-call',
  bet33: 'text-action-bet',
  bet50: 'text-action-bet',
  bet75: 'text-action-raise',
  bet150: 'text-action-raise',
  raise: 'text-action-raise',
};

const ACTION_BG: Record<string, string> = {
  fold: 'bg-action-fold/10 border-action-fold/20',
  check: 'bg-action-check/10 border-action-check/20',
  call: 'bg-action-call/10 border-action-call/20',
  bet33: 'bg-action-bet/10 border-action-bet/20',
  bet50: 'bg-action-bet/10 border-action-bet/20',
  bet75: 'bg-action-raise/10 border-action-raise/20',
  bet150: 'bg-action-raise/10 border-action-raise/20',
  raise: 'bg-action-raise/10 border-action-raise/20',
};

const ACTION_LABELS: Record<string, string> = {
  fold: 'Fold', check: 'Check', call: 'Call',
  bet33: 'Bet 33%', bet50: 'Bet 50%', bet75: 'Bet 75%',
  bet150: 'Bet 150%', raise: 'Raise',
};

const CONNECTION_LABELS: Record<string, string> = {
  set: '🎯 Сет',
  two_pair: '✌️ Две пары',
  overpair: '👑 Оверпара',
  top_pair: '🃏 Топ-пара',
  middle_pair: '📋 Средняя пара',
  bottom_pair: '📉 Нижняя пара',
  pair: '🔹 Пара',
  underpair: '⬇️ Андерпара',
  draw: '🎨 Дро',
  nothing: '❌ Нет попадания',
};

const TIER_COLORS: Record<number, string> = {
  1: 'text-yellow-400',
  2: 'text-orange-400',
  3: 'text-green-400',
  4: 'text-blue-400',
  5: 'text-cyan-400',
  6: 'text-purple-400',
  7: 'text-gray-400',
  8: 'text-gray-600',
};


function TreeNodeItem({
  node,
  allNodes,
  selectedNodeId,
  onSelect,
  depth = 0,
}: {
  node: TreeNode;
  allNodes: TreeNode[];
  selectedNodeId: string | null;
  onSelect: (id: string) => void;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const children = allNodes.filter((n) => n.parentId === node.id);
  const hasChildren = children.length > 0;
  const isSelected = selectedNodeId === node.id;

  return (
    <div>
      <button
        onClick={() => {
          onSelect(node.id);
          if (hasChildren) setExpanded(!expanded);
        }}
        className={cn(
          'w-full text-left flex items-center gap-1.5 py-1.5 px-2 rounded-lg text-sm transition-colors',
          isSelected
            ? 'bg-primary/10 text-primary'
            : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
        )}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren ? (
          expanded ? (
            <ChevronDown className="w-3.5 h-3.5 shrink-0" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 shrink-0" />
          )
        ) : (
          <span className="w-3.5" />
        )}
        <span className="truncate">{node.actionLabel || node.id}</span>
        <span className="text-[10px] text-muted-foreground ml-auto shrink-0">
          {node.player}
        </span>
      </button>
      {expanded &&
        children.map((child) => (
          <TreeNodeItem
            key={child.id}
            node={child}
            allNodes={allNodes}
            selectedNodeId={selectedNodeId}
            onSelect={onSelect}
            depth={depth + 1}
          />
        ))}
    </div>
  );
}

function HandDetailPanel({
  nodeId,
  hand,
  onClose,
}: {
  nodeId: string;
  hand: string;
  onClose: () => void;
}) {
  const { data: detail, isLoading } = useQuery({
    queryKey: ['hand-detail', nodeId, hand],
    queryFn: () => api.getHandDetail(nodeId, hand),
    enabled: !!nodeId && !!hand,
  });

  if (isLoading) {
    return (
      <div className="bg-card border border-border rounded-2xl p-5 animate-pulse">
        <div className="h-4 bg-secondary rounded w-1/3 mb-3" />
        <div className="h-3 bg-secondary rounded w-2/3 mb-2" />
        <div className="h-3 bg-secondary rounded w-1/2" />
      </div>
    );
  }

  if (!detail) return null;

  const sortedFreqs = Object.entries(detail.frequencies).sort(
    ([, a], [, b]) => b - a
  );
  const maxFreq = sortedFreqs.length > 0 ? sortedFreqs[0][1] : 0;

  return (
    <div className="bg-card border border-border rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="text-2xl font-mono font-black text-foreground">
            {detail.hand}
          </div>
          <div>
            <div className={cn('text-xs font-bold', TIER_COLORS[detail.tier] || 'text-foreground')}>
              Tier {detail.tier}
            </div>
            <div className="text-[10px] text-muted-foreground">
              {detail.tierLabel}
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-secondary transition-colors"
        >
          <X className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>

      {/* Connection */}
      <div className="px-4 pt-3 pb-2">
        <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
          Связь с бордом
        </div>
        <div className="text-sm text-foreground font-medium">
          {CONNECTION_LABELS[detail.connection] || detail.connection}
        </div>
      </div>

      {/* Frequencies — bar chart style */}
      <div className="px-4 py-3">
        <div className="flex items-center gap-1.5 mb-2">
          <BarChart3 className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
            GTO Частоты
          </span>
        </div>
        <div className="space-y-1.5">
          {sortedFreqs.map(([action, freq]) => (
            <div key={action} className="group">
              <div className="flex items-center justify-between text-xs mb-0.5">
                <span className={cn('font-bold', ACTION_COLORS[action] || 'text-foreground')}>
                  {ACTION_LABELS[action] || action}
                </span>
                <span className="font-mono text-foreground font-bold">
                  {formatPercent(freq)}
                </span>
              </div>
              <div className="w-full h-2.5 bg-secondary/50 rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-500',
                    action.startsWith('bet') || action === 'raise'
                      ? 'bg-gradient-to-r from-orange-500 to-red-500'
                      : action === 'call'
                        ? 'bg-gradient-to-r from-green-500 to-emerald-500'
                        : action === 'check'
                          ? 'bg-gradient-to-r from-blue-500 to-cyan-500'
                          : 'bg-gradient-to-r from-gray-500 to-gray-400'
                  )}
                  style={{ width: `${(freq / Math.max(maxFreq, 0.01)) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Explanations */}
      <div className="px-4 py-3 border-t border-border">
        <div className="flex items-center gap-1.5 mb-2">
          <Layers className="w-3.5 h-3.5 text-muted-foreground" />
          <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
            Анализ
          </span>
        </div>
        <div className="space-y-1.5">
          {detail.explanation.map((line, i) => (
            <div
              key={i}
              className="text-xs text-foreground/80 bg-secondary/30 rounded-lg p-2.5 border border-border/50"
            >
              <span className="text-primary font-bold mr-1">{i + 1}.</span>
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const Explore = () => {
  const selectedSpotId = useAppStore((s) => s.selectedSpotId);
  const setSelectedSpot = useAppStore((s) => s.setSelectedSpot);
  const spotId = selectedSpotId || 'srp-btn-bb-flop';
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [selectedHand, setSelectedHand] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>(() => {
    try {
      return JSON.parse(localStorage.getItem('pt-notes') || '{}');
    } catch {
      return {};
    }
  });

  const { data: nodes } = useQuery({
    queryKey: ['nodes', spotId],
    queryFn: () => api.getNodeChildren(spotId),
  });

  // Auto-select first root node when nodes load
  const rootNodes = nodes?.filter((n) => !n.parentId) || [];
  if (nodes && !selectedNodeId && rootNodes.length > 0) {
    setSelectedNodeId(rootNodes[0].id);
  }

  const { data: currentNode } = useQuery({
    queryKey: ['node', spotId, selectedNodeId],
    queryFn: () => api.getNode(spotId, selectedNodeId!),
    enabled: !!selectedNodeId,
  });

  const { data: strategy } = useQuery({
    queryKey: ['strategy', selectedNodeId],
    queryFn: () => api.getStrategy(selectedNodeId!),
    enabled: !!selectedNodeId,
  });

  const { data: spot } = useQuery({
    queryKey: ['spot', spotId],
    queryFn: () => api.getSpot(spotId),
  });

  const handleSpotChange = (newSpotId: string) => {
    setSelectedSpot(newSpotId);
    setSelectedNodeId(null);
    setSelectedAction(null);
    setSelectedHand(null);
  };

  const handleSolve = () => {
    api.createJob(spotId).then(() => {
      toast.success('Задача добавлена в очередь', {
        description: spot?.name || spotId,
      });
    });
  };

  const saveNote = (text: string) => {
    const key = `${spotId}:${selectedNodeId}`;
    const updated = { ...notes, [key]: text };
    setNotes(updated);
    localStorage.setItem('pt-notes', JSON.stringify(updated));
  };

  const noteKey = `${spotId}:${selectedNodeId}`;

  const handleHandClick = (hand: string) => {
    setSelectedHand(selectedHand === hand ? null : hand);
  };

  return (
    <div className="flex h-full">
      {/* Left: Spot selector + Tree */}
      <div className="w-64 border-r border-border p-3 overflow-auto shrink-0 scrollbar-thin">
        {/* Spot Selector */}
        <SpotSelector
          selectedSpotId={spotId}
          onSelect={handleSpotChange}
          className="mb-3"
        />

        <div className="flex items-center gap-2 mb-3">
          <GitBranch className="w-4 h-4 text-primary" />
          <span className="text-xs font-medium text-foreground truncate">
            Дерево решений
          </span>
        </div>
        <div className="space-y-0.5">
          {rootNodes.map((node) => (
            <TreeNodeItem
              key={node.id}
              node={node}
              allNodes={nodes || []}
              selectedNodeId={selectedNodeId}
              onSelect={(id) => {
                setSelectedNodeId(id);
                setSelectedHand(null);
              }}
            />
          ))}
        </div>
        <button
          onClick={handleSolve}
          className="w-full mt-6 px-3 py-2 bg-secondary hover:bg-secondary/80 text-secondary-foreground rounded-xl text-xs transition-colors"
        >
          Посчитать этот спот
        </button>
      </div>

      {/* Right: Content */}
      <div className="flex-1 p-4 lg:p-6 overflow-auto">
        {currentNode && (
          <div className="mb-4">
            <div className="text-xs text-muted-foreground mb-1">
              {currentNode.lineDescription}
            </div>
            <div className="flex items-center gap-2 text-sm">
              <span className="bg-secondary px-2 py-0.5 rounded-lg text-secondary-foreground">
                {currentNode.player}
              </span>
              <span className="text-muted-foreground">
                Pot: {currentNode.pot}bb
              </span>
              <span className="text-muted-foreground capitalize">
                {currentNode.street}
              </span>
            </div>
          </div>
        )}

        <Tabs defaultValue="strategy" className="space-y-4">
          <TabsList className="bg-secondary">
            <TabsTrigger value="strategy">Strategy</TabsTrigger>
            <TabsTrigger value="breakdown">Breakdown</TabsTrigger>
            <TabsTrigger value="notes">Заметки</TabsTrigger>
          </TabsList>

          <TabsContent value="strategy" className="space-y-4">
            <div className="flex gap-4">
              {/* Matrix */}
              <div className="shrink-0">
                <HandMatrix
                  strategy={strategy}
                  highlightHand={selectedHand || undefined}
                  selectedAction={selectedAction || undefined}
                  onHandClick={handleHandClick}
                />
                {/* Action filters */}
                {currentNode && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    <button
                      onClick={() => setSelectedAction(null)}
                      className={cn(
                        'text-xs px-2.5 py-1 rounded-md border transition-colors',
                        !selectedAction
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border text-muted-foreground'
                      )}
                    >
                      All
                    </button>
                    {currentNode.actions.map((action) => (
                      <button
                        key={action.id}
                        onClick={() =>
                          setSelectedAction(
                            selectedAction === action.id ? null : action.id
                          )
                        }
                        className={cn(
                          'text-xs px-2.5 py-1 rounded-md border transition-colors',
                          selectedAction === action.id
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border text-muted-foreground'
                        )}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                )}
                <p className="text-[10px] text-muted-foreground mt-2">
                  Нажмите на ячейку для детального анализа руки
                </p>
              </div>

              {/* Hand Detail Panel */}
              {selectedHand && selectedNodeId && (
                <div className="flex-1 min-w-[280px] max-w-md">
                  <HandDetailPanel
                    nodeId={selectedNodeId}
                    hand={selectedHand}
                    onClose={() => setSelectedHand(null)}
                  />
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="breakdown">
            <div className="bg-card border border-border rounded-2xl p-5 space-y-4">
              <h3 className="font-medium text-foreground">
                Классификация рейнджа
              </h3>
              {strategy && currentNode && (() => {
                // Classify hands by dominant action
                const actionGroups: Record<string, string[]> = {};
                for (const [hand, freqs] of Object.entries(strategy)) {
                  let maxFreq = 0;
                  let maxAction = '';
                  for (const [action, freq] of Object.entries(freqs)) {
                    if (freq > maxFreq) {
                      maxFreq = freq;
                      maxAction = action;
                    }
                  }
                  if (!actionGroups[maxAction]) actionGroups[maxAction] = [];
                  actionGroups[maxAction].push(hand);
                }

                return Object.entries(actionGroups)
                  .sort(([, a], [, b]) => b.length - a.length)
                  .map(([action, hands]) => (
                    <div key={action}>
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className={cn('text-xs font-bold', ACTION_COLORS[action])}>
                          {ACTION_LABELS[action] || action}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          ({hands.length} комбо, {formatPercent(hands.length / 169)})
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {hands.slice(0, 30).map((h) => (
                          <button
                            key={h}
                            onClick={() => {
                              setSelectedHand(h);
                              // switch to strategy tab to see detail
                            }}
                            className={cn(
                              'text-[10px] px-1.5 py-0.5 rounded border font-mono cursor-pointer',
                              ACTION_BG[action] || 'bg-secondary border-border',
                              'hover:opacity-80 transition-opacity'
                            )}
                          >
                            {h}
                          </button>
                        ))}
                        {hands.length > 30 && (
                          <span className="text-[10px] text-muted-foreground px-1.5 py-0.5">
                            +{hands.length - 30} ещё
                          </span>
                        )}
                      </div>
                    </div>
                  ));
              })()}
              {!strategy && (
                <p className="text-sm text-muted-foreground">
                  Выберите ноду для просмотра классификации
                </p>
              )}
            </div>
          </TabsContent>

          <TabsContent value="notes">
            <div className="bg-card border border-border rounded-2xl p-4">
              <textarea
                className="w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground resize-none outline-none min-h-[120px]"
                placeholder="Ваши заметки к этому узлу..."
                value={notes[noteKey] || ''}
                onChange={(e) => saveNote(e.target.value)}
              />
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default Explore;
