"""Hindsight memory layer for RecallDesk.

Every Hindsight API call lives here. The rest of the app never touches the
memory client directly, which keeps the memory integration auditable in one
place and the rest of the code testable without a running Hindsight server.
"""

import logging
import uuid
from datetime import datetime, timezone
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MemoryLayer:
    """Thin wrapper around the Hindsight client with graceful degradation.

    When Hindsight is unreachable every method degrades to a no-op return
    value instead of raising, so the support flow keeps working without
    memory and the UI can flag the degraded state.
    """

    def __init__(self, base_url: str) -> None:
        self._client = Hindsight(base_url=base_url)
        self.available = True

    def ping(self) -> bool:
        try:
            self._client.get_version()
        except Exception as exc:
            self.available = False
            log.info("Hindsight ping failed: %s", exc)
            return False
        self.available = True
        return True

    def _ensure_bank(self, bank_id: str, name: str, mission: str, disposition: dict[str, int]) -> None:
        try:
            self._client.create_bank(
                bank_id=bank_id, name=name, mission=mission, disposition=disposition
            )
        except Exception:
            # create_bank on an existing bank is not an error for us; the
            # recall/retain calls below surface real connectivity problems.
            log.debug("create_bank(%s) skipped or already exists", bank_id)

    def ensure_customer_bank(self, customer_id: str, name: str, plan: str) -> str:
        bank_id = f"customer-{customer_id}"
        self._ensure_bank(
            bank_id,
            name,
            CUSTOMER_MISSION.format(name=name, customer_id=customer_id, plan=plan),
            CUSTOMER_DISPOSITION,
        )
        return bank_id

    def ensure_playbook_bank(self) -> str:
        self._ensure_bank(
            "support-playbook", "Support Playbook", PLAYBOOK_MISSION, PLAYBOOK_DISPOSITION
        )
        return "support-playbook"

    def recall_customer(self, customer_id: str, query: str) -> list[dict[str, Any]]:
        return self._recall(f"customer-{customer_id}", query)

    def recall_playbook(self, query: str) -> list[dict[str, Any]]:
        return self._recall("support-playbook", query)

    def _recall(self, bank_id: str, query: str) -> list[dict[str, Any]]:
        try:
            response = self._client.recall(
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
            results.append(
                {
                    "text": getattr(item, "text", ""),
                    "type": getattr(item, "type", "world") or "world",
                    "score": float(getattr(item, "score", 0.0) or 0.0),
                }
            )
        return results

    def retain_fact(
        self, bank_id: str, content: str, context: str, timestamp: datetime
    ) -> None:
        try:
            self._client.retain(
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

    def remember_exchange(
        self,
        customer_id: str,
        user_message: str,
        assistant_reply: str,
        session_id: str,
        frustration: str,
    ) -> bool:
        """Retain a live chat exchange with real timestamps (the cross-session memory)."""
        try:
            self._client.retain(
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

    def sandbox_retain(self, user_message: str, assistant_reply: str) -> None:
        """Store the exchange in a throwaway bank so nothing persists (memory-off demo)."""
        try:
            self._client.retain(
                bank_id=f"sandbox-{uuid.uuid4()}",
                content=f"Customer: {user_message}\nSupport agent: {assistant_reply}",
                context="memory-off demo",
                timestamp=_utcnow(),
            )
        except Exception as exc:
            log.debug("sandbox retain skipped: %s", exc)

    def customer_memory_snapshot(self, customer_id: str) -> dict[str, Any]:
        """Observations (consolidated beliefs) + raw memories for the Memory Lens panel."""
        observations: list[dict[str, Any]] = []
        memories: list[dict[str, Any]] = []
        try:
            response = self._client.recall(
                bank_id=f"customer-{customer_id}",
                query="all known issues, resolutions, preferences and history",
                types=["observation"],
                budget="high",
                max_tokens=4096,
            )
            for item in getattr(response, "results", None) or []:
                observations.append(
                    {
                        "text": getattr(item, "text", ""),
                        "proof_count": int(getattr(item, "proof_count", 1) or 1),
                    }
                )
            listed = self._client.list_memories(
                bank_id=f"customer-{customer_id}", limit=100
            )
            for item in getattr(listed, "memories", listed) or []:
                memories.append(
                    {
                        "text": getattr(item, "text", ""),
                        "type": getattr(item, "type", "world") or "world",
                    }
                )
        except Exception as exc:
            self.available = False
            log.warning("memory snapshot failed: %s", exc)
        return {"observations": observations, "memories": memories, "count": len(memories)}

    def is_seeded(self) -> bool:
        try:
            listed = self._client.list_memories(
                bank_id="support-playbook", search_query="recalldesk-seed-marker-v1", limit=5
            )
            return bool(getattr(listed, "memories", listed))
        except Exception:
            return False

    def mark_seeded(self) -> None:
        try:
            self._client.retain(
                bank_id="support-playbook",
                content=SEED_MARKER,
                context="seed marker",
                timestamp=_utcnow(),
            )
        except Exception as exc:
            log.warning("seed marker retain failed: %s", exc)
