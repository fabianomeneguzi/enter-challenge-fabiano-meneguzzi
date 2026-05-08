# Enter Challenge — Portfolio Letter Generator

This repo generates an XP-style monthly letter by combining:

- **Client input files** (portfolio, risk profile, macro notes)
- **Live market/benchmark data** (Yahoo Finance + BACEN)
- **Rivet workflows** (LLM extraction + letter writing)
- **Python analytics** (returns table, chart, recommendations)

You can run it either as a **web app** (FastAPI) or as a **batch script** (`main.py`).

---

## Requirements

- **Python 3.10+**
- **Node.js (LTS)** + npm (Rivet runs via Node)
- (Optional) Git

---

## Setup

### 1) Install Python deps

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Install Node deps

```bash
npm install
```

### 3) Configure environment variables

Create a local `.env` (do **not** commit it):

```bash
copy .env.example .env
```

Set:

- **`OPENAI_API_KEY`**: required for Rivet graphs and the optional AI rewrite endpoint

If deploying (see `render.yaml`), you may also configure:

- `SESSION_SECRET`
- `ADVISOR_LOGIN_EMAIL`
- `ADVISOR_LOGIN_PASSWORD`

---

## Run the project

### Option A — Web app (recommended)

```bash
uvicorn api_server:app --reload --port 8000
```

Open `http://127.0.0.1:8000`.

### Option B — Batch pipeline

```bash
python main.py
```

This runs the full pipeline end-to-end for the **first client** in `clients.json`.

---

## Key inputs

### `clients.json`

Defines which files to use for each client:

- **`portfolio_file`**: the portfolio text used by Rivet to extract positions
- **`risk_file`**: risk profile text used by Rivet
- **`macro_file`**: macro notes text passed to Rivet

If someone clones the repo, they must ensure these referenced files exist (same repo folder or absolute paths).

### Rivet project

- **`Enter Challenge.rivet-project`**: the Rivet graph definitions

---

## Outputs (generated files)

All generated artifacts are written under **`outputs/`**.

### Produced by Rivet (Node)

- **`outputs/positions.json`**: extracted portfolio holdings used by Python calculations
- **`outputs/risk_profile.json`**: extracted risk profile
- **`outputs/letter.json`**: final letter sections (greeting / portfolio / macro_and_risk)

### Produced by Python

- **`outputs/portfolio_returns.csv`**: returns table (holdings + watchlist + portfolio + CDI row)
- **`outputs/performance_summary.json`**: condensed table used as `performance_data` input to Rivet  
  (Watchlist rows are removed here to reduce mistakes in the LLM prompt.)
- **`outputs/performance_chart.png`**: chart image used by the web preview and DOCX export
- **`outputs/macro_news.json`**: macro headlines pulled from DuckDuckGo (cached for 1 day)
- **`outputs/recommendations.json`**: structured recommendation payload used as `recommendations` input to Rivet
- **`outputs/Client_Letter_<timestamp>.docx`**: final Word document export

---

## How the Rivet connection works

Rivet is executed through Node:

- `rivet_runner.py` runs `node run_workflows.js <graph_name> [client_id]`
- `run_workflows.js` loads `Enter Challenge.rivet-project` and runs one of:
  - `extract_positions` → writes `outputs/positions.json`
  - `extract_riskprofile` → writes `outputs/risk_profile.json`
  - `main_challenge` → reads `outputs/performance_summary.json`, `outputs/macro_news.json`, `outputs/recommendations.json` and writes `outputs/letter.json`

---

## What each main file does

- **`api_server.py`**: FastAPI backend + SSE pipeline runner + serves frontend and generated assets
- **`frontend/index.html`**: single-page UI that calls the API endpoints
- **`main.py`**: batch runner that executes the whole pipeline locally
- **`rivet_runner.py`**: Python → Node bridge for Rivet graphs (`node run_workflows.js ...`)
- **`run_workflows.js`**: Node runner that invokes Rivet graphs and writes JSON outputs
- **`returns_calculator.py`**: computes monthly returns, portfolio aggregation, CDI benchmark row, and writes CSV/summary JSON
- **`chart_generator.py`**: generates `outputs/performance_chart.png` from the raw returns table
- **`macro_researcher.py`**: fetches and caches macro headlines → `outputs/macro_news.json`
- **`recommender.py`**: builds a structured `outputs/recommendations.json` using **last-month-only** stock signals + context flags
- **`document_generator.py`**: renders a DOCX using `outputs/letter.json` + chart image (requires a template at `templates/letter_template.docx`)

---

## Troubleshooting

- **Rivet fails / Node not found**: install Node.js and ensure `node` is on PATH.
- **No `outputs/positions.json`**: run the pipeline (`/generate/...` in web UI or `python main.py`) to produce it.
- **DOCX fails**: ensure `templates/letter_template.docx` exists at the expected path.

