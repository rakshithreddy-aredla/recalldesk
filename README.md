# RecallDesk

A customer support copilot with perfect recall, powered by [Hindsight](https://github.com/vectorize-io/hindsight) agent memory.

Stateless chatbots make customers repeat their story on every contact. RecallDesk never forgets: it retains every conversation with real timestamps, recalls each customer's full history through four parallel search strategies, and consolidates cross-customer learnings into a playbook — so repeat issues are resolved in seconds instead of re-explained from scratch.

## Quick start

**Prerequisites:** Python 3.11+, a [Groq](https://groq.com/) API key (free tier works), and a running Hindsight server.

1. Install dependencies:

```powershell
# Windows PowerShell
pip install -r backend/requirements.txt
```

```bash
# macOS / Linux
pip install -r backend/requirements.txt
```

2. Start the Hindsight memory server (terminal 1):

```bash
pip install hindsight-api
export OPENAI_API_KEY=sk-xxx            # Hindsight's internal extractor needs an LLM key
export HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY
hindsight-api                            # serves http://localhost:8888
```

Alternatively use [Hindsight Cloud](https://ui.hindsight.vectorize.io) and point `HINDSIGHT_API_URL` at your instance.

3. Configure and start RecallDesk (terminal 2):

```powershell
# Windows PowerShell
copy backend\.env.example backend\.env   # then edit: GROQ_API_KEY=gsk-xxx
Set-Location backend
uvicorn app.main:app --port 8000
```

```bash
# macOS / Linux
cp backend/.env.example backend/.env     # then edit: GROQ_API_KEY=gsk-xxx
cd backend
uvicorn app.main:app --port 8000
```

4. Open http://localhost:8000, click **Run demo scenario** (or seed first via `POST /seed`).

## Architecture

```
                 ┌─────────────────────────────┐
                 │   Chat UI (vanilla JS)      │
                 │   chat + Memory Lens panel  │
                 └──────────────┬──────────────┘
                                │ JSON
                 ┌──────────────▼──────────────┐
                 │   FastAPI backend           │
                 │   frustration + prompts     │──────────┐
                 └──────┬──────────────┬───────┘          │
                        │ retain/recall│                  │ reply
                        │              │           ┌──────▼──────┐
        ┌───────────────▼───┐   ┌──────▼────────┐  │ Groq LLM    │
        │ Hindsight         │   │ Hindsight     │  └─────────────┘
        │ customer-* banks  │   │ support-      │
        │ (full history,    │   │ playbook bank │
        │  real timestamps) │   │ (what worked) │
        └───────────────────┘   └───────────────┘
```

- **Chat UI** — chat panel plus a "Memory Lens" inspector that shows what was recalled, what beliefs have consolidated, and a memory ON/OFF toggle for the before/after demo.
- **FastAPI backend** — builds prompts from recalled memory, classifies frustration, retains every exchange, and degrades gracefully when Hindsight or the LLM is down.
- **Hindsight memory banks** — per-customer banks plus one cross-customer playbook bank; all memory operations go through `backend/app/memory.py`.
- **Groq LLM** — generates support replies from the memory-grounded prompt, with retries and a fallback reply.

## How Hindsight memory is used

Memory is not a feature of RecallDesk — it is the product. The integration is explicit and auditable in one file (`backend/app/memory.py`):

1. **Per-customer memory banks** (`customer-<id>`). Every chat exchange is retained with real timestamps, the customer's frustration level, and a session document ID. Each bank has a mission ("You are the complete support memory of Priya Sharma…"), directives ("Never promise a refund without human approval", "Always cite the past ticket number"), and a disposition (high empathy).
2. **Four-way retrieval per query.** Hindsight's TEMPR recall runs semantic, keyword, graph, and temporal search in parallel — so a message like "it broke AGAIN" finds last month's incident, not just semantically similar text. Recall results (text, type, score) are surfaced live in the Memory Lens panel.
3. **Cross-customer playbook bank** (`support-playbook`). Experience facts of which solutions worked for which issue types ("billing double-charge complaints resolved by specialist-approved credit within 24h, 3 of 3 customers"). The agent learns from other customers' outcomes, not just this customer's history.
4. **Auto-consolidated observations.** Hindsight's worker merges repeated facts into evidence-grounded observations with source counts — visible in the Memory Lens "Observations" tab as beliefs like "resolved → 2 sources".
5. **Memory ON/OFF before/after demo.** With memory off, the agent retains nothing and replies from a deliberately generic prompt (asks the customer to re-explain). With memory on, it cites the exact past ticket and its resolution status instantly. The toggle makes the memory's value obvious within seconds.

## Judging-criteria mapping

| Criterion | Weight | Where it lives |
|---|---|---|
| Innovation | 30% | Two-level memory: per-customer banks + cross-customer playbook |
| Use of Hindsight Memory | 25% | `backend/app/memory.py`, Memory Lens panel, ON/OFF toggle |
| Technical Implementation | 20% | FastAPI structure, retries/fallbacks, pytest suite |
| User Experience | 15% | Chat + Memory Lens UI, scripted demo scenario button |
| Real-world Impact | 10% | Realistic synthetic data (names, ticket IDs, invoices, timestamps) |

## Repository layout

| Path | What it is |
|---|---|
| `backend/app/main.py` | FastAPI app, endpoints, prompt assembly, session state |
| `backend/app/memory.py` | All Hindsight calls (retain/recall/reflect/banks) |
| `backend/app/llm.py` | Groq wrapper with retries and fallback reply |
| `backend/app/seed.py` | Synthetic customers + playbook seeder |
| `frontend/` | Chat UI + Memory Lens (vanilla HTML/CSS/JS) |
| `tests/test_api.py` | Integration tests against a live server |
| `docs/demo-script.md` | 3-minute video demo script |
| `docs/submission-checklist.md` | Final deliverables checklist |

## Testing

```bash
pip install pytest httpx
# with the API running:
pytest tests/test_api.py -v
# without the API running, tests skip cleanly and still pass
```

## License

MIT
