import type {
  Analytics,
  Experiment,
  ExperimentCreate,
  ExperimentStats,
  Question,
  RatingSubmit,
  Session,
  Upload,
} from './types';

function resolveApiBase(): string {
  const host = (import.meta.env.VITE_API_HOST || '').trim().replace(/\/+$/, '');
  const rawPrefix = (import.meta.env.VITE_API_PREFIX ?? '').trim();
  const cleanedPrefix = rawPrefix.replace(/^\/+|\/+$/g, '');
  const prefix = cleanedPrefix ? `/${cleanedPrefix}` : '';
  return `${host}${prefix}`;
}

const API_BASE = resolveApiBase();

function buildUrl(path: string): string {
  return `${API_BASE}${path}`;
}

function looksLikeHtml(payload: string): boolean {
  const normalized = payload.trim().toLowerCase();
  return normalized.startsWith('<!doctype html') || normalized.startsWith('<html');
}

function buildRoutingHint(url: string): string {
  return (
    `Expected JSON from ${url}, but received HTML. ` +
    'This usually means API routing is misconfigured. ' +
    'Check VITE_API_HOST and VITE_API_PREFIX.'
  );
}

async function readText(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    return '';
  }
}

async function throwHttpError(response: Response, url: string): Promise<never> {
  const body = await readText(response);
  if (body && looksLikeHtml(body)) {
    throw new Error(buildRoutingHint(url));
  }

  const message = body.trim() || `${response.status} ${response.statusText}`;
  throw new Error(`Request failed (${response.status}) for ${url}: ${message}`);
}

async function parseJson<T>(response: Response, url: string): Promise<T> {
  const contentType = (response.headers.get('content-type') || '').toLowerCase();
  if (!contentType.includes('application/json')) {
    const body = await readText(response);
    if (looksLikeHtml(body)) {
      throw new Error(buildRoutingHint(url));
    }
    throw new Error(
      `Expected JSON from ${url}, but received content-type '${contentType || 'unknown'}'.`
    );
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new Error(
      `Invalid JSON returned from ${url}. Check API routing and response format.`
    );
  }
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = buildUrl(path);
  const response = await fetch(url, init);

  if (!response.ok) {
    await throwHttpError(response, url);
  }

  return parseJson<T>(response, url);
}

export const api = {
  // Admin endpoints
  async createExperiment(data: ExperimentCreate): Promise<Experiment> {
    return fetchJson<Experiment>('/admin/experiments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  async listExperiments(): Promise<Experiment[]> {
    return fetchJson<Experiment[]>('/admin/experiments');
  },

  async uploadQuestions(experimentId: number, file: File): Promise<{ message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    return fetchJson<{ message: string }>(`/admin/experiments/${experimentId}/upload`, {
      method: 'POST',
      body: formData,
    });
  },

  async getExperimentStats(experimentId: number): Promise<ExperimentStats> {
    return fetchJson<ExperimentStats>(`/admin/experiments/${experimentId}/stats`);
  },

  getExportUrl(experimentId: number): string {
    return buildUrl(`/admin/experiments/${experimentId}/export`);
  },

  async getExperimentAnalytics(experimentId: number): Promise<Analytics> {
    return fetchJson<Analytics>(`/admin/experiments/${experimentId}/analytics`);
  },

  async listUploads(experimentId: number): Promise<Upload[]> {
    return fetchJson<Upload[]>(`/admin/experiments/${experimentId}/uploads`);
  },

  async deleteExperiment(experimentId: number): Promise<{ message: string }> {
    return fetchJson<{ message: string }>(`/admin/experiments/${experimentId}`, {
      method: 'DELETE',
    });
  },

  // Rater endpoints
  async startSession(
    experimentId: string,
    prolificId: string,
    studyId: string | null,
    sessionId: string | null
  ): Promise<Session> {
    let url = `/raters/start?experiment_id=${experimentId}&PROLIFIC_PID=${encodeURIComponent(prolificId)}`;
    if (studyId) {
      url += `&STUDY_ID=${encodeURIComponent(studyId)}`;
    }
    if (sessionId) {
      url += `&SESSION_ID=${encodeURIComponent(sessionId)}`;
    }

    return fetchJson<Session>(url, { method: 'POST' });
  },

  async getNextQuestion(raterId: number): Promise<Question | null> {
    const path = `/raters/next-question?rater_id=${raterId}`;
    const url = buildUrl(path);
    const response = await fetch(url);

    if (response.status === 403) {
      throw new Error('Session expired');
    }

    if (!response.ok) {
      await throwHttpError(response, url);
    }

    return parseJson<Question | null>(response, url);
  },

  async submitRating(raterId: number, data: RatingSubmit): Promise<{ id: number; success: boolean }> {
    return fetchJson<{ id: number; success: boolean }>(`/raters/submit?rater_id=${raterId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  },

  async getSessionStatus(
    raterId: number
  ): Promise<{ is_active: boolean; time_remaining_seconds: number; questions_completed: number }> {
    return fetchJson<{ is_active: boolean; time_remaining_seconds: number; questions_completed: number }>(
      `/raters/session-status?rater_id=${raterId}`
    );
  },

  async endSession(raterId: number): Promise<{ message: string }> {
    return fetchJson<{ message: string }>(`/raters/end-session?rater_id=${raterId}`, {
      method: 'POST',
    });
  },
};
