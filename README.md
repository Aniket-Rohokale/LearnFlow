# TrackAI

TrackAI is a personal learning dashboard that captures courses from learning platforms (via a Chrome extension + LLM syllabus parser), tracks module progress and study time, and uses AI to plan your week, flag burnout risk, and recommend next skills.

```
learnflow/
├── backend/          FastAPI + SQLAlchemy (async) + Supabase Postgres
├── frontend/         React 19 + Vite + Tailwind (retro UI)
├── extension/        Chrome Manifest V3 capture + study timer
└── supabase/         SQL migration (schema + RLS)
```

---

## What it does

| Feature | How |
|---|---|
| **Course capture** | Extension scrapes page text → `POST /api/courses/ingest` → LLM parses syllabus → upserts on `(user_id, url)` |
| **Progress tracking** | Module checklists; percent is recomputed server-side on every toggle |
| **Study logging** | Manual form, extension Start/Stop timer, or dashboard source |
| **AI study plan** | 7-day calendar from incomplete modules + your daily hours cap |
| **Burnout detector** | Cheap heuristic gate over 14 days of activity; LLM only when thresholds trip |
| **Skill roadmap** | Gaps + ordered next steps from completed work + career goal |

Auth is Supabase email/password. The FastAPI backend verifies Supabase JWTs on every `/api/*` route. The browser never holds the LLM key — all AI calls are server-side.

---

## Pages

### Public

| Route | Page | What you do |
|---|---|---|
| `/login` | Sign in | Email + password against Supabase Auth |
| `/signup` | Create account | Min 8-char password; may require email confirmation depending on Supabase settings |

### Authenticated (header nav: Overview · Activity · Plan · Roadmap · Profile)

#### `/` — Overview
- **Stats:** courses, overall %, streak, this week's hours, burnout-risk badge (click for signals/suggestions)
- **How to capture & update** — step-by-step guide for the extension, plus a yellow note: *do not switch tabs while the capture is running*
- **Log a course manually** — title / platform / URL / instructor → `POST /api/courses`
- **Weekly activity chart** — last 7 days (zero-filled bars)
- **Course list** — progress bars linking to course detail

#### `/courses/:id` — Course detail
- Title, platform, instructor, external URL
- Progress bar + module checklist (optimistic toggle via `PATCH /api/modules/:id`)
- Delete course (confirm dialog) → cascades modules + progress

#### `/activity` — Study log
- **Log a session** — minutes + optional datetime (`source: manual`)
- **Add the course you're learning** — same manual course form as Overview
- Recent sessions list (14 days) with source badges (`extension` / `manual` / `dashboard`)

#### `/plan` — Study plan
- 7-day columns of study blocks (module + minutes), daily totals
- **Regenerate** → `POST /api/plan/generate` (needs `target_hours_per_day` in Profile and incomplete modules)
- Empty state until you generate one; page loads only read the latest stored plan (no AI call)

#### `/roadmap` — Skill roadmap
- Identified skill gaps (chips) + numbered next steps (skill / why / resource)
- **Regenerate** → `POST /api/roadmap/generate` (needs `career_goal` in Profile; 409 otherwise)
- Auto-regenerates when a course hits 100% (best-effort, never blocks the toggle)

#### `/profile` — Profile
- Career goal (textarea) and target study hours/day
- These feed the planner and roadmap; helper text explains that

---

## Chrome extension

Load `extension/` as an **unpacked** extension (`chrome://extensions` → Developer mode → Load unpacked).

| Control | Behavior |
|---|---|
| Status dot | Green once you've signed into the TrackAI dashboard (token synced from Supabase localStorage) |
| **Capture this course** | Reads `document.body.innerText`, normalizes the URL, `POST /api/courses/ingest` |
| **Start / Stop** timer | `sessionStart` in `chrome.storage.local` survives popup close; Stop posts elapsed minutes as `source: extension` (sessions &lt; 1 min discarded) |

Host permission defaults to `http://localhost:8000/*`. Content script runs on `http://localhost:5173/*` to sync the auth token.

---

