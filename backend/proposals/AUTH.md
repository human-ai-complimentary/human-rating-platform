# Authentication & Access Control Roadmap  

This document defines the staged approach to authentication and access control for both **Researcher (experiment management)** and **Rater (participant)** flows.

---

# Researcher Access

### v0 – Open Access
- Anyone can access all experiments
- No authentication required

---

### v1 – Firebase Auth (Email/Password + Google) + Invite-Only Allowlist

- Use **Firebase Authentication** for admin authentication (supports both email/password and Google sign-in)
- Admins can:
  - Sign up / sign in with **email + password**
  - Or sign in with **Google**
- After Firebase auth, backend checks whether the user’s email is in an **invite-only allowlist**
- If not allowlisted → deny access (403) to `/admin` UI and `/api/admin/*`
- If allowlisted → backend creates an application session ([HTTPOnly](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Cookies) should suffice)
- All allowlisted admins can access all experiments

**Alternatives considered**
- **Sign in with Prolific:** Not viable — Prolific does not provide an OAuth-style “Sign in with Prolific” API for admin authentication
- **Homegrown username/password (no managed provider):** Avoided due to added complexity (password storage, reset flow, lockouts, security hardening)

**Why this approach**
- Minimal implementation complexity (Firebase SDK + backend token verification)
- No custom password storage or reset flows
- Clear identity + audit trail for admin actions
- Works well for a small invite-only team without a shared Workspace domain
- Supports both Google and email/password for admins
- Firebase Auth is free up to roughly **50k users**, so cost is not a concern at our expected scale

**Goal:** Prevent public access to experiment data and exports

---

## v2 – Owner + Collaborator Model
- Anyone who authenticates via Firebase (email/password or Google) is an admin and can create their own experiment
- To access other experiments, backend authorizes access based on experiment-level rules

### Experiment Access Rules
- Owner can:
  - View/edit/export/delete
  - Add/remove collaborators
- Collaborators can:
  - View/edit/export
  - Access only experiments they are assigned to
- Superadmin (optional) can access all experiments

### UI Additions
- “Share” / “Access” section in experiment detail
- Add collaborator by email
- List owner + collaborators

**Goal:** Scoped experiment-level access control

**Q - Does it make more sense to control access per experiment (as above) or per team?**

---

## Other considerations

- **Why not only “Sign in with Google”?**
  - Not everyone will want (or be able) to sign in with Google
  - Email/password via Firebase lets us onboard anyone with an email address while still offering Google as a one-click option.

- **Why Firebase Auth specifically?**
  - Provides Google sign-in, email/password auth, email verification, and password reset flows out of the box.
  - We don’t have to build or maintain password + email infrastructure (secure storage, reset tokens, lockouts, etc.) ourselves
  - Firebase Auth is free up to around **50k users**, so cost should not be an issue at our scale

---

# Rater Access

Raters access experiments exclusively via Prolific external study links.

---

## v0 – Minimal Param Check
Requires:
- `experiment_id`
- `PROLIFIC_PID`

Shows error if missing.

### Limitations
- Query params are trusted throughout session
- `/next-question?rater_id=...` is callable if ID guessed
- Link sharing mid-task possible

---

## v1 – Strict Param Enforcement + Server Session + Reconciliation

### 1) Required Query Params
Require **all** of:
- `experiment_id`
- `PROLIFIC_PID`
- `STUDY_ID`
- `SESSION_ID`

If any missing → show:

> “Please access this study from Prolific.”

---

### 2) Format Validation
Before session creation:
- Ensure `PROLIFIC_PID`, `STUDY_ID`, `SESSION_ID` match expected pattern: `^[a-f0-9]{24}$` and reject if invalid

Blocks:
- Accidental malformed URLs
- Basic manual tampering

### 3) Server-Issued Session Identifier

#### Flow
1. Participant lands on:
`/rate?experiment_id=...&PROLIFIC_PID=...&STUDY_ID=...&SESSION_ID=...`

2. Frontend calls:
`POST /api/raters/start`

3. Backend:
- Validates params
- Creates `RaterSession`
- Returns:
  - `rater_session_token` (random UUID or signed token)
  - session metadata
4. Frontend:
- Stores session token
- Removes query params using `history.replaceState`
5. All future requests use:
- Session token (NOT query params and NOT `rater_id` alone)

Blocks:
- Guessing `/next-question?rater_id=...`
- Calling submit endpoints with arbitrary IDs
- Link sharing mid-task
- Replaying initial Prolific URL

### 4) Post-Hoc Reconciliation (Data Integrity Layer)

After data collection:
- Reconcile each session by cross-checking `SESSION_ID`, `PROLIFIC_PID` + `STUDY_ID` against Prolific submission records
- Drop any sessions that do **not** exist in Prolific’s records

This ensures:
- Only real Prolific participation attempts are included in analysis
- Fabricated or externally injected sessions are excluded