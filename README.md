# Human Rating Platform

A web platform for collecting human ratings on LLM responses, designed for use with Prolific.

## Support Scope

- Supported runtime target: Docker Compose.
- Legacy manifests (`render.yaml`, `backend/Procfile`, `backend/railway.json`) are not maintained in this pass.

## Stack

- Backend: FastAPI + SQLModel (async)
- Migrations: Alembic
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

Frontend config uses `frontend/.env`:

- `VITE_API_HOST` (optional, example `https://your-host.ts.net`; empty = same-origin)
- `VITE_API_PREFIX` (optional; default empty)

Default local/dev happy path:

- `VITE_API_HOST=`
- `VITE_API_PREFIX=`

Optional ingress mode (for setups that expose API under `/api`):

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
- Node.js 18+
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
make db.seed     # seed local dataset from backend/config.toml (disabled by default)
make down        # stop services
make db.clear    # wipe local DB volume (destructive)
make db.reset    # wipe + rebuild from migrations
make db.migrate  # run alembic upgrade head
```

Create a new migration:

```bash
make db.migrate.new MIGRATION_NAME=add_new_column
```

Makefile targets are intentionally backend-focused. Frontend dev runs separately.

Run frontend in a second terminal:

```bash
cd frontend
make up
```

## CI Lint

Local commands that mirror `main.yml`:

```bash
ruff check backend
ruff format --check backend
npm --prefix frontend run lint
npm --prefix frontend run typecheck
yamllint .
```

## Alembic Commands

The project uses a wrapper command instead of `alembic.ini`:

```bash
cd backend
python scripts/migrate.py upgrade head
python scripts/migrate.py current
python scripts/migrate.py revision --autogenerate -m "my_change"
python scripts/migrate.py stamp head
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
