import { expect, test, type Page, type Route } from '@playwright/test';
import { fileURLToPath } from 'node:url';

type ExperimentRecord = {
  id: number;
  name: string;
  created_at: string;
  num_ratings_per_question: number;
  prolific_completion_url: string | null;
  prolific_study_id: string | null;
  prolific_study_status: string | null;
  prolific_study_url: string | null;
  question_count: number;
  rating_count: number;
};

type UploadRecord = {
  id: number;
  filename: string;
  uploaded_at: string;
  question_count: number;
};

type StudyRoundRecord = {
  id: number;
  round_number: number;
  is_pilot: boolean;
  prolific_study_id: string;
  prolific_study_status: 'UNPUBLISHED' | 'ACTIVE' | 'COMPLETED';
  places_requested: number;
  created_at: string;
  prolific_study_url: string;
};

type RecommendationRecord = {
  avg_time_per_question_seconds: number;
  remaining_rating_actions: number;
  total_hours_remaining: number;
  recommended_places: number;
  is_complete: boolean;
};

function buildExperiment(state: MockState, partial: Partial<ExperimentRecord> = {}): ExperimentRecord {
  return {
    id: state.nextExperimentId++,
    name: 'Smoke Test Experiment',
    created_at: '2026-03-09T00:00:00Z',
    num_ratings_per_question: 3,
    prolific_completion_url: null,
    prolific_study_id: null,
    prolific_study_status: null,
    prolific_study_url: null,
    question_count: 0,
    rating_count: 0,
    ...partial,
  };
}

type MockState = {
  experiments: ExperimentRecord[];
  uploads: Record<number, UploadRecord[]>;
  rounds: Record<number, StudyRoundRecord[]>;
  recommendations: Record<number, RecommendationRecord>;
  statsRequests: string[];
  previewStartRequests: string[];
  nextExperimentId: number;
  nextUploadId: number;
  nextRoundId: number;
};

function createMockState(): MockState {
  return {
    experiments: [],
    uploads: {},
    rounds: {},
    recommendations: {},
    statsRequests: [],
    previewStartRequests: [],
    nextExperimentId: 1,
    nextUploadId: 1,
    nextRoundId: 1,
  };
}

