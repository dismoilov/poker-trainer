import { create } from 'zustand';

interface AppState {
  selectedSpotId: string | null;
  selectedNodeId: string | null;
  showMatrix: boolean;
  showHotkeyModal: boolean;
  drillCount: number;
  setSelectedSpot: (id: string | null) => void;
  setSelectedNode: (id: string | null) => void;
  toggleMatrix: () => void;
  toggleHotkeyModal: () => void;
  incrementDrill: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedSpotId: null,
  selectedNodeId: null,
  showMatrix: true,
  showHotkeyModal: false,
  drillCount: 0,
  setSelectedSpot: (id) => set({ selectedSpotId: id }),
  setSelectedNode: (id) => set({ selectedNodeId: id }),
  toggleMatrix: () => set((s) => ({ showMatrix: !s.showMatrix })),
  toggleHotkeyModal: () => set((s) => ({ showHotkeyModal: !s.showHotkeyModal })),
  incrementDrill: () => set((s) => ({ drillCount: s.drillCount + 1 })),
}));
