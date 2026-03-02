import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SettingsState {
  stack: number;
  rakeProfile: 'low' | 'high';
  sizings: { flop: number[]; turn: number[]; river: number[] };
  theme: 'dark' | 'light';
  compact: boolean;
  showHints: boolean;
  language: 'ru' | 'en';
  hotkeys: Record<string, string>;
  setStack: (v: number) => void;
  setRakeProfile: (v: 'low' | 'high') => void;
  setTheme: (v: 'dark' | 'light') => void;
  setCompact: (v: boolean) => void;
  setShowHints: (v: boolean) => void;
  setLanguage: (v: 'ru' | 'en') => void;
  setHotkey: (action: string, key: string) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      stack: 100,
      rakeProfile: 'low',
      sizings: {
        flop: [33, 75],
        turn: [50, 75, 125],
        river: [50, 75, 150],
      },
      theme: 'dark',
      compact: false,
      showHints: true,
      language: 'ru',
      hotkeys: {
        action1: '1',
        action2: '2',
        action3: '3',
        action4: '4',
        next: 'Space',
        toggleMatrix: 'h',
        help: '?',
      },
      setStack: (v) => set({ stack: v }),
      setRakeProfile: (v) => set({ rakeProfile: v }),
      setTheme: (v) => {
        document.documentElement.classList.toggle('dark', v === 'dark');
        set({ theme: v });
      },
      setCompact: (v) => set({ compact: v }),
      setShowHints: (v) => set({ showHints: v }),
      setLanguage: (v) => set({ language: v }),
      setHotkey: (action, key) =>
        set((s) => ({ hotkeys: { ...s.hotkeys, [action]: key } })),
    }),
    { name: 'pt-settings' }
  )
);
