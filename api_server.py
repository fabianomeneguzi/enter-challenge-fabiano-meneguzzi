"""
api_server.py
FastAPI application — thin HTTP layer on top of the existing pipeline.

Run with:  uvicorn api_server:app --reload --port 8000
"""

import asyncio
import json
import os
import sys
import io
from functools import partial

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── Internal modules (existing backend) ──────────────────────────────────────
from rivet_runner import run_rivet_workflows
from returns_calculator import generate_returns_csv
from chart_generator import generate_performance_chart
from macro_researcher import fetch_macro_news
from recommender import generate_recommendations
from document_generator import generate_document

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="XP Advisor Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# ── Pydantic models ───────────────────────────────────────────────────────────
class AIEditRequest(BaseModel):
    section: str          # "greeting" | "portfolio" | "macro_and_risk"
    current_text: str
    instruction: str


class LetterSaveRequest(BaseModel):
    greeting: str
    portfolio: str
    macro_and_risk: str


# ── Helpers ───────────────────────────────────────────────────────────────────
CLIENTS_FILE = "clients.json"
LETTER_FILE = "outputs/letter.json"
CHART_FILE = "outputs/performance_chart.png"
PERFORMANCE_FILE = "outputs/performance_summary.json"


def load_clients() -> list:
    with open(CLIENTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_client(client_id: str) -> dict:
    clients = load_clients()
    for c in clients:
        if c["id"] == client_id:
            return c
    raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")


def load_letter() -> dict:
    if not os.path.exists(LETTER_FILE):
        raise HTTPException(status_code=404, detail="Letter not yet generated")
    with open(LETTER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_letter(data: dict):
    os.makedirs("outputs", exist_ok=True)
    with open(LETTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sse_event(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")


@app.get("/clients")
async def list_clients():
    """Returns all available clients with their portfolio metadata."""
    clients = load_clients()

    # Enrich with last-generated date if letter exists
    letter_exists = os.path.exists(LETTER_FILE)
    perf_exists = os.path.exists(PERFORMANCE_FILE)

    aum = None
    last_return = None
    if perf_exists:
        with open(PERFORMANCE_FILE, "r", encoding="utf-8") as f:
            perf = json.load(f)
        # Find global portfolio row
        for row in perf:
            if row.get("Name") == "Global Portfolio Return":
                aum = row.get("Value")
                last_return = row.get("Last Month Return")
                break

    enriched = []
    for c in clients:
        enriched.append({
            **c,
            "letter_ready": letter_exists,
            "aum": aum,
            "last_month_return": last_return
        })
    return enriched


@app.get("/generate/{client_id}")
async def generate_letter(client_id: str):
    """
    Streams Server-Sent Events reporting pipeline progress.
    The browser reads this as an EventSource.
    """
    client = get_client(client_id)  # validates existence

    async def run_pipeline():
        loop = asyncio.get_event_loop()


        # Step 1
        label = "Extraindo posições do portfólio"
        yield sse_event({"step": label, "status": "running"})
        try:
            ok = await loop.run_in_executor(
                None, partial(run_rivet_workflows, "extract_positions", client_id)
            )
            yield sse_event({"step": label, "status": "done" if ok else "error"})
            if not ok:
                yield sse_event({"step": "pipeline", "status": "failed", "detail": "extract_positions failed"})
                return
        except Exception as e:
            yield sse_event({"step": label, "status": "error", "detail": str(e)})
            return

        # Step 2
        label = "Extraindo perfil de risco"
        yield sse_event({"step": label, "status": "running"})
        try:
            ok = await loop.run_in_executor(
                None, partial(run_rivet_workflows, "extract_riskprofile", client_id)
            )
            yield sse_event({"step": label, "status": "done" if ok else "error"})
        except Exception as e:
            yield sse_event({"step": label, "status": "error", "detail": str(e)})
            return

        # Step 3
        label = "Calculando retornos e buscando dados de mercado"
        yield sse_event({"step": label, "status": "running"})
        try:
            chart_data = await loop.run_in_executor(None, generate_returns_csv)
            yield sse_event({"step": label, "status": "done"})
        except Exception as e:
            yield sse_event({"step": label, "status": "error", "detail": str(e)})
            return

        # Step 4
        label = "Gerando gráfico de performance"
        yield sse_event({"step": label, "status": "running"})
        try:
            await loop.run_in_executor(None, generate_performance_chart, chart_data)
            yield sse_event({"step": label, "status": "done"})
        except Exception as e:
            yield sse_event({"step": label, "status": "error", "detail": str(e)})
            return

        # Step 5
        label = "Pesquisando notícias macroeconômicas"
        yield sse_event({"step": label, "status": "running"})
        try:
            await loop.run_in_executor(None, fetch_macro_news)
            yield sse_event({"step": label, "status": "done"})
        except Exception as e:
            yield sse_event({"step": label, "status": "error", "detail": str(e)})
            return

        # Step 6
        label = "Gerando recomendações quantitativas"
        yield sse_event({"step": label, "status": "running"})
        try:
            await loop.run_in_executor(None, generate_recommendations)
            yield sse_event({"step": label, "status": "done"})
        except Exception as e:
            yield sse_event({"step": label, "status": "error", "detail": str(e)})
            return

        # Step 7
        label = "Redigindo a carta final"
        yield sse_event({"step": label, "status": "running"})
        try:
            ok = await loop.run_in_executor(
                None, partial(run_rivet_workflows, "main_challenge", client_id)
            )
            yield sse_event({"step": label, "status": "done" if ok else "error"})
            if not ok:
                yield sse_event({"step": "pipeline", "status": "failed", "detail": "main_challenge failed"})
                return
        except Exception as e:
            yield sse_event({"step": label, "status": "error", "detail": str(e)})
            return

        # All done
        yield sse_event({"step": "pipeline", "status": "complete"})

    return StreamingResponse(
        run_pipeline(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/letter")
async def get_letter():
    """Returns the current letter.json content."""
    return load_letter()


@app.put("/letter")
async def update_letter(body: LetterSaveRequest):
    """Saves manual edits back to letter.json."""
    data = body.dict()
    save_letter(data)
    return {"success": True}


@app.get("/chart")
async def get_chart():
    """Serves the performance chart PNG."""
    if not os.path.exists(CHART_FILE):
        raise HTTPException(status_code=404, detail="Chart not generated yet")
    return FileResponse(
        CHART_FILE,
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/performance")
async def get_performance():
    """Returns performance_summary.json."""
    if not os.path.exists(PERFORMANCE_FILE):
        raise HTTPException(status_code=404, detail="Performance data not available")
    with open(PERFORMANCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/download-docx")
async def download_docx(client_id: str | None = None):
    """Generates the .docx from current letter data and serves it for download."""
    loop = asyncio.get_event_loop()
    client = None
    if client_id:
        try:
            client = get_client(client_id)
        except HTTPException:
            client = None

    def _run():
        return generate_document(client)

    docx_path = await loop.run_in_executor(None, _run)
    if not docx_path or not os.path.exists(docx_path):
        raise HTTPException(status_code=500, detail="Falha ao gerar o documento Word")
    filename = os.path.basename(docx_path)
    return FileResponse(
        docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@app.post("/letter/ai-edit")
async def ai_edit_section(body: AIEditRequest):
    """
    Rewrites a single letter section using OpenAI.
    Accepts: { section, current_text, instruction }
    Returns: { rewritten_text }
    """
    import openai

    api_key = os.getenv("OPENAI_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

    client_oai = openai.OpenAI(api_key=api_key)

    section_labels = {
        "greeting": "saudação inicial",
        "portfolio": "análise de portfólio",
        "macro_and_risk": "análise macroeconômica e recomendações",
    }
    section_label = section_labels.get(body.section, body.section)

    system_prompt = (
        "Você é um redator especialista em comunicação financeira institucional de alto padrão, "
        "escrevendo para a XP Investimentos. "
        "Seu texto deve ser profissional, preciso, empático e em Português Brasileiro formal. "
        "Retorne APENAS o texto reescrito, sem prefácio, sem aspas, sem comentários extras."
    )

    user_prompt = (
        f"Reescreva o seguinte trecho de '{section_label}' de uma carta de investimentos, "
        f"aplicando esta instrução: '{body.instruction}'.\n\n"
        f"Texto original:\n{body.current_text}"
    )

    loop = asyncio.get_event_loop()

    def call_openai():
        response = client_oai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1200,
        )
        return response.choices[0].message.content.strip()

    try:
        rewritten = await loop.run_in_executor(None, call_openai)
        return {"rewritten_text": rewritten}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

