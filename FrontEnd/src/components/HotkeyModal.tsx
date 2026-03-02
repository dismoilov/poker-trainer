import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useAppStore } from '@/store/useAppStore';

const HOTKEYS = [
  { key: '1–4', description: 'Выбрать действие по номеру' },
  { key: 'Space / Enter', description: 'Следующий вопрос' },
  { key: 'H', description: 'Показать/скрыть матрицу рук' },
  { key: '?', description: 'Справка по горячим клавишам' },
];

export function HotkeyModal() {
  const show = useAppStore((s) => s.showHotkeyModal);
  const toggle = useAppStore((s) => s.toggleHotkeyModal);

  return (
    <Dialog open={show} onOpenChange={toggle}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Горячие клавиши</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-2">
          {HOTKEYS.map((h) => (
            <div key={h.key} className="flex items-center justify-between gap-4">
              <span className="text-sm text-muted-foreground">
                {h.description}
              </span>
              <kbd className="px-2.5 py-1 bg-secondary rounded-md text-xs font-mono text-secondary-foreground shrink-0">
                {h.key}
              </kbd>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
