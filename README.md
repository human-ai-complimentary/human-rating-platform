# Human Rating Platform

A web platform for collecting human ratings on LLM responses, designed for use with Prolific.

## Support Scope

- Supported runtime target: Docker Compose.
- Supported hosted deployment target: Render Blueprint via `render.yaml`.
- Legacy manifests (`backend/Procfile`, `backend/railway.json`) are not maintained in this pass.

## Stack

- Backend: FastAPI + SQLModel (async)
- Migrations: Alembic
- Python tooling: uv / uvx
- Config: Pydantic Settings (`backend/config.toml` + `backend/.env` + process env)
- Frontend: React + TypeScript + Vite
- Database: PostgreSQL

## Configuration Model

Backend config is accessed only through `backend/config.py` (`get_settings()`), with this precedence:

1. Python init kwargs
2. Process environment variables
3. `backend/.env`
4. `backend/config.toml`
5. Python defaults

Backend env overrides use nested keys with `__`:

- `APP__CORS_ORIGINS`
- `DATABASE__URL`
- `EXPORTS__STREAM_BATCH_SIZE`
- `TESTING__EXPORT_SEED_ROW_COUNT`
- `SEEDING__*`

Contributor notes:

- `backend/config.py` is the single source of truth for backend settings.
- Unknown environment keys are tolerated; only recognized keys are used.
- Legacy flat env keys (for example `DATABASE_URL`, `CORS_ORIGINS`, `DEV_SEED_*`) are rejected at startup.
- When adding a new setting, add it to nested `Settings` models first, then document the env key.

Frontend config uses `frontend/.env`:

- `VITE_API_HOST` (API origin, for example `https://human-rating-platform-api.onrender.com`)
- `VITE_API_PREFIX` (optional path prefix; default empty)

Default local/dev happy path:

- `VITE_API_HOST=`
- `VITE_API_PREFIX=`

Optional local ingress mode (for setups that expose API under `/api`):

- `VITE_API_HOST=`
- `VITE_API_PREFIX=/api`

Tailscale local exposure tip:

- Yes, Funnel can route by path when configured via Serve/Funnel handlers (for example `/ -> :5173` and `/api -> :8000`).
- Why this setup is useful:
  - public HTTPS endpoint on your `.ts.net` domain
  - frontend + API on the same origin (`/` + `/api`)
  - avoids mixed-content errors
  - reduces CORS complexity for local internet exposure
  - gives you a clean HTTPS URL to paste into Prolific
- In that setup, keep `VITE_API_HOST=` and `VITE_API_PREFIX=/api`.
- Verify active handlers with `tailscale funnel status --json`.
- If you expose backend directly (`tailscale funnel 8000` with no `/api` handler), set `VITE_API_HOST=https://<your-host>.ts.net` and `VITE_API_PREFIX=`.

Example handler setup:

```bash
tailscale funnel --bg --set-path / http://127.0.0.1:5173
tailscale funnel --bg --set-path /api http://127.0.0.1:8000
tailscale funnel status --json
```

`backend/config.toml` is the base local config. Main sections:

- `[exports]` controls CSV export chunking via `stream_batch_size` (memory/throughput tradeoff).
- `[testing]` controls characterization export dataset volume via `export_seed_row_count`.
- `[seeding]` controls optional local seed generation for `make db.seed` (`enabled`, `experiment_name`, `question_count`, `num_ratings_per_question`, `prolific_completion_url`).

## Local Setup

### Prerequisites

- Python 3.10+
- Node.js 20+
- Docker + Docker Compose

### One-time setup

```bash
make env.sync
```

This creates:

- `backend/.env` from `backend/.env.example`
- `frontend/.env` from `frontend/.env.example`

### Core workflow

```bash
make up          # start db + alembic migration + api (hot reload)
make ps          # show running services
make logs        # stream db/api logs
make test        # run characterization tests with real db+migrations
make fmt         # format backend Python
make db.seed     # seed local dataset from backend/config.toml (disabled by default)
make down        # stop services
make db.clear    # wipe local DB volume (destructive)
make db.reset    # wipe + rebuild from migrations
make db.up       # run alembic upgrade head
make db.down     # rollback one migration (set MIGRATION_REVISION=... to override)
```

