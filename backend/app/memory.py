"""Hindsight memory layer for RecallDesk.

Every Hindsight API call lives here. The rest of the app never touches the
memory client directly, which keeps the memory integration auditable in one
place and the rest of the code testable without a running Hindsight server.

All methods are async and use the client's `a`-prefixed async operations —
the sync client methods wrap asyncio.run() internally and fail with
"This event loop is already running" when called from an async context.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hindsight_client import Hindsight

log = logging.getLogger("recalldesk.memory")

CUSTOMER_MISSION = (
    "You are the complete support memory of {name} ({customer_id}), an SMB customer on "
    "the {plan} plan. Track every issue, its resolution, the customer's environment, and "
    "their frustration level."
)

PLAYBOOK_MISSION = (
    "You are the accumulated playbook of which solutions worked for which issue types "
    "across all customers. Prioritise proven resolutions over plausible ones."
)

CUSTOMER_DISPOSITION = {"skepticism": 2, "literalism": 2, "empathy": 4}
PLAYBOOK_DISPOSITION = {"skepticism": 3, "literalism": 3, "empathy": 2}

DIRECTIVES = [
    "Never promise a refund or credit without human approval — always say a specialist will confirm.",
    "Always cite the past ticket number when referencing previous issues.",
    "If the customer has been angry in two consecutive messages, recommend escalation.",
]

SEED_MARKER = "recalldesk-seed-marker-v1: seeding completed for this deployment."

# Cloud retention is processed asynchronously, so a just-retained marker is not
# visible via list_memories for several seconds. A local flag file makes
# seed idempotency immediate; delete it to force a reseed.
SEED_FLAG_PATH = Path(__file__).resolve().parents[2] / ".seeded"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _fact_type(item: Any) -> str:
    """Recall results use `type`; list_memories items use `fact_type`."""
    return (
        getattr(item, "type", None)
        or getattr(item, "fact_type", None)
        or "world"
    )


class MemoryLayer:
    """Thin async wrapper around the Hindsight client with graceful degradation.

    When Hindsight is unreachable every method degrades to a no-op return
    value instead of raising, so the support flow keeps working without
    memory and the UI can flag the degraded state.
    """

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._client = Hindsight(base_url=base_url, api_key=api_key)
        self._loop: asyncio.AbstractEventLoop | None = None
        self.available = True

    async def aclose(self) -> None:
        try:
            await self._client.aclose()
        except Exception:
            pass

    async def _ensure_loop_client(self) -> Hindsight:
        """Return a client bound to the CURRENT running event loop.

        The SDK's HTTP session binds to the event loop of its first call; when
        the app runs under a harness that spins a new loop per request (or the
        loop is recycled), calls fail with "Event loop is closed". Recreating
        the client whenever the running loop differs makes every context work.
        """
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            if self._client is not None:
                try:
                    await self._client.aclose()
                except Exception:
                    pass
            self._client = Hindsight(base_url=self._base_url, api_key=self._api_key)
            self._loop = loop
        return self._client

    async def ping(self) -> bool:
        client = await self._ensure_loop_client()
        try:
            await client.aget_version()
        except Exception as exc:
            self.available = False
            log.info("Hindsight ping failed: %s", exc)
            return False
        self.available = True
        return True

    async def _ensure_bank(
        self, bank_id: str, name: str, mission: str, disposition: dict[str, int]
    ) -> None:
        client = await self._ensure_loop_client()
        try:
            await client.acreate_bank(
                bank_id=bank_id, name=name, mission=mission, disposition=disposition
            )
        except Exception:
            # create_bank on an existing bank is not an error for us; the
            # recall/retain calls below surface real connectivity problems.
            log.debug("create_bank(%s) skipped or already exists", bank_id)

    async def ensure_customer_bank(self, customer_id: str, name: str, plan: str) -> str:
        bank_id = f"customer-{customer_id}"
        await self._ensure_bank(
            bank_id,
            name,
            CUSTOMER_MISSION.format(name=name, customer_id=customer_id, plan=plan),
            CUSTOMER_DISPOSITION,
        )
        return bank_id

    async def ensure_playbook_bank(self) -> str:
        await self._ensure_bank(
            "support-playbook", "Support Playbook", PLAYBOOK_MISSION, PLAYBOOK_DISPOSITION
        )
        return "support-playbook"

    async def recall_customer(self, customer_id: str, query: str) -> list[dict[str, Any]]:
        return await self._recall(f"customer-{customer_id}", query)

    async def recall_playbook(self, query: str) -> list[dict[str, Any]]:
        return await self._recall("support-playbook", query)

    async def _recall(self, bank_id: str, query: str) -> list[dict[str, Any]]:
        client = await self._ensure_loop_client()
        try:
            response = await client.arecall(
                bank_id=bank_id,
                query=query,
                types=["world", "observation", "experience"],
                budget="mid",
                max_tokens=4096,
            )
        except Exception as exc:
            self.available = False
            log.warning("recall(%s) failed: %s", bank_id, exc)
            return []
        self.available = True
        results: list[dict[str, Any]] = []
        for item in getattr(response, "results", None) or []:
            scores = getattr(item, "scores", None)
            if scores is not None:
                score = float(getattr(scores, "final", 0.0) or 0.0)
            else:
                score = float(getattr(item, "score", 0.0) or 0.0)
            results.append(
                {
                    "text": getattr(item, "text", ""),
                    "type": _fact_type(item),
                    "score": score,
                }
            )
        return results

    async def retain_fact(
        self, bank_id: str, content: str, context: str, timestamp: datetime
    ) -> None:
        client = await self._ensure_loop_client()
        try:
            await client.aretain(
                bank_id=bank_id,
                content=content,
                context=context,
                timestamp=timestamp,
                document_id="seed-data",
            )
        except Exception as exc:
            self.available = False
            log.warning("retain(%s) failed: %s", bank_id, exc)
            raise

    async def remember_exchange(
        self,
        customer_id: str,
        user_message: str,
        assistant_reply: str,
        session_id: str,
        frustration: str,
    ) -> bool:
        """Retain a live chat exchange with real timestamps (the cross-session memory)."""
        client = await self._ensure_loop_client()
        try:
            await client.aretain(
                bank_id=f"customer-{customer_id}",
                content=f"Customer: {user_message}\nSupport agent: {assistant_reply}",
                context=f"live chat, frustration={frustration}",
                timestamp=_utcnow(),
                document_id=f"chat-{session_id}",
                metadata={"frustration": frustration, "channel": "recalldesk-web"},
            )
        except Exception as exc:
            self.available = False
            log.warning("retain(customer-%s) failed: %s", customer_id, exc)
            return False
        return True

    async def sandbox_retain(self, user_message: str, assistant_reply: str) -> None:
        """Store the exchange in a throwaway bank so nothing persists (memory-off demo)."""
        client = await self._ensure_loop_client()
        try:
            await client.aretain(
                bank_id=f"sandbox-{uuid.uuid4()}",
                content=f"Customer: {user_message}\nSupport agent: {assistant_reply}",
                context="memory-off demo",
                timestamp=_utcnow(),
            )
        except Exception as exc:
            log.debug("sandbox retain skipped: %s", exc)

    async def customer_memory_snapshot(self, customer_id: str) -> dict[str, Any]:
        """Observations (consolidated beliefs) + raw memories for the Memory Lens panel."""
        client = await self._ensure_loop_client()
        observations: list[dict[str, Any]] = []
        memories: list[dict[str, Any]] = []
        try:
            response = await client.arecall(
                bank_id=f"customer-{customer_id}",
                query="all known issues, resolutions, preferences and history",
                types=["observation"],
                budget="high",
                max_tokens=4096,
            )
            for item in getattr(response, "results", None) or []:
                src_ids = getattr(item, "source_fact_ids", None)
                proof = len(src_ids) if src_ids else 1
                observations.append(
                    {
                        "text": getattr(item, "text", ""),
                        "proof_count": int(proof),
                    }
                )
            listed = await client.alist_memories(
                bank_id=f"customer-{customer_id}", limit=100
            )
            items = getattr(listed, "items", None) or getattr(listed, "memories", None) or []
            for item in items:
                memories.append(
                    {
                        "text": getattr(item, "text", ""),
                        "type": _fact_type(item),
                    }
                )
        except Exception as exc:
            self.available = False
            log.warning("memory snapshot failed: %s", exc)
        return {"observations": observations, "memories": memories, "count": len(memories)}

    async def is_seeded(self) -> bool:
        if SEED_FLAG_PATH.exists():
            return True
        try:
            # Hindsight's extraction rewrites stored text, so the raw marker
            # string does not survive; match on the extracted wording instead.
            client = await self._ensure_loop_client()
            listed = await client.alist_memories(bank_id="support-playbook", limit=100)
            for item in getattr(listed, "items", None) or []:
                text = (getattr(item, "text", "") or "").lower()
                if "deployment completed" in text or "seeding completed" in text:
                    return True
            return False
        except Exception:
            return False

    async def mark_seeded(self) -> None:
        try:
            SEED_FLAG_PATH.write_text("seeded", encoding="utf-8")
        except Exception as exc:
            log.warning("seed flag write failed: %s", exc)
