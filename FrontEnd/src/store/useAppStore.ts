import { create } from 'zustand';

// ── Study Session Steps ──
export const STUDY_STEPS = [
  { id: 1, key: 'review', label: 'Разбор', emoji: '📋', route: null },
  { id: 2, key: 'drill', label: 'Тренировка', emoji: '🎯', route: '/drill' },
  { id: 3, key: 'explore', label: 'Изучение', emoji: '📊', route: '/explore' },
  { id: 4, key: 'practice', label: 'Практика', emoji: '🎮', route: '/play' },
] as const;

export interface StudyContext {
  source: 'play' | 'solver' | null;
  solveId: string | null;
  board: string[];
  boardDisplay: string;
  spotLabel: string;
  coachingNote: string;
  // Session progression
  currentStep: number; // 1-4
  completedSteps: number[];
  drillsInSession: number;
  drillsCorrectInSession: number;
  // Solver coaching fields (from Phase 8E)
  mainIdea?: string;
  keyTakeaway?: string;
  strictness?: 'strict' | 'flexible' | 'hand_dependent';
  strictnessLabel?: string;
  rootStrategy?: Record<string, number>;
}

const EMPTY_STUDY_CONTEXT: StudyContext = {
  source: null,
  solveId: null,
  board: [],
  boardDisplay: '',
  spotLabel: '',
  coachingNote: '',
  currentStep: 0,
  completedSteps: [],
  drillsInSession: 0,
  drillsCorrectInSession: 0,
};

interface AppState {
  selectedSpotId: string | null;
  selectedNodeId: string | null;
  showMatrix: boolean;
  showHotkeyModal: boolean;
  drillCount: number;
  studyContext: StudyContext;
  // Legacy alias for compatibility
  solverContext: StudyContext;
  setSelectedSpot: (id: string | null) => void;
  setSelectedNode: (id: string | null) => void;
  toggleMatrix: () => void;
  toggleHotkeyModal: () => void;
  incrementDrill: () => void;
  setStudyContext: (ctx: StudyContext) => void;
  clearStudyContext: () => void;
  // Session actions
  advanceStep: (step: number) => void;
  markStepComplete: (step: number) => void;
  recordDrillResult: (correct: boolean) => void;
  // Legacy aliases
  setSolverContext: (ctx: StudyContext) => void;
  clearSolverContext: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedSpotId: null,
  selectedNodeId: null,
  showMatrix: true,
  showHotkeyModal: false,
  drillCount: 0,
  studyContext: { ...EMPTY_STUDY_CONTEXT },
  get solverContext() {
    // @ts-ignore — legacy alias reads from studyContext
    return this.studyContext;
  },
  setSelectedSpot: (id) => set({ selectedSpotId: id }),
  setSelectedNode: (id) => set({ selectedNodeId: id }),
  toggleMatrix: () => set((s) => ({ showMatrix: !s.showMatrix })),
  toggleHotkeyModal: () => set((s) => ({ showHotkeyModal: !s.showHotkeyModal })),
  incrementDrill: () => set((s) => ({ drillCount: s.drillCount + 1 })),
  setStudyContext: (ctx) => set({ studyContext: ctx, solverContext: ctx }),
  clearStudyContext: () => set({
    studyContext: { ...EMPTY_STUDY_CONTEXT },
    solverContext: { ...EMPTY_STUDY_CONTEXT },
  }),
  // Session actions
  advanceStep: (step) => set((s) => ({
    studyContext: { ...s.studyContext, currentStep: step },
    solverContext: { ...s.studyContext, currentStep: step },
  })),
  markStepComplete: (step) => set((s) => {
    const completed = s.studyContext.completedSteps.includes(step)
      ? s.studyContext.completedSteps
      : [...s.studyContext.completedSteps, step];
    const ctx = { ...s.studyContext, completedSteps: completed };
    return { studyContext: ctx, solverContext: ctx };
  }),
  recordDrillResult: (correct) => set((s) => {
    const ctx = {
      ...s.studyContext,
      drillsInSession: s.studyContext.drillsInSession + 1,
      drillsCorrectInSession: s.studyContext.drillsCorrectInSession + (correct ? 1 : 0),
    };
    return { studyContext: ctx, solverContext: ctx };
  }),
  // Legacy aliases — write to both fields
  setSolverContext: (ctx) => set({ studyContext: ctx, solverContext: ctx }),
  clearSolverContext: () => set({
    studyContext: { ...EMPTY_STUDY_CONTEXT },
    solverContext: { ...EMPTY_STUDY_CONTEXT },
  }),
}));
