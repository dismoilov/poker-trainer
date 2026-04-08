/**
 * TypeScript types for the live poker game session API.
 */

export interface LegalAction {
  type: 'fold' | 'check' | 'call' | 'bet' | 'raise' | 'allin';
  amount: number;
  label: string;
}

export interface ActionEntry {
  player: 'IP' | 'OOP';
  type: string;
  amount: number;
  street: string;
}

export interface SessionState {
  sessionId: string;
  status: 'active' | 'waiting_action' | 'showdown' | 'hand_complete' | 'completed';
  handsPlayed: number;
  heroStack: number;
  villainStack: number;
  pot: number;
  board: string[];
  heroHand: string[];
  villainHand: string[];
  street: string;
  currentPlayer: 'IP' | 'OOP';
  legalActions: LegalAction[];
  actionHistory: ActionEntry[];
  lastResult?: string;
  winningSummary?: string;
}

export interface CreateSessionRequest {
  startingStack: number;
  heroPosition: 'IP' | 'OOP';
}

export interface TakeActionRequest {
  sessionId: string;
  actionType: string;
  amount: number;
}

export interface HandRecord {
  id: string;
  handNumber: number;
  board: string[];
  heroHand: string[];
  villainHand: string[];
  pot: number;
  heroWon: number;
  villainWon: number;
  result: string;
  actions: ActionEntry[];
}