function extractExperimentId(url: URL): number {
  const match = url.pathname.match(/\/experiments\/(\d+)\//);
  if (!match) {
    throw new Error(`Missing experiment id in path: ${url.pathname}`);
  }
  return Number(match[1]);
}

function buildRound(state: MockState, experimentId: number, round: Partial<StudyRoundRecord>): StudyRoundRecord {
  return {
    id: state.nextRoundId++,
    round_number: 0,
    is_pilot: false,
    prolific_study_id: `study-${state.nextRoundId}`,
    prolific_study_status: 'UNPUBLISHED',
    places_requested: 0,
    created_at: '2026-03-09T00:00:00Z',
    prolific_study_url: 'https://app.prolific.com/studies/mock',
    ...round,
  };
}

async function fulfillJson(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApiMocks(
  page: Page,
  state: MockState,
  options: { prolificMode?: 'disabled' | 'real' | 'fake' } = {}
) {
  const prolificMode = options.prolificMode ?? 'fake';

  await page.context().route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname, search } = url;
    const method = request.method();

    if (pathname === '/api/v1/intercom/tokens/') {
      await route.fulfill({ status: 204, body: '' });
      return;
    }

    if (pathname === '/api/admin/auth/logout') {
      await fulfillJson(route, 200, { ok: true });
      return;
    }

    if (pathname === '/api/admin/platform-status') {
      await fulfillJson(route, 200, {
        prolific_enabled: prolificMode !== 'disabled',
        prolific_mode: prolificMode,
      });
      return;
    }

    if (pathname.startsWith('/api/admin/prolific/fake-studies/') && method === 'GET') {
      const studyId = pathname.split('/').at(-1) ?? '';
      const matchingRound = Object.values(state.rounds)
        .flat()
        .find((round) => round.prolific_study_id === studyId);
      const experiment = matchingRound
        ? state.experiments.find((item) =>
            state.rounds[item.id]?.some((round) => round.prolific_study_id === matchingRound.prolific_study_id)
          )
        : undefined;
      if (!matchingRound || !experiment) {
        await fulfillJson(route, 404, { detail: 'Fake study not found' });
        return;
      }

      await fulfillJson(route, 200, {
        study_id: matchingRound.prolific_study_id,
        study_status: matchingRound.prolific_study_status,
        experiment_id: experiment.id,
        experiment_name: experiment.name,
        round_number: matchingRound.round_number,
        is_pilot: matchingRound.is_pilot,
        places_requested: matchingRound.places_requested,
        description: 'Pilot description for smoke coverage',
        estimated_completion_time: 60,
        reward: 900,
        device_compatibility: ['desktop'],
        external_study_url: `${url.origin}/rate?experiment_id=${experiment.id}&PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}`,
        completion_url: 'https://app.prolific.com/submissions/complete?cc=TEST1234',
        created_at: matchingRound.created_at,
      });
      return;
    }

    if (pathname === '/api/admin/experiments' && method === 'GET') {
      await fulfillJson(route, 200, state.experiments);
      return;
    }

    if (pathname === '/api/admin/experiments' && method === 'POST') {
      const payload = request.postDataJSON() as { name: string; num_ratings_per_question: number };
      const experiment = buildExperiment(state, {
        name: payload.name,
        num_ratings_per_question: payload.num_ratings_per_question,
      });
      state.experiments = [experiment];
      state.uploads[experiment.id] = [];
      state.rounds[experiment.id] = [];
      state.recommendations[experiment.id] = {
        avg_time_per_question_seconds: 0,
        remaining_rating_actions: 0,
        total_hours_remaining: 0,
        recommended_places: 0,
        is_complete: false,
      };
      await fulfillJson(route, 200, experiment);
      return;
    }

    if (pathname.endsWith('/upload') && method === 'POST') {
      const experimentId = extractExperimentId(url);
      const upload = {
        id: state.nextUploadId++,
        filename: 'sample_questions.csv',
        uploaded_at: '2026-03-09T00:01:00Z',
        question_count: 2,
      };
      state.uploads[experimentId] = [upload];
      const experiment = state.experiments.find((item) => item.id === experimentId);
      if (experiment) {
        experiment.question_count = 2;
      }
      await fulfillJson(route, 200, { message: 'Uploaded 2 questions' });
      return;
    }

    if (pathname.endsWith('/uploads') && method === 'GET') {
      const experimentId = extractExperimentId(url);
      await fulfillJson(route, 200, state.uploads[experimentId] || []);
      return;
    }

    if (pathname.endsWith('/stats') && method === 'GET') {
      const experimentId = extractExperimentId(url);
      state.statsRequests.push(search);
      const experiment = state.experiments.find((item) => item.id === experimentId);
      await fulfillJson(route, 200, {
        experiment_name: experiment?.name ?? 'Unknown',
        total_questions: experiment?.question_count ?? 0,
        questions_complete: 0,
        total_ratings: 0,
        total_raters: 0,
        target_ratings_per_question: experiment?.num_ratings_per_question ?? 3,
      });
      return;
    }

    if (pathname.endsWith('/analytics') && method === 'GET') {
      await fulfillJson(route, 200, {
        experiment_name: 'Smoke Test Experiment',
        overview: {
          total_ratings: 0,
          total_questions: 2,
          total_raters: 0,
          avg_response_time_seconds: 0,
          avg_confidence: 0,
        },
        questions: [],
        raters: [],
      });
      return;
    }

    if (pathname.endsWith('/prolific/recommend') && method === 'GET') {
      const experimentId = extractExperimentId(url);
      await fulfillJson(route, 200, state.recommendations[experimentId]);
      return;
    }

    if (pathname.endsWith('/prolific/rounds') && method === 'GET') {
      const experimentId = extractExperimentId(url);
      await fulfillJson(route, 200, state.rounds[experimentId] || []);
      return;
    }

    if (pathname.endsWith('/prolific/pilot') && method === 'POST') {
      const experimentId = extractExperimentId(url);
      const payload = request.postDataJSON() as {
        description: string;
        estimated_completion_time: number;
        reward: number;
        pilot_hours: number;
      };
      const pilot = buildRound(state, experimentId, {
        round_number: 0,
        is_pilot: true,
        prolific_study_id: 'study-pilot-1',
        prolific_study_status: 'UNPUBLISHED',
        places_requested: payload.pilot_hours,
        prolific_study_url: `${url.origin}/admin/prolific/fake-studies/study-pilot-1`,
      });
      state.rounds[experimentId] = [pilot];
      state.recommendations[experimentId] = {
        avg_time_per_question_seconds: 42,
        remaining_rating_actions: 320,
        total_hours_remaining: 3.7,
        recommended_places: 4,
        is_complete: false,
      };
      const experiment = state.experiments.find((item) => item.id === experimentId);
      if (experiment) {
        experiment.prolific_study_id = pilot.prolific_study_id;
        experiment.prolific_study_status = pilot.prolific_study_status;
        experiment.prolific_study_url = pilot.prolific_study_url;
        experiment.prolific_completion_url = 'https://app.prolific.com/submissions/complete?cc=TEST1234';
      }
      await fulfillJson(route, 200, pilot);
      return;
    }

    if (pathname.endsWith('/prolific/publish') && method === 'POST') {
      const experimentId = extractExperimentId(url);
      const rounds = state.rounds[experimentId] || [];
      const current = rounds.find((round) => round.prolific_study_id === state.experiments[0]?.prolific_study_id);
      if (current) {
        current.prolific_study_status = 'ACTIVE';
      }
      const experiment = state.experiments.find((item) => item.id === experimentId);
      if (experiment) {
        experiment.prolific_study_status = 'ACTIVE';
      }
      await fulfillJson(route, 200, { message: 'Study published on Prolific', status: 'ACTIVE' });
      return;
    }

    if (pathname.endsWith('/prolific/rounds') && method === 'POST') {
      const experimentId = extractExperimentId(url);
      const payload = request.postDataJSON() as { places: number };
      const nextRoundNumber = (state.rounds[experimentId] || []).filter((round) => !round.is_pilot).length + 1;
      const round = buildRound(state, experimentId, {
        round_number: nextRoundNumber,
        is_pilot: false,
        prolific_study_id: `study-round-${nextRoundNumber}`,
        prolific_study_status: 'UNPUBLISHED',
        places_requested: payload.places,
        prolific_study_url: `${url.origin}/admin/prolific/fake-studies/study-round-${nextRoundNumber}`,
      });
      state.rounds[experimentId] = [...(state.rounds[experimentId] || []), round];
      const experiment = state.experiments.find((item) => item.id === experimentId);
      if (experiment) {
        experiment.prolific_study_id = round.prolific_study_id;
        experiment.prolific_study_status = round.prolific_study_status;
        experiment.prolific_study_url = round.prolific_study_url;
      }
      await fulfillJson(route, 200, round);
      return;
    }

    if (pathname === '/api/raters/start' && method === 'POST') {
      state.previewStartRequests.push(search);
      await fulfillJson(route, 200, {
        rater_id: 101,
        session_start: '2026-03-09T00:02:00Z',
        session_end_time: '2099-03-09T01:02:00Z',
        experiment_name: 'Smoke Test Experiment',
        completion_url: 'https://app.prolific.com/submissions/complete?cc=TEST1234',
      });
      return;
    }

    if (pathname === '/api/raters/next-question' && method === 'GET') {
      await fulfillJson(route, 200, {
        id: 500,
        question_id: 'q-1',
        question_text: 'Is this workflow ready for release?',
        options: 'Yes|No',
        question_type: 'MC',
      });
      return;
    }

    if (pathname === '/api/raters/submit' && method === 'POST') {
      await fulfillJson(route, 200, { id: 1, success: true });
      return;
    }

    if (pathname === '/api/raters/session-status' && method === 'GET') {
      await fulfillJson(route, 200, {
        is_active: true,
        time_remaining_seconds: 3600,
        questions_completed: 0,
      });
      return;
    }

    if (pathname === '/api/raters/end-session' && method === 'POST') {
      await fulfillJson(route, 200, { message: 'ok' });
      return;
    }

    throw new Error(`Unhandled API request: ${method} ${pathname}`);
  });
}

