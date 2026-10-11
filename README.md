# InsightFlow — Intelligent Customer Feedback & Decision Platform

An end-to-end, AI-assisted platform that turns raw customer feedback into evidence-backed,
explainable business decisions. Built for **Build Battle 2026** (AI × Web Development).

InsightFlow ingests customer-feedback CSVs, analyzes each record for sentiment and topic,
groups similar complaints with text-similarity clustering, prioritizes the resulting issues
with a transparent scoring formula, and turns the highest-impact issues into actionable,
evidence-backed recommendations — all persisted in a real database and presented through a
polished, responsive analytics UI.

---

## Table of contents

1. [Key features](#key-features)
2. [Architecture](#architecture)
3. [Technology stack](#technology-stack)
4. [Project structure](#project-structure)
5. [Prerequisites](#prerequisites)
6. [Installation](#installation)
7. [Environment variables](#environment-variables)
8. [Database initialization](#database-initialization)
9. [Seeding the dataset](#seeding-the-dataset)
10. [Running the app](#running-the-app)
11. [AI configuration](#ai-configuration)
12. [Adaption setup & integration](#adaption-setup--integration)
13. [How the analysis pipeline works](#how-the-analysis-pipeline-works)
14. [Priority scoring](#priority-scoring)
15. [Testing](#testing)
16. [Deployment](#deployment)
17. [Demonstration guide](#demonstration-guide)
18. [Troubleshooting](#troubleshooting)

---

## Key features

- **CSV import** with validation, duplicate detection, and clear error messages (empty file,
  malformed CSV, missing required columns). Imports never block the browser.
- **Duplicate-aware analytics** — all records are preserved; duplicate texts are flagged, and
  metrics distinguish total records from unique review texts. Analysis runs once per unique
  text and reuses cached results.
- **Sentiment analysis** — Positive / Negative / Neutral with a real confidence value derived
  from the model's own class proportions (no invented scores). A domain-tuned lexicon and a
  transparent all-clear rule cover e-commerce vocabulary.
- **Topic identification** — a human-readable keyword lexicon with explicit negation handling
  (so "no fraudulent activity" is not misread as a fraud complaint). Matched keywords are
  stored as inspectable evidence.
- **Similarity grouping** — TF-IDF + agglomerative clustering groups paraphrases of the same
  complaint ("delivery was late" ≈ "shipment was delayed") so unrelated reviews are not
  grouped merely for sharing a sentiment.
- **Explainable prioritization** — a configurable weighted formula (frequency, negative
  ratio, severity, trend) with renormalization when a factor's data is missing, plus a
  severity floor so frequent mild complaints never auto-escalate to Critical.
- **Evidence-backed recommendations** — each recommendation cites record counts, negative
  ratio, category breakdown, and sample reviews. A transparent template engine is the
  default; an optional LLM refines wording when configured (and is labelled as such).
- **Persistent issue tracker** — save issues, change status/priority, add notes and action
  plans, resolve/reopen. Everything survives a backend restart.
- **Reports & exports** — generate report snapshots and export PDF or CSV; filtered feedback
  CSV export; report history is persisted.
- **Interactive dashboard** — KPI cards and charts (sentiment, category, topic, priority)
  computed from live data. A trend chart appears **only** when real timestamps exist; without
  them the UI explains why the chart is unavailable rather than fabricating dates.
- **Adaption integration** — a real Adaptive Data workflow (instruction-dataset optimization)
  with an honest, verifiable status and graceful fallback when unconfigured.

---

## Architecture

```
┌─────────────┐   HTTP/JSON    ┌──────────────────────────────┐
│   Frontend  │ ─────────────▶ │           Backend            │
│ React + Vite│   /api proxy   │           FastAPI            │
└─────────────┘                │  ┌────────────────────────┐  │
                               │  │  Routers (feedback,     │  │
                               │  │  analytics, issues,     │  │
                               │  │  reports, system)       │  │
                               │  └───────────┬────────────┘  │
                               │              │               │
                               │  ┌───────────▼────────────┐  │
                               │  │      Services          │  │
                               │  │  importer (pandas)     │  │
                               │  │  analyzer (VADER,      │  │
                               │  │   lexicon, TF-IDF)     │  │
                               │  │  prioritization        │  │
                               │  │  recommendations       │  │
                               │  │  reporting (PDF/CSV)   │  │
                               │  │  adaption_service      │  │
                               │  └───────────┬────────────┘  │
                               │              │               │
                               │  ┌───────────▼────────────┐  │
                               │  │  SQLAlchemy + SQLite   │  │
                               │  └────────────────────────┘  │
                               └──────────────────────────────┘
```

Clear separation of concerns: frontend, backend API, dataset import/validation, analysis
pipeline, issue grouping & prioritization, recommendation generation, persistence, Adaption
integration, and reporting/export are each their own module.

---

## Technology stack

**Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, Recharts, lucide-react,
React Router.

**Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, pandas, scikit-learn,
VADER (vaderSentiment), reportlab (PDF), optional `adaption` SDK.

**Database:** SQLite (single-instance deployment).

---

## Project structure

```
insightflow/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, router wiring, startup
│   │   ├── config.py             # env-driven settings
│   │   ├── database.py           # engine, session, init_db
│   │   ├── models.py             # SQLAlchemy ORM models
│   │   ├── routers/
│   │   │   ├── feedback.py       # list/search/filter, manual submit, CSV import
│   │   │   ├── analytics.py      # summary, charts, job progress, issue groups
│   │   │   ├── issues.py         # tracker CRUD, notes, evidence
│   │   │   ├── reports.py        # generate, history, CSV/PDF export
│   │   │   └── system.py         # settings, Adaption status/run, health
│   │   └── services/
│   │       ├── importer.py       # pandas CSV validation & duplicate handling
│   │       ├── analyzer.py       # background pipeline orchestration
│   │       ├── sentiment.py      # VADER + domain lexicon
│   │       ├── topics.py         # keyword lexicon with negation handling
│   │       ├── clustering.py     # TF-IDF + agglomerative grouping
│   │       ├── prioritization.py # explainable scoring
│   │       ├── recommendations.py# template engine + optional LLM
│   │       ├── reporting.py      # report snapshots, CSV & PDF builders
│   │       └── adaption_service.py # Adaptive Data workflow + evaluation
│   ├── data/
│   │   ├── adaption_reference_labels.json  # hand-labeled evaluation subset
│   │   └── insightflow.db                   # created at startup
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/           # Layout, ui primitives
│   │   ├── lib/                  # api client, types, toast
│   │   └── pages/                # Overview, Feedback Explorer, AI Insights,
│   │                             # Recommendations, Issue Tracker, Reports, Settings
│   └── vite.config.ts            # Tailwind + /api proxy to backend
├── scripts/
│   └── seed.py                   # one-command dataset load + analysis
├── data/
│   └── BuildBattle_2026_Customer_Feedback_Dataset.csv
└── README.md
```

---

## Prerequisites

- **Python** 3.11+
- **Node.js** 18+ (with npm)
- No external services required — SQLite is embedded.

---

## Installation

```bash
# 1. Backend dependencies
cd insightflow/backend
pip install -r requirements.txt

# 2. Frontend dependencies
cd ../frontend
npm install
```

---

## Environment variables

Copy the example env file and adjust as needed. **Never commit real secrets.**

```bash
cd insightflow/backend
cp .env.example .env
```

| Variable | Required | Purpose |
|---|---|---|
| `INSIGHTFLOW_DATABASE_URL` | No | SQLite path (defaults to `backend/data/insightflow.db`) |
| `INSIGHTFLOW_MAX_UPLOAD_MB` | No | CSV upload size limit (default 25 MB) |
| `INSIGHTFLOW_ANALYSIS_BATCH_SIZE` | No | Records per analysis batch (default 200) |
| `INSIGHTFLOW_CORS_ORIGINS` | No | Comma-separated allowed origins (dev: `http://localhost:5173`) |
| `INSIGHTFLOW_LLM_API_KEY` | Optional | Enables LLM-written recommendation wording |
| `INSIGHTFLOW_LLM_BASE_URL` | Optional | OpenAI-compatible endpoint |
| `INSIGHTFLOW_LLM_MODEL` | Optional | Model name |
| `ADAPTION_API_KEY` | Optional | Enables the real Adaption Adaptive Data workflow |

Sentiment, topic, and clustering analysis are fully local and require **no API keys**. LLM
and Adaption are optional enhancements; the app is fully functional without them and shows an
honest status when they are unconfigured.

---

## Database initialization

Tables are created automatically on backend startup (`init_db()` runs at startup and calls
`Base.metadata.create_all`). There are no manual migration steps for the initial version.

To reset the database completely:

```bash
cd insightflow/backend
rm -f data/insightflow.db
# restart the backend; tables are recreated empty
```

---

## Seeding the dataset

The supplied dataset ships with the project at
`insightflow/data/BuildBattle_2026_Customer_Feedback_Dataset.csv` (7,000 records, 4 categories,
320 unique review texts). Load it and run the full analysis with one command:

```bash
# with the backend running on http://127.0.0.1:8000
cd insightflow
python scripts/seed.py
```

The script waits for any in-flight job, imports the CSV in `replace` mode, and polls analysis
until it completes. Re-running it is idempotent (related rows are cleaned up on replace).

You can also import through the UI (**Feedback Explorer → Import CSV**) or the API:

```bash
curl -X POST -F "file=@data/BuildBattle_2026_Customer_Feedback_Dataset.csv" \
     -F "mode=replace" http://127.0.0.1:8000/api/feedback/import
```

---

## Running the app

**Backend** (terminal 1):

```bash
cd insightflow/backend
uvicorn app.main:app --reload --port 8000
```

**Frontend** (terminal 2):

```bash
cd insightflow/frontend
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies `/api` to the backend on port 8000.

Interactive API docs: **http://127.0.0.1:8000/docs**.

---

## AI configuration

- **Sentiment:** VADER with a documented domain lexicon (e-commerce complaint/praise terms)
  and an explicit all-clear rule for factual safety confirmations. Confidence is derived from
  the model's own class proportions. Verified against the 50 clear-item reference subset: 100%
  sentiment and 96% topic accuracy (the 9 genuinely ambiguous mixed reviews are scored
  separately).
- **Topics:** an ordered, human-readable keyword lexicon with negation handling. Matched
  keywords are stored as evidence on each analysis row.
- **Similarity grouping:** TF-IDF vectors + agglomerative clustering over unique review texts.
- **Recommendations:** a transparent template engine (default) or an optional OpenAI-compatible
  LLM. When the LLM is used, the recommendation is labelled "LLM-generated"; otherwise it is
  labelled "Template engine". The LLM prompt receives only structured statistics and a few
  sample reviews — never the full dataset.

To enable LLM recommendations, set `INSIGHTFLOW_LLM_API_KEY` (and optionally base URL/model)
in `backend/.env` and restart the backend.

---

## Adaption setup & integration

InsightFlow integrates **Adaption** (https://adaptionlabs.ai) meaningfully into the AI
workflow via the official Python SDK — not just a logo. The task: build an optimized
**instruction dataset** (review → structured analysis) from InsightFlow's analyzed feedback,
run it through Adaptive Data, and evaluate the result against a hand-labeled reference subset.

**Workflow implemented in `adaption_service.py`:**

1. Prepare a task-specific instruction dataset from real, analyzed feedback.
2. Upload via `client.datasets.upload_file()`.
3. Map columns (prompt / completion / context) and request an estimate.
4. Run `client.datasets.adapt()` and poll `get_status()` until completion.
5. Download the adapted dataset and evaluate against the reference subset.
6. Record every attempt honestly in the `adaption_runs` table (succeeded / failed /
   not_configured), with the real step and error if any.

**Setup:**

```bash
cd insightflow/backend
pip install adaption
# put your key in backend/.env:
#   ADAPTION_API_KEY=pt_live_...
```

Create a key at **https://adaptionlabs.ai/app/settings?tab=api_keys**.

Then, in the UI (**Settings & Integrations**), press **Run Adaptive Data workflow** and
**Run local pipeline evaluation**. Without a key, the app keeps every other feature working
and shows honest setup instructions — it never fakes a successful integration and never
exposes the key to the frontend.

**Evaluation honesty:** the hand-labeled reference subset scores the pipeline on clear items
separately from ambiguous mixed reviews ("problem + resolution"), and the UI reports both.

---

## How the analysis pipeline works

1. **Import** (pandas) validates the CSV, preserves original text/category verbatim, flags
   duplicate texts, and stores analysis fields separately.
2. **Analyze** runs in a background thread with progress tracked in `analysis_jobs`:
   sentiment (VADER) and topic (lexicon) are computed once per unique text and reused for
   duplicates.
3. **Group** — unique texts are clustered with TF-IDF + agglomerative clustering into issue
   groups; every record inherits its text's cluster.
4. **Score & recommend** — each group is scored with the transparent formula and paired with
   an evidence-backed recommendation; results persist as issues with feedback links.

---

## Priority scoring

```
Priority Score = w1·Frequency + w2·NegativeRatio + w3·Severity + w4·Trend
```

Default weights: Frequency 35%, Negative 25%, Severity 25%, Trend 15% — adjustable live on
the **Settings** page, which re-scores all issues on save.

- **Trend** uses real timestamp data only. Without timestamps, its weight is **renormalized**
  across the remaining factors and the UI states which factors were used — nothing is invented.
- **Severity** blends topic severity with average sentiment magnitude.
- **Critical** requires score ≥ threshold **and** severity ≥ 0.70, so a frequent but mild
  complaint is never auto-labelled Critical.

---

## Testing

**Dataset tests** (all verified):

- Valid CSV → 7,000 rows imported, 6,680 duplicate texts preserved and flagged, 320 unique.
- Empty file → `422 The uploaded file is empty.`
- Malformed CSV (unclosed quote) → `422 CSV parsing failed: ... EOF inside string`
- Missing required columns → `422 Missing required column(s): category, review`

**Feedback tests:** manual submission is saved and auto-analyzed; search is case-insensitive
and partial-match; multiple filters combine; filters clear; pagination works (280 pages for
7,000 records).

**AI tests:** positive / negative / neutral / ambiguous reviews classified; similar complaints
grouped, unrelated ones not; evidence inspectable per issue.

**Dashboard tests:** KPIs match the database; charts reflect live data; no fabricated values;
sensible empty states when no records exist.

**Recommendation tests:** scores follow the configured formula; missing factors handled
transparently; recommendations cite real findings; evidence accessible.

**Issue-tracking tests:** save → status change → note → **backend restart** → all changes
persist (verified).

**Reporting tests:** CSV and PDF exports generated; statistics match the dataset; filtered
exports honored.

**Adaption tests:** integration status is honest; workflow runs when a key is present; local
pipeline evaluation runs without a key; failures recorded truthfully.

Run the seed to reproduce the dataset tests end-to-end:

```bash
cd insightflow && python scripts/seed.py
```

---

## Deployment

**Frontend build:**

```bash
cd insightflow/frontend
npm run build      # outputs static assets to dist/
```

Serve `dist/` from any static host (Netlify, Vercel, Cloudflare Pages, S3, nginx). Set
`VITE_API_BASE` (or configure the `/api` proxy) to point at the deployed backend origin.

**Backend:**

```bash
cd insightflow/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run behind a process manager (gunicorn/uvicorn workers) and a TLS-terminating reverse proxy.
Mount a persistent volume for `backend/data/` so the SQLite database survives restarts.
Set `INSIGHTFLOW_CORS_ORIGINS` to your frontend's production origin.

**Environment-only secret:** `ADAPTION_API_KEY` (and optional `INSIGHTFLOW_LLM_API_KEY`) are
read server-side from the environment; they are never sent to the browser.

---

## Demonstration guide

A ~5-minute path that showcases the full workflow:

1. **Overview** — show live KPIs (7,000 records, 320 unique, 6,680 duplicates preserved), the
   sentiment/category/topic charts, and the honest "no timestamps → no trend chart" note.
2. **Feedback Explorer** — show the table with original category vs. inferred topic side by
   side; search "scam"; apply a sentiment + priority filter; open a record's detail modal;
   submit a review manually and watch it get analyzed.
3. **AI Insights** — show the transparency banner, topic distribution, similarity groups with
   representative texts, and run the **pipeline evaluation** to show scored accuracy against
   the hand-labeled subset.
4. **Recommendations** — open the top Critical issue; expand **Evidence & details** to show
   the factor breakdown (frequency / negative / severity with weights), the evidence-grounded
   recommendation, the success metric, and the trend-unavailable note. Press **Track issue**.
5. **Issue Tracker** — the issue appears with its evidence; change status, add a note, resolve,
   reopen — then **restart the backend** to prove persistence.
6. **Reports** — generate a report, export **PDF** and **CSV**, copy the executive summary,
   and show the documented limitations section.
7. **Settings & Integrations** — adjust a priority weight and re-score; show the **Adaption**
   panel with honest status and setup steps (or a real run if a key is configured).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Frontend loads but no data | Ensure the backend is running on port 8000; the Vite dev server proxies `/api` there. |
| `ModuleNotFoundError` on backend start | `pip install -r backend/requirements.txt` |
| `column does not exist` / schema errors | Delete `backend/data/insightflow.db` and restart (tables are recreated). |
| Analysis stays pending | Check the backend logs; `GET /api/analytics/job` reports the current job status and message. |
| CSV rejected as invalid | Confirm it has `review` and `category` columns and is UTF-8/Latin-1 encoded. |
| Adaption run fails | Requires `ADAPTION_API_KEY`; the exact failing step and error are shown on the Settings page and stored in `adaption_runs`. |
| Trend chart missing | Expected without timestamps — the UI explains this; upload a CSV with a `timestamp`/`date` column to enable it. |

---

## License

Provided for the Build Battle 2026 hackathon submission.
