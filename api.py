import json
import logging
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
app = FastAPI(title="AI Trends Research Agent", version="1.0.0")

_running = False


def _run_agent_task(max_ideas: int):
    global _running
    _running = True
    try:
        from src.agents.trends_agent import TrendsAgent
        with TrendsAgent() as agent:
            agent.run(max_ideas=max_ideas)
    except Exception as e:
        logger.error(f"Agent task failed: {e}")
    finally:
        _running = False


@app.get("/")
def root():
    return {"status": "ok", "service": "AI Trends Research Agent"}


@app.get("/health")
def health():
    return {"status": "healthy", "agent_running": _running}


@app.post("/run")
def trigger_run(background_tasks: BackgroundTasks, max_ideas: int = 10):
    global _running
    if _running:
        raise HTTPException(status_code=409, detail="Agent already running")
    background_tasks.add_task(_run_agent_task, max_ideas)
    return {"message": "Agent started", "max_ideas": max_ideas}


@app.get("/results/latest")
def get_latest():
    latest = Path("outputs/json/latest.json")
    if not latest.exists():
        raise HTTPException(status_code=404, detail="No results yet")
    return JSONResponse(content=json.loads(latest.read_text()))


@app.get("/results/list")
def list_results():
    output_dir = Path("outputs/json")
    if not output_dir.exists():
        return {"files": []}
    files = sorted(
        [f.name for f in output_dir.glob("trends_*.json")],
        reverse=True,
    )
    return {"files": files, "total": len(files)}