test.beforeEach(async ({ page }) => {
  page.on('dialog', (dialog) => dialog.accept());
});

test('create experiment, upload CSV, run pilot, and launch a round', async ({ page }) => {
  const state = createMockState();
  await installApiMocks(page, state);

  await page.goto('/admin');

  await page.getByTestId('experiment-name-input').fill('Hour Breakdown Smoke Test');
  await page.getByTestId('ratings-per-question-input').fill('3');
  await page.getByRole('button', { name: 'Create Experiment' }).click();

  await expect(page.getByRole('heading', { name: 'Hour Breakdown Smoke Test' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Prolific Study Rounds' })).toBeVisible();
  await expect(page.getByTestId('prolific-mode-badge')).toHaveText('Fake Mode');
  await expect(page.getByTestId('prolific-mode-notice')).toContainText('Fake Prolific mode is enabled');
  await expect(page.getByTestId('run-pilot-button')).toBeVisible();

  const csvPath = fileURLToPath(new URL('../../sample_questions.csv', import.meta.url));
  await page.getByTestId('upload-csv-input').setInputFiles(csvPath);
  await page.getByTestId('upload-csv-button').click();

  await expect(page.getByText('sample_questions.csv')).toBeVisible();
  await expect(page.getByText('2 questions', { exact: true })).toBeVisible();
  await expect(page.getByText('Uploaded 2 questions')).toBeVisible();

  await page.getByTestId('pilot-description-input').fill('Pilot description for smoke coverage');
  await page.getByTestId('pilot-estimated-completion-time-input').fill('60');
  await page.getByTestId('pilot-reward-input').fill('900');
  await page.getByTestId('pilot-hours-input').fill('5');
  await page.getByTestId('run-pilot-button').click();

  await expect(page.getByText('Pilot Study', { exact: true })).toBeVisible();
  await expect(page.getByTestId('publish-round-0')).toBeVisible();
  await expect(page.getByTestId('recommendation-panel')).toContainText('Recommendation for next round');
  await expect(page.getByTestId('recommendation-panel')).toContainText('42s');
  await expect(page.getByText('Completion URL')).toBeVisible();
  await expect(page.getByTestId('completion-url-input')).toHaveValue(
    'https://app.prolific.com/submissions/complete?cc=TEST1234'
  );

  const fakeStudyPromise = page.context().waitForEvent('page');
  await page.getByRole('button', { name: 'Open Local Draft' }).click();
  const fakeStudyPage = await fakeStudyPromise;
  await fakeStudyPage.waitForLoadState('networkidle');
  await expect(fakeStudyPage.getByTestId('fake-study-detail-page')).toBeVisible();
  await expect(fakeStudyPage.getByText('Fake Study Review')).toBeVisible();
  await expect(fakeStudyPage.getByText('Pilot description for smoke coverage')).toBeVisible();
  await expect(fakeStudyPage.getByText('UNPUBLISHED')).toBeVisible();

  await page.getByTestId('publish-round-0').click();
  await expect(page.getByText('ACTIVE')).toBeVisible();

  await page.getByTestId('launch-round-button').click();
  await expect(page.getByText('Round 1')).toBeVisible();
  await expect(page.getByText('4 places', { exact: true })).toBeVisible();

  const exportLink = page.getByTestId('export-link');
  await expect(exportLink).toHaveAttribute('href', /\/api\/admin\/experiments\/1\/export$/);
  await page.getByTestId('include-preview-toggle').click();
  await expect(exportLink).toHaveAttribute('href', /include_preview=true/);
  await expect.poll(() => state.statsRequests.some((query) => query.includes('include_preview=true'))).toBeTruthy();
});

test('preview participant link opens /rate with preview mode and starts one preview session', async ({ page, context }) => {
  const state = createMockState();
  state.experiments = [
    buildExperiment(state, {
      id: 1,
      name: 'Preview Experiment',
      question_count: 2,
      prolific_completion_url: 'https://app.prolific.com/submissions/complete?cc=TEST1234',
    }),
  ];
  state.nextExperimentId = 2;
  state.uploads[1] = [
    {
      id: 1,
      filename: 'sample_questions.csv',
      uploaded_at: '2026-03-09T00:00:00Z',
      question_count: 2,
    },
  ];
  state.rounds[1] = [];
  state.recommendations[1] = {
    avg_time_per_question_seconds: 0,
    remaining_rating_actions: 0,
    total_hours_remaining: 0,
    recommended_places: 0,
    is_complete: false,
  };

  await installApiMocks(page, state);
  await page.goto('/admin/experiments/1');

  const popupPromise = context.waitForEvent('page');
  await page.getByTestId('preview-participant-button').click();
  const popup = await popupPromise;
  await popup.waitForLoadState('networkidle');

  await expect(popup).toHaveURL(/preview=true/);
  await expect(popup.getByText('Preview mode')).toBeVisible();
  await expect(popup.getByText('Smoke Test Experiment')).toBeVisible();
  await expect(popup.getByText('Is this workflow ready for release?')).toBeVisible();
  await expect.poll(() => state.previewStartRequests.length).toBe(1);
  await expect(state.previewStartRequests[0]).toContain('preview=true');
});

test('disabled mode explains why pilot controls are unavailable', async ({ page }) => {
  const state = createMockState();
  state.experiments = [
    buildExperiment(state, {
      id: 1,
      name: 'Disabled Prolific Experiment',
      question_count: 2,
    }),
  ];
  state.nextExperimentId = 2;
  state.uploads[1] = [];
  state.rounds[1] = [];
  state.recommendations[1] = {
    avg_time_per_question_seconds: 0,
    remaining_rating_actions: 0,
    total_hours_remaining: 0,
    recommended_places: 0,
    is_complete: false,
  };

  await installApiMocks(page, state, { prolificMode: 'disabled' });
  await page.goto('/admin/experiments/1');

  await expect(page.getByTestId('prolific-mode-badge')).toHaveText('Disabled');
  await expect(page.getByTestId('prolific-mode-notice')).toContainText('Prolific is disabled for this environment');
  await expect(page.getByTestId('prolific-mode-notice')).toContainText('PROLIFIC__MODE=fake');
  await expect(page.getByTestId('preview-participant-button')).toBeVisible();
  await expect(page.getByTestId('run-pilot-button')).toHaveCount(0);
});
