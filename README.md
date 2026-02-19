# Human Rating Platform

A web platform for collecting human ratings on LLM responses, designed for use with Prolific.

## Features

- **Admin Panel**: Create experiments, upload questions via CSV, view analytics, export ratings
- **Rater Interface**: Clean UI for rating questions with confidence scores and session timer
- **Prolific Integration**: Automatic capture of Prolific IDs and redirect on completion
- **Analytics**: Per-question and per-rater statistics with response time tracking

## Tech Stack

- **Backend**: Python FastAPI + SQLAlchemy
- **Frontend**: React + TypeScript + Vite
- **Database**: SQLite (local) or PostgreSQL/MySQL (production)

## Local Development

### Prerequisites

- Python 3.9+
- Node.js 18+

### Setup

1. **Set up the backend**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set up the frontend**
   ```bash
   cd frontend
   npm install
   ```

### Running Locally

Start both servers separately:

**Backend**:
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

**Frontend**:
```bash
cd frontend
npm run dev
```

Access the app at the provided front end URL

## CSV Format

Upload questions using a CSV file with the following columns:

| Column | Required | Description |
|--------|----------|-------------|
| `question_id` | Yes | Unique identifier for the question |
| `question_text` | Yes | The question text to display |
| `gt_answer` | No | Ground truth answer (for export/analysis) |
| `options` | No | Comma-separated options for multiple choice |
| `question_type` | No | `MC` (multiple choice) or `FT` (free text). Default: `MC` |
| `metadata` | No | JSON string with additional data |

Example:
```csv
question_id,question_text,gt_answer,options,question_type
q1,"Is the sky blue?","Yes","Yes,No,Maybe",MC
q2,"Explain photosynthesis","Plants convert sunlight...",,FT
```

## Prolific Integration

1. Create your experiment in the admin panel
2. Copy the **Study URL** from the experiment settings
3. In Prolific, paste this URL as your study URL
4. Set the **Completion URL** in your experiment settings (get this from Prolific)

The Study URL format:
```
https://your-app.com/rate?experiment_id=1&PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}
```

## Deployment to Render

This app deploys as two separate services on Render:

### 1. Backend (Web Service)

1. Create a new **Web Service** on Render
2. Connect your GitHub repository
3. Configure:
   - **Name**: `human-rating-platform-api`
   - **Root Directory**: `backend`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

4. Add environment variables:
   | Variable | Description |
   |----------|-------------|
   | `DATABASE_URL` | Database connection string (optional, defaults to SQLite) |
   | `CORS_ORIGINS` | Frontend URL, e.g., `https://your-frontend.onrender.com` |

5. If using SQLite, add a **Disk** for persistent storage:
   - Mount path: `/data`

### 2. Frontend (Static Site)

1. Create a new **Static Site** on Render
2. Connect the same GitHub repository
3. Configure:
   - **Name**: `human-rating-platform`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`

4. Add environment variable:
   | Variable | Description |
   |----------|-------------|
   | `VITE_API_URL` | Backend URL, e.g., `https://human-rating-platform-api.onrender.com` |

5. Add a **Rewrite Rule** for SPA routing:
   - **Source**: `/*`
   - **Destination**: `/index.html`
   - **Action**: Rewrite

### 3. Update CORS

After both services are deployed, update the backend's `CORS_ORIGINS` environment variable with your frontend URL.

## Environment Variables

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | SQLite in `/data` | Database connection string |
| `CORS_ORIGINS` | `*` | Allowed origins (comma-separated) |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | (empty) | Backend API URL |

## API Endpoints

### Admin

- `POST /api/admin/experiments` - Create experiment
- `GET /api/admin/experiments` - List experiments
- `POST /api/admin/experiments/{id}/upload` - Upload questions CSV
- `GET /api/admin/experiments/{id}/stats` - Get experiment stats
- `GET /api/admin/experiments/{id}/analytics` - Get detailed analytics
- `GET /api/admin/experiments/{id}/export` - Export ratings as CSV
- `DELETE /api/admin/experiments/{id}` - Delete experiment

### Rater

- `POST /api/raters/start` - Start rating session
- `GET /api/raters/next-question` - Get next question
- `POST /api/raters/submit` - Submit rating
- `GET /api/raters/session-status` - Check session status

## License

MIT
