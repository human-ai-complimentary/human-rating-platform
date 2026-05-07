# Analytics Roadmap

This document defines the staged approach to analytics — what we capture per rating, how researchers see it, and how data quality is enforced.

---

# What we have today (v0)

### Capture

- Per-rating (`Rating`): `answer`, `confidence` (1–5), `time_started`, `time_submitted`, `assistance_session_id`
- Per-rater (`Rater`): `prolific_id`, `study_id`, `session_id`, `session_start`, `session_end`, `is_active`, `is_preview`
- Per-question (`Question`): `gt_answer`, `options`, `question_type`, `extra_data` (untyped JSON blob)
- Per-assistance-session (`AssistanceSession`, FK'd from `Rating`): `method_name`, `params`, `step_type`, `state`, `payload`, `is_complete`, `created_at`, `updated_at`

### Researcher-facing surfaces

- `GET /admin/experiments/{id}/stats` — fast counts: `total_questions`, `total_ratings`, `total_raters`, `questions_complete`
- `GET /admin/experiments/{id}/analytics` — averages of response time and confidence, grouped by question and by rater. Computed on demand, no caching.
- `GET /admin/experiments/{id}/export` — streaming CSV at the **per-rating grain** with columns: `rating_id, question_id, question_text, gt_answer, rater_prolific_id, rater_study_id, rater_session_id, answer, confidence, time_started, time_submitted, response_time_seconds`
- All three accept `include_preview` (default false)
- Frontend `Analytics.tsx`: three tables (Overview, Per-Question, Per-Rater), preview toggle, refresh button. No charts, no drill-down.

### Prolific round management (relevant to data-quality v3)

- `Round` model + `/admin/experiments/{id}/prolific/recommend` computes avg time per question from existing ratings and recommends hours for the next round
- No quality gates: doesn't account for rater reliability before scaling

### Limitations

- `gt_answer` is captured but never compared to `Rating.answer` anywhere — no accuracy, no calibration, no agreement
- `AssistanceSession.state` and `payload` are captured but never exposed in the analytics endpoint or export — reliance metrics are unreachable today even though the underlying data is there
- No focus / paste / answer-change / first-interaction telemetry — can't detect AI agents or fast-clickers beyond raw timing
- No `is_attention_check` on `Question`; no `flagged` on `Rater`
- Analytics endpoint reports means only — no medians, no distributions, no histograms
- Researchers can pull per-rating data via the CSV export, but the admin UI never shows individual ratings (no drill-down)

---

# v1 – Capture + Compute + Visualize (pre-pilot)

### 1) Per-rating telemetry columns

Add to `Rating` (all nullable / default-zero so old rows still work):

- `first_interaction_at: datetime` — when the rater first clicked or typed
- `answer_change_count: int` — how many times the answer was changed before submit
- `tab_blur_count: int` — number of times the tab lost focus during this question
- `tab_blur_seconds: float` — total blurred time during this question
- `paste_count: int` — number of paste events into the answer field
- `client_metadata: text` — JSON for user agent, viewport, anything else we want later

Frontend changes in `QuestionCard.tsx` and `RaterView.tsx`:

- `first_interaction_at` set on first `onChange` of the answer input
- `answer_change_count` incremented on each value change (debounced for free-text)
- Tab blur tracked via `visibilitychange` listener scoped to the current question
- `paste_count` via `onPaste` listener

Backend: extend `RatingSubmit` schema and the `Rating` insert in `backend/services/rater/operations.py`. One Alembic migration. Add the new columns to the `EXPORT_COLUMNS` list in `backend/services/admin/exports.py` so the existing CSV export carries them.

### 2) Accuracy computation

Extend `build_analytics_payload` in `backend/services/admin/mappers.py`:

- Per-rating `is_correct: bool | null` — case-insensitive trimmed match for MC; null for FT (see Q below)
- Per-rater: `accuracy`, `num_gradable_ratings` (excludes FT and questions without gt_answer)
- Per-question: `accuracy`, `majority_answer`, `agreement_pct` (% of raters matching the majority — start simple, upgrade to Krippendorff later)
- Overall: `mean_rater_accuracy`, `mean_question_accuracy`

Backend-only PR. Also surface `is_correct` as a column in the existing CSV export.

### 3) Distribution charts

Tables don't show distributions. Add Recharts to the SPA and a fourth Analytics tab "Distributions":

- Histogram of per-rater accuracy
- Histogram of per-rater median response time
- Scatter of confidence vs. correctness (calibration plot — research deliverable in its own right)
- Box plot of per-question response times

Frontend-only PR, uses the payload from (2).

### 4) Confidence scale reconciliation

The live code uses 1–5 (`schemas.py`: `confidence: int = Field(ge=1, le=5)`). Prior data collection used a 0–100 slider with anchors at 0/50/100. Pick one before the pilot — irreversible after data collection starts.

**Recommendation:** restore 0–100 to enable direct comparison with prior data.

**Goal:** unblock every analytic researchers currently want. Even if (3) doesn't ship before pilot, (1) + (2) means we can run any of those analyses retrospectively.

---

# v2 – Quality & Action (post-pilot)

### 1) Attention checks

- Add `is_attention_check: bool = False` to `Question`
- CSV upload accepts an `is_attention_check` column
- Analytics computes per-rater `attention_check_pass_rate` and surfaces it on the rater table
- Default exclusion threshold: <80% pass rate flagged for review

Question content can be drawn from a standard list of attention-check items (e.g., "Please select Strongly disagree", "What is 3+5", "Please choose 25 on the slider").

### 2) Rater flagging

- Add `flagged: bool = False`, `flag_reason: text` to `Rater`
- Admin UI: flag button on each row of the rater table with a free-text reason
- Analytics filter: "include flagged raters" toggle, parallel to existing `includePreview`
- Export endpoint respects the same filter

### 3) Reliance metrics

Reliance metrics depend on the assistance method:

### **HumanAsATool** (single suggestion):
- **Take rate** — % of questions where the rater changed their answer to match the AI suggestion
- **Override rate** — % of questions where the rater stuck with their original answer despite a divergent suggestion
- **Outcome by reliance** — was reliance correlated with accuracy?

### **Top-N** (N candidates, none privileged):
- **Hit rate** — % of questions where the rater's final answer was one of the N candidates
- **Selected rank distribution** — when the rater picks from the set, which position do they pick? (Catches anchoring on candidate 1.)
- **Off-list rate** — % of questions where the rater's answer is none of the candidates
- **Outcome by selection** — accuracy conditional on selected rank vs. off-list

If metrics are computed on demand, requires persisting what was shown to the rater — probably `AssistanceSession.presented_candidates` plus `presented_order` if randomized. Independent of compute strategy, persisting candidates is also useful for retrospective analysis of N-sweep experiments.

### 4) Per-rater drill-down

Click a rater in the table → page showing every rating they submitted with question text, answer, gt, correctness, confidence, response time, blur events, paste count. This is what we'd actually use to decide whether to manually flag someone.

**Goal:** turn pilot data into actionable filters and decisions, instead of CSVs we grade by hand.

---

# v3 – Later

- **AI-agent detection signals** — variance of typing rhythm, mouse-movement entropy, time-to-first-interaction. Build the model offline against pilot data first; only ship a UI signal once we know what's predictive.
- **Auto-rerun after exclusion** — when a rater is filtered out, automatically request additional Prolific rating hours to backfill `num_ratings_per_question`. Slots into the existing `calculate_recommendation` logic in `backend/services/admin/rounds.py`, which already computes hours-needed from outstanding actions; v3 just teaches it to subtract excluded raters' contributions before recommending.
- **Cross-experiment dashboard** — rater performance across multiple studies; catches repeat low-quality raters.
- **Attention-check timing** — not just pass/fail but how long the check took vs. real questions.

---

## Other considerations

- **Q - Confidence scale:** 1–5 (current code) or 0–100 (prior data)? 
- **Q - Free-text grading:** in-platform (LLM judge), or always export-and-grade-offline?
- **Q - Where accuracy lives:** computed on demand in the analytics endpoint (proposed) or persisted on `Rating` at submit time?

