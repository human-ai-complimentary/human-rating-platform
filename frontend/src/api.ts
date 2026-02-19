import type { Experiment, ExperimentCreate, ExperimentStats, Question, Session, RatingSubmit, Analytics, Upload } from './types';

// Use environment variable for API URL, fallback to relative path for same-origin deployment
const API_BASE = (import.meta.env.VITE_API_URL || '') + '/api';

export const api = {
  // Admin endpoints
  async createExperiment(data: ExperimentCreate): Promise<Experiment> {
    const res = await fetch(`${API_BASE}/admin/experiments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async listExperiments(): Promise<Experiment[]> {
    const res = await fetch(`${API_BASE}/admin/experiments`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async uploadQuestions(experimentId: number, file: File): Promise<{ message: string }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/admin/experiments/${experimentId}/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getExperimentStats(experimentId: number): Promise<ExperimentStats> {
    const res = await fetch(`${API_BASE}/admin/experiments/${experimentId}/stats`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  getExportUrl(experimentId: number): string {
    return `${API_BASE}/admin/experiments/${experimentId}/export`;
  },

  async getExperimentAnalytics(experimentId: number): Promise<Analytics> {
    const res = await fetch(`${API_BASE}/admin/experiments/${experimentId}/analytics`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async listUploads(experimentId: number): Promise<Upload[]> {
    const res = await fetch(`${API_BASE}/admin/experiments/${experimentId}/uploads`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async deleteExperiment(experimentId: number): Promise<{ message: string }> {
    const res = await fetch(`${API_BASE}/admin/experiments/${experimentId}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Rater endpoints
  async startSession(experimentId: string, prolificId: string, studyId: string | null, sessionId: string | null): Promise<Session> {
    let url = `${API_BASE}/raters/start?experiment_id=${experimentId}&PROLIFIC_PID=${encodeURIComponent(prolificId)}`;
    if (studyId) url += `&STUDY_ID=${encodeURIComponent(studyId)}`;
    if (sessionId) url += `&SESSION_ID=${encodeURIComponent(sessionId)}`;
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getNextQuestion(raterId: number): Promise<Question | null> {
    const res = await fetch(`${API_BASE}/raters/next-question?rater_id=${raterId}`);
    if (res.status === 403) throw new Error('Session expired');
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async submitRating(raterId: number, data: RatingSubmit): Promise<{ id: number; success: boolean }> {
    const res = await fetch(`${API_BASE}/raters/submit?rater_id=${raterId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getSessionStatus(raterId: number): Promise<{ is_active: boolean; time_remaining_seconds: number; questions_completed: number }> {
    const res = await fetch(`${API_BASE}/raters/session-status?rater_id=${raterId}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async endSession(raterId: number): Promise<{ message: string }> {
    const res = await fetch(`${API_BASE}/raters/end-session?rater_id=${raterId}`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