## Local setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project (Auth + Postgres)
- An OpenAI-compatible API key (OpenAI, or any router that speaks the chat-completions API)

### 1. Database

In the Supabase SQL editor, run:

```
supabase/migrations/20260720000001_init.sql
```

That creates `users`, `courses`, `modules`, `course_progress`, `activity_logs`, `ai_recommendations`, RLS policies, and the signup trigger that mirrors `auth.users` → `public.users`.

### 2. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Fill `backend/.env`:

| Variable | Where to get it |
|---|---|
| `SUPABASE_URL` | Project Settings → API |
| `SUPABASE_JWT_SECRET` | Project Settings → API → JWT Settings (legacy HS256 secret; optional if your project only uses JWKS) |
| `DATABASE_URL` | Project Settings → Database → Connection string → URI, **Transaction pooler on port 6543**, with `postgresql+asyncpg://` scheme |
| `OPENAI_API_KEY` | Your provider |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` or your router |
| `OPENAI_MODEL` | e.g. `gpt-4o-mini` |
| `CORS_ORIGINS` | `http://localhost:5173` (comma-separated; add the extension origin at deploy) |

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Health check: [http://localhost:8000/health](http://localhost:8000/health) → `{"status":"ok"}`.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
```

Fill `frontend/.env`:

| Variable | Value |
|---|---|
| `VITE_SUPABASE_URL` | Same Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Project Settings → API → anon public key |
| `VITE_API_URL` | `http://localhost:8000` |

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

### 4. Extension

1. Sign up / sign in at `http://localhost:5173` first (stocks the token).
2. Chrome → `chrome://extensions` → Developer mode → **Load unpacked** → select the `extension/` folder.
3. Open a course page → click the TrackAI icon → **Capture this course**. Stay on the tab until the popup finishes.

### 5. Tests (backend)

```bash
cd backend
.venv\Scripts\python -m pytest tests/ -v   # Windows
# or: python -m pytest tests/ -v
```

The suite uses in-memory SQLite and HS256 test JWTs — no network, no real Supabase, no LLM calls. LLM paths are monkeypatched.

---

## API surface (all under `/api`, JWT required)

| Method | Path | Purpose |
|---|---|---|
| GET | `/me` | Auth smoke test |
| GET/PATCH | `/profile` | Career goal + target hours |
| GET/POST | `/courses` | List / manual create |
| POST | `/courses/ingest` | Extension capture (LLM parse + upsert) |
| GET/PATCH/DELETE | `/courses/{id}` | Detail / edit / delete |
| POST | `/courses/{id}/modules` | Add module |
| PATCH/DELETE | `/modules/{id}` | Toggle complete / delete |
| GET/POST | `/activity` | List / log session |
| GET | `/dashboard` | Overview payload (+ gated burnout assess) |
| POST | `/plan/generate` | Build 7-day plan |
| POST | `/burnout/assess` | Force re-assess |
| POST | `/roadmap/generate` | Build skill roadmap |
| GET | `/recommendations/{type}/latest` | Latest stored plan / burnout / roadmap |

---

## Stack

- **Backend:** FastAPI, SQLAlchemy 2 (async) + asyncpg, Pydantic v2, PyJWT, OpenAI SDK
- **DB / Auth:** Supabase Postgres + Auth (RLS on all tables; backend connects as owner)
- **Frontend:** React 19, Vite 8, Tailwind 4, TanStack Query, React Router 7, Recharts
- **Extension:** Manifest V3, vanilla JS (no build step)
- **UI:** old-school fixed-width page tiers (540 / 720 / 960 px), double borders, beveled buttons, serif + mono type

---

## Notes

- Re-capturing the same course URL (query/fragment/trailing-slash normalized) **updates** modules in place and preserves completion by title match — it does not duplicate.
- Page loads never trigger AI. Generation is always an explicit `POST` (or the gated auto-assess on dashboard load / course-complete auto-roadmap).
- Successful AI outputs are append-only rows in `ai_recommendations` (`type ∈ syllabus | plan | burnout | roadmap`).
