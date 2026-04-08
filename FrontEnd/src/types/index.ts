export interface Spot {
  id: string;
  name: string;
  format: 'SRP' | '3bet' | '4bet' | 'squeeze';
  positions: [string, string];
  stack: number;
  rakeProfile: string;
  streets: string[];
  tags: string[];
  solved: boolean;
  nodeCount: number;
  isCustom?: boolean;
}

export interface SpotCreateRequest {
  format: string;
  positions: string[];
  street: string;
  stack: number;
}

export interface SpotConfig {
  stack: number;
  rakeProfile: string;
  sizings: {
    flop: number[];
    turn: number[];
    river: number[];
  };
}

export interface Action {
  id: string;
  label: string;
  type: 'fold' | 'check' | 'call' | 'bet' | 'raise';
  size?: number;
}

export interface TreeNode {
  id: string;
  spotId: string;
  street: 'preflop' | 'flop' | 'turn' | 'river';
  pot: number;
  player: string;
  actions: Action[];
  parentId?: string;
  lineDescription: string;
  children: string[];
  actionLabel?: string;
}

export interface DrillQuestion {
  questionId?: string;
  spotId: string;
  nodeId: string;
  board: string[];
  hand: string;
  handCards: [string, string];
  position: string;
  potSize: number;
  stackSize: number;
  actions: Action[];
  lineDescription: string;
  street: string;
}

export interface DrillAnswer {
  nodeId: string;
  hand: string;
  actionId: string;
  questionId?: string;
}

export interface DrillFeedback {
  frequencies: Record<string, number>;
  chosenAction: string;
  correctAction: string;
  evLoss: number;
  accuracy: number;
  explanation: string[];
}

export type StrategyMatrix = Record<string, Record<string, number>>;
export type EvMatrix = Record<string, number>;

export interface Job {
  id: string;
  type: 'solve' | 'import';
  spotId?: string;
  spotName?: string;
  status: 'pending' | 'running' | 'done' | 'failed';
  progress: number;
  createdAt: string;
  log: string[];
}

export interface AnalyticsSummary {
  totalSessions: number;
  totalQuestions: number;
  avgEvLoss: number;
  accuracy: number;
}

export interface AnalyticsRow {
  date: string;
  evLoss: number;
  accuracy: number;
  questions: number;
}

export interface AnalyticsQuestion {
  id: string;
  spotName: string;
  spotId: string;
  nodeId: string;
  board: string[];
  hand: string;
  position: string;
  chosenAction: string;
  correctAction: string;
  evLoss: number;
  accuracy: number;
  lineDescription: string;
  date: string;
}

export interface GameDetail {
  id: string;
  spotName: string;
  spotId: string;
  nodeId: string;
  board: string[];
  hand: string;
  position: string;
  chosenAction: string;
  correctAction: string;
  evLoss: number;
  accuracy: number;
  lineDescription: string;
  date: string;
  frequencies: Record<string, number>;
  explanation: string[];
}

export interface HandDetail {
  hand: string;
  tier: number;
  tierLabel: string;
  frequencies: Record<string, number>;
  connection: string;
  explanation: string[];
  recommendation_summary?: string;
  node_context?: { node_explanation: string; spot_context: string };
  data_source_label?: string;
}

export interface HotkeyConfig {
  [action: string]: string;
}