Create a new migration:

```bash
make db.new MIGRATION_NAME=add_new_column
```

Makefile targets are intentionally backend-focused. Frontend dev runs separately.

Run frontend in a second terminal:

```bash
cd frontend
make up
```

## Render Deployment

`render.yaml` now reflects the current split architecture:

- `human-rating-platform-web` (static frontend)
- `human-rating-platform-api` (FastAPI backend)
- `human-rating-platform-db` (Postgres)
- both web + API use `autoDeployTrigger: checksPass` (Render deploys after GitHub checks pass on `main`)

Default Render blueprint wiring in `render.yaml`:

- API service: `APP__CORS_ORIGINS=https://human-rating-platform-web.onrender.com`
- Frontend service: `VITE_API_HOST=https://human-rating-platform-api.onrender.com`
- Frontend service: `VITE_API_PREFIX=""`

If you rename services or use custom domains, override those values in Render.

Recommended production flow:

1. CI (`.github/workflows/main.yml`) runs lint + characterization tests.
2. Protected branch rules gate merges to `main` (owners/admins approve here).
3. Render auto-deploys from `main` only after checks pass.
4. No custom deploy workflow in this repo; deployment orchestration is Render-native.
5. Runtime secrets live in Render Secret Groups (not in this repo).

Render setup runbook:

- [`ops/secrets/README.md`](ops/secrets/README.md)

## CI Lint

Local commands that mirror `main.yml`:

```bash
uvx ruff==0.15.2 check backend
uvx ruff==0.15.2 format --check backend
npm --prefix frontend run lint
npm --prefix frontend run typecheck
uvx yamllint==1.38.0 .
```

## Alembic Commands

Usage guidance:

- Use `make db.up`, `make db.down`, and `make db.new MIGRATION_NAME=...` for normal development.
- Use the direct Alembic commands below when you need explicit control (debugging/history/stamping).

Common Make targets:

```bash
make db.up
make db.down
make db.new MIGRATION_NAME=my_change
```

Direct Alembic commands via thin wrapper:

```bash
cd backend
sh scripts/migrate.sh upgrade head
sh scripts/migrate.sh downgrade -1
sh scripts/migrate.sh revision --autogenerate --rev-id "$(date -u +%Y%m%d%H%M%S)" -m "my_change"
sh scripts/migrate.sh current
sh scripts/migrate.sh history
sh scripts/migrate.sh stamp head
```

## CSV Format

Upload questions with these columns:

| Column | Required | Description |
| --- | --- | --- |
| `question_id` | Yes | Unique identifier for the question |
| `question_text` | Yes | Question text shown to raters |
| `gt_answer` | No | Ground-truth answer |
| `options` | No | Comma-separated options for MC |
| `question_type` | No | `MC` or `FT` (default `MC`) |
| `metadata` | No | JSON string with additional data |

Example:

```csv
question_id,question_text,gt_answer,options,question_type
q1,"Is the sky blue?","Yes","Yes,No,Maybe",MC
q2,"Explain photosynthesis","Plants convert sunlight...",,FT
```

## Prolific Integration

1. Create an experiment in admin.
2. Copy the study URL.
3. Paste it into Prolific as external study URL.
4. Set completion URL in experiment settings.

Study URL format:

```text
https://your-app.com/rate?experiment_id=1&PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}
```

## API Endpoints

### Admin

- `POST /admin/experiments`
- `GET /admin/experiments`
- `POST /admin/experiments/{id}/upload`
- `GET /admin/experiments/{id}/stats`
- `GET /admin/experiments/{id}/analytics`
- `GET /admin/experiments/{id}/export`
- `DELETE /admin/experiments/{id}`

### Rater

- `POST /raters/start`
- `GET /raters/next-question`
- `POST /raters/submit`
- `GET /raters/session-status`
- `POST /raters/end-session`

## License

MIT
