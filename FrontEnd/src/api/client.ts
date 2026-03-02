import type {
  Spot,
  SpotCreateRequest,
  DrillQuestion,
  DrillFeedback,
  TreeNode,
  Job,
  AnalyticsSummary,
  AnalyticsRow,
  AnalyticsQuestion,
  StrategyMatrix,
  GameDetail,
  HandDetail,
} from '@/types';
import { useAuthStore } from '@/store/useAuthStore';

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const token = useAuthStore.getState().token;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...options,
  });

  if (res.status === 401) {
    useAuthStore.getState().logout();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  // Auth
  login: async (username: string, password: string) => {
    const res = await fetch(`${BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Login failed');
    }
    return res.json() as Promise<{ accessToken: string; user: { id: number; username: string } }>;
  },

  getSpots: async (): Promise<Spot[]> => {
    return fetchApi('/api/spots');
  },

  getSpot: async (id: string): Promise<Spot | undefined> => {
    return fetchApi(`/api/spots/${id}`);
  },

  getDrillQuestion: async (
    spotId: string,
    nodeId?: string
  ): Promise<DrillQuestion> => {
    return fetchApi('/api/drill/next', {
      method: 'POST',
      body: JSON.stringify({ spotId, nodeId }),
    });
  },

  submitDrillAnswer: async (
    nodeId: string,
    hand: string,
    actionId: string,
    questionId?: string
  ): Promise<DrillFeedback> => {
    return fetchApi('/api/drill/answer', {
      method: 'POST',
      body: JSON.stringify({ nodeId, hand, actionId, questionId }),
    });
  },

  getNode: async (_spotId: string, nodeId: string): Promise<TreeNode> => {
    return fetchApi(`/api/explore/node?spotId=${_spotId}&nodeId=${nodeId}`);
  },

  getNodeChildren: async (spotId: string): Promise<TreeNode[]> => {
    return fetchApi(`/api/explore/nodes?spotId=${spotId}`);
  },

  getStrategy: async (nodeId: string): Promise<StrategyMatrix> => {
    return fetchApi(`/api/explore/strategy?nodeId=${nodeId}`);
  },

  createJob: async (spotId: string): Promise<Job> => {
    return fetchApi('/api/jobs/solve', {
      method: 'POST',
      body: JSON.stringify({ spotId }),
    });
  },

  getJobs: async (): Promise<Job[]> => {
    return fetchApi('/api/jobs');
  },

  createSpot: async (req: SpotCreateRequest): Promise<Spot> => {
    return fetchApi('/api/spots', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  deleteSpot: async (spotId: string): Promise<void> => {
    return fetchApi(`/api/spots/${spotId}`, {
      method: 'DELETE',
    });
  },

  getAnalyticsSummary: async (): Promise<AnalyticsSummary> => {
    return fetchApi('/api/analytics/summary');
  },

  getAnalyticsHistory: async (): Promise<AnalyticsRow[]> => {
    return fetchApi('/api/analytics/history');
  },

  getRecentQuestions: async (): Promise<AnalyticsQuestion[]> => {
    return fetchApi('/api/analytics/recent');
  },

  getGameDetail: async (gameId: string): Promise<GameDetail> => {
    return fetchApi(`/api/analytics/game/${gameId}`);
  },

  getHandDetail: async (nodeId: string, hand: string): Promise<HandDetail> => {
    return fetchApi(`/api/explore/hand-detail?nodeId=${encodeURIComponent(nodeId)}&hand=${encodeURIComponent(hand)}`);
  },
};
