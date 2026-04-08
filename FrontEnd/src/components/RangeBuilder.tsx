/**
 * RangeBuilder — Phase 8D
 *
 * Interactive 13×13 range grid selector with presets and quick actions.
 * Primary UX for range selection, replacing manual text input.
 */

import { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
  RANKS,
  RangeGrid,
  emptyGrid,
  handLabel,
  handType,
  rangeToGrid,
  gridToRange,
  countSelected,
  countCombos,
  PRESETS,
  PresetKey,
  selectAllPairs,
  selectAll,
  selectBroadways,
  selectSuitedConnectors,
} from '@/lib/rangeUtils';
import { ChevronDown, ChevronUp, Eraser, Grid3X3, Layers, Sparkles } from 'lucide-react';

interface RangeBuilderProps {
  value: string;
  onChange: (range: string) => void;
  label: string;
  hint?: string;
}

const CELL_COLORS = {
  pair: {
    on: 'bg-amber-500/80 text-white border-amber-400/60',
    off: 'bg-amber-500/10 text-amber-200/60 border-amber-500/20',
  },
  suited: {
    on: 'bg-emerald-500/80 text-white border-emerald-400/60',
    off: 'bg-emerald-500/10 text-emerald-200/60 border-emerald-500/20',
  },
  offsuit: {
    on: 'bg-sky-500/80 text-white border-sky-400/60',
    off: 'bg-sky-500/10 text-sky-200/60 border-sky-500/20',
  },
};

export const RangeBuilder = ({ value, onChange, label, hint }: RangeBuilderProps) => {
  const [grid, setGrid] = useState<RangeGrid>(() => rangeToGrid(value));
  const [showText, setShowText] = useState(false);
  const [textValue, setTextValue] = useState(value);
  const [isDragging, setIsDragging] = useState(false);
  const [dragMode, setDragMode] = useState<boolean>(true); // true = selecting, false = deselecting

  // Sync grid → text when grid changes
  useEffect(() => {
    const range = gridToRange(grid);
    setTextValue(range);
    onChange(range);
  }, [grid]);

  // Sync external value → grid
  useEffect(() => {
    if (value !== gridToRange(grid)) {
      setGrid(rangeToGrid(value));
      setTextValue(value);
    }
  }, [value]);

  const toggleCell = useCallback((r: number, c: number) => {
    setGrid(prev => {
      const next = prev.map(row => [...row]);
      next[r][c] = !next[r][c];
      return next;
    });
  }, []);

  const setCellValue = useCallback((r: number, c: number, val: boolean) => {
    setGrid(prev => {
      if (prev[r][c] === val) return prev;
      const next = prev.map(row => [...row]);
      next[r][c] = val;
      return next;
    });
  }, []);

  const handleMouseDown = (r: number, c: number) => {
    setIsDragging(true);
    const newVal = !grid[r][c];
    setDragMode(newVal);
    setCellValue(r, c, newVal);
  };

  const handleMouseEnter = (r: number, c: number) => {
    if (isDragging) {
      setCellValue(r, c, dragMode);
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const applyPreset = (key: PresetKey) => {
    const preset = PRESETS[key];
    setGrid(rangeToGrid(preset.hands));
  };

  const applyTextInput = () => {
    setGrid(rangeToGrid(textValue));
  };

  const selected = countSelected(grid);
  const combos = countCombos(grid);

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-medium text-foreground">{label}</div>
          {hint && <div className="text-[10px] text-muted-foreground">{hint}</div>}
        </div>
        <div className="text-[10px] text-muted-foreground">
          {selected} рук • {combos} комбо
        </div>
      </div>

      {/* Presets */}
      <div className="flex gap-1.5 flex-wrap">
        {(Object.keys(PRESETS) as PresetKey[]).map(key => (
          <button
            key={key}
            onClick={() => applyPreset(key)}
            className="px-2.5 py-1 text-[10px] bg-secondary/80 hover:bg-secondary border border-border rounded-lg text-muted-foreground hover:text-foreground transition-colors"
            title={PRESETS[key].desc}
          >
            {PRESETS[key].label}
          </button>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="flex gap-1 flex-wrap">
        {[
          { label: 'Очистить', icon: Eraser, action: () => setGrid(emptyGrid()) },
          { label: 'Все', icon: Grid3X3, action: () => setGrid(selectAll()) },
          { label: 'Пары', icon: Layers, action: () => setGrid(selectAllPairs()) },
          { label: 'Бродвей', icon: Sparkles, action: () => setGrid(selectBroadways()) },
          { label: 'Коннекторы', icon: Sparkles, action: () => setGrid(selectSuitedConnectors()) },
        ].map(qa => (
          <button
            key={qa.label}
            onClick={qa.action}
            className="flex items-center gap-1 px-2 py-0.5 text-[9px] bg-secondary/50 hover:bg-secondary border border-border/50 rounded text-muted-foreground hover:text-foreground transition-colors"
          >
            <qa.icon className="w-2.5 h-2.5" />
            {qa.label}
          </button>
        ))}
      </div>

      {/* 13×13 Grid */}
      <div
        className="select-none"
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <div className="grid gap-[1px]" style={{ gridTemplateColumns: 'repeat(13, 1fr)' }}>
          {Array.from({ length: 13 }).map((_, r) =>
            Array.from({ length: 13 }).map((_, c) => {
              const type = handType(r, c);
              const isOn = grid[r][c];
              const colors = CELL_COLORS[type][isOn ? 'on' : 'off'];

              return (
                <button
                  key={`${r}-${c}`}
                  onMouseDown={(e) => { e.preventDefault(); handleMouseDown(r, c); }}
                  onMouseEnter={() => handleMouseEnter(r, c)}
                  className={cn(
                    'aspect-square flex items-center justify-center text-[8px] sm:text-[9px] font-medium rounded-[3px] border transition-colors cursor-pointer',
                    colors,
                  )}
                  title={handLabel(r, c)}
                >
                  {handLabel(r, c)}
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 text-[9px] text-muted-foreground">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-[2px] bg-amber-500/60" />
          Пары
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-[2px] bg-emerald-500/60" />
          Одномастные
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-[2px] bg-sky-500/60" />
          Разномастные
        </div>
      </div>

      {/* Collapsible text input */}
      <div>
        <button
          onClick={() => setShowText(!showText)}
          className="flex items-center gap-1 text-[10px] text-muted-foreground/70 hover:text-muted-foreground transition-colors"
        >
          {showText ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          Текстовый ввод
        </button>
        {showText && (
          <div className="mt-1 flex gap-1">
            <input
              value={textValue}
              onChange={e => setTextValue(e.target.value)}
              onBlur={applyTextInput}
              onKeyDown={e => e.key === 'Enter' && applyTextInput()}
              className="flex-1 bg-secondary border border-border rounded-lg px-2 py-1 text-[10px] text-foreground font-mono focus:border-primary outline-none"
              placeholder="AA,KK,AKs,AQs..."
            />
            <button
              onClick={applyTextInput}
              className="px-2 py-1 bg-primary/20 text-primary text-[10px] rounded-lg hover:bg-primary/30 transition-colors"
            >
              ОК
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default RangeBuilder;
