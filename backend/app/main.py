"""RecallDesk API — a support copilot with perfect recall, powered by Hindsight.

Endpoints follow the contract in the README:
  POST /chat                        — support reply with memory on/off
  GET  /customer/{id}/memory        — Memory Lens data (observations + raw history)
  POST /seed                        — idempotent synthetic data loader
  GET  /health                      — Hindsight + LLM status
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .llm import LLM
from .memory import CUSTOMER_MISSION, DIRECTIVES, PLAYBOOK_MISSION, MemoryLayer
from .seed import CUSTOMERS, seed

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("recalldesk.main")

load_dotenv()

HINDSIGHT_API_URL = os.getenv("HINDSIGHT_API_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY") or None
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

memory = MemoryLayer(base_url=HINDSIGHT_API_URL, api_key=HINDSIGHT_API_KEY)
llm = LLM(api_key=GROQ_API_KEY, model=LLM_MODEL)

app = FastAPI(title="RecallDesk", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict[str, dict[str, Any]] = {}

ANGRY_WORDS = {"angry", "furious", "ridiculous", "unacceptable", "worst", "terrible", "useless"}
FRUSTRATION_WORDS = {"again", "still", "broken", "waiting", "nothing", "slow", "failed", "third"}


def _session(customer_id: str) -> dict[str, Any]:
    return sessions.setdefault(
        customer_id,
        {"history": [], "consecutive_angry": 0, "session_id": uuid.uuid4().hex[:12]},
    )


def _classify_frustration(message: str) -> str:
    """Cheap heuristic first; the LLM classifier is only used for ambiguous cases."""
    words = set(message.lower().split())
    if words & ANGRY_WORDS or "!!" in message:
        return "angry"
    if words & FRUSTRATION_WORDS:
        return "frustrated"
    if any(word.isupper() and len(word) > 3 for word in message.split()):
        return "angry"
    return "calm"


def _customer_identity(customer_id: str) -> tuple[str, str]:
    for customer in CUSTOMERS:
        if customer["customer_id"] == customer_id:
            return customer["name"], customer["plan"]
    return customer_id, "unspecified"


def _memory_system_prompt(
    customer_id: str,
    name: str,
    plan: str,
    history_hits: list[dict[str, Any]],
    playbook_hits: list[dict[str, Any]],
    frustration: str,
) -> str:
    lines = [
        CUSTOMER_MISSION.format(name=name, customer_id=customer_id, plan=plan),
        f"Current customer frustration level: {frustration}.",
        "",
        "MEMORIES RECALLED FOR THIS CUSTOMER (most relevant first):",
    ]
    if history_hits:
        for i, m in enumerate(history_hits, 1):
            lines.append(f"{i}. [{m['type']}] {m['text']}")
    else:
        lines.append(
            "(none — likely first contact; say you'll note the details and ask what happened)"
        )
    lines.extend(["", "CROSS-CUSTOMER PLAYBOOK (what has worked before):"])
    if playbook_hits:
        for i, m in enumerate(playbook_hits, 1):
            lines.append(f"{i}. {m['text']}")
    else:
        lines.append("(no playbook hits)")
    lines.extend(
        [
            "",
            "RULES:",
            *DIRECTIVES,
            "Cite ticket numbers from memory when they exist. Be brief, warm, and specific. Never invent history.",
        ]
    )
    return "\n".join(lines)


def _generic_system_prompt() -> str:
    return (
        "You are a generic support chatbot with no memory of past conversations. "
        "You know nothing about this customer. Greet them, ask them to describe "
        "their issue from scratch, and ask clarifying questions. Do not mention "
        "any previous tickets, past issues, or history. Keep replies to 2-4 sentences."
    )


class ChatRequest(BaseModel):
    customer_id: str
    message: str
    memory_mode: str = Field(default="on", pattern="^(on|off)$")


class MemoryUsed(BaseModel):
    text: str
    type: str
    score: float


class ChatResponse(BaseModel):
    reply: str
    memories_used: list[MemoryUsed]
    frustration: str
    retained: bool
    playbook_used: list[MemoryUsed] = []
    degraded: bool = False


class SeedResponse(BaseModel):
    customers: list[str]
    playbook_facts: int
    skipped: bool = False


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    state = _session(req.customer_id)
    detected = _classify_frustration(req.message)
    if detected == "angry":
        state["consecutive_angry"] += 1
        frustration = "angry" if state["consecutive_angry"] >= 2 else "frustrated"
    else:
        state["consecutive_angry"] = 0
        frustration = detected

    name, plan = _customer_identity(req.customer_id)
    degraded = not llm.available

    if req.memory_mode == "on":
        history_hits = memory.recall_customer(req.customer_id, req.message)
        playbook_hits = memory.recall_playbook(req.message)
        system_prompt = _memory_system_prompt(
            req.customer_id, name, plan, history_hits, playbook_hits, frustration
        )
        reply = llm.support_reply(system_prompt, state["history"], req.message)
        retained = memory.remember_exchange(
            req.customer_id, req.message, reply, state["session_id"], frustration
        )
    else:
        history_hits, playbook_hits = [], []
        system_prompt = _generic_system_prompt()
        reply = llm.support_reply(system_prompt, [], req.message)
        memory.sandbox_retain(req.message, reply)
        retained = False

    state["history"].append({"role": "user", "content": req.message})
    state["history"].append({"role": "assistant", "content": reply})

    return ChatResponse(
        reply=reply,
        memories_used=[MemoryUsed(**m) for m in history_hits],
        frustration=frustration,
        retained=retained,
        playbook_used=[MemoryUsed(**m) for m in playbook_hits],
        degraded=degraded or not memory.available,
    )


@app.get("/customer/{customer_id}/memory")
def customer_memory(customer_id: str) -> dict[str, Any]:
    snapshot = memory.customer_memory_snapshot(customer_id)
    return {"customer_id": customer_id, **snapshot}


@app.post("/seed", response_model=SeedResponse)
def run_seed() -> SeedResponse:
    if not memory.ping():
        raise HTTPException(
            status_code=503,
            detail="Hindsight is unreachable at HINDSIGHT_API_URL; start it with 'hindsight-api' first.",
        )
    return SeedResponse(**seed(memory))


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "hindsight": "up" if memory.ping() else "down",
        "llm": "up" if llm.available else "down",
    }


frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    log.warning("frontend/ not found at %s — the UI will not be served", frontend_dir)
