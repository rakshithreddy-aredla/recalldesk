"""Synthetic seed data: four customers with multi-week histories plus the playbook.

Data realism is a scored criterion, so every fact carries real-sounding names,
ticket IDs, invoice numbers, and dates spanning Aug–Sep 2026.
"""

import logging
from datetime import datetime

from .memory import MemoryLayer

log = logging.getLogger("recalldesk.seed")

CUSTOMERS: list[dict] = [
    {
        "customer_id": "cust-1042",
        "name": "Priya Sharma",
        "plan": "Growth",
        "facts": [
            (
                "Aug 12: Priya reported invoice #4821 was double-charged Rs 2,499. A specialist approved a credit; it was refunded within one day.",
                "billing issue",
                datetime(2026, 8, 12),
            ),
            (
                "Aug 12: Agent suggested Priya enable invoice email notifications; she said she prefers the dashboard.",
                "preference",
                datetime(2026, 8, 12),
            ),
            (
                "Sep 2: Priya could not download invoice PDFs; the download button fails on app v2.4.0. Tracked as ticket #4837.",
                "technical issue",
                datetime(2026, 9, 2),
            ),
            (
                "Sep 28: Priya returned angry about a renewal charge on Sep 27 and the invoice download still being broken.",
                "billing + technical",
                datetime(2026, 9, 28),
            ),
        ],
    },
    {
        "customer_id": "cust-1043",
        "name": "Arjun Patel",
        "plan": "Starter",
        "facts": [
            (
                "Aug 20: Arjun hit API rate limits (429s) on the Starter plan during load tests; ticket #4701.",
                "technical issue",
                datetime(2026, 8, 20),
            ),
            (
                "Aug 21: Upgrading to the Growth plan raised his limits and resolved the 429s; he confirmed all clear.",
                "technical issue",
                datetime(2026, 8, 21),
            ),
            (
                "Sep 10: Arjun asked about webhooks; pointed him to the v2 events API docs.",
                "question",
                datetime(2026, 9, 10),
            ),
        ],
    },
    {
        "customer_id": "cust-1044",
        "name": "Meera Iyer",
        "plan": "Enterprise",
        "facts": [
            (
                "Sep 5: Meera's team hit an SSO SAML configuration error (certificate mismatch); runbook RB-114 resolved it in 40 minutes.",
                "technical issue",
                datetime(2026, 9, 5),
            ),
            (
                "Sep 15: Meera requested a custom data-retention clause for the renewal; flagged for the account team.",
                "account",
                datetime(2026, 9, 15),
            ),
        ],
    },
    {
        "customer_id": "cust-1045",
        "name": "Vikram Rao",
        "plan": "Growth",
        "facts": [
            (
                "Aug 28: Vikram's CSV export timed out on 18 months of data; ticket #4766.",
                "technical issue",
                datetime(2026, 8, 28),
            ),
            (
                "Aug 29: Date-range filters under 6 months completed the export in 30s; shared as the workaround.",
                "technical issue",
                datetime(2026, 8, 29),
            ),
            (
                "Sep 18: Vikram reported the same export timeout 'again'; the date-range workaround was re-sent and he confirmed it worked.",
                "technical issue",
                datetime(2026, 9, 18),
            ),
        ],
    },
]

PLAYBOOK_FACTS: list[tuple[str, str, datetime]] = [
    (
        "Billing double-charge complaints were resolved by a specialist-approved credit within 24h for 3 of 3 customers.",
        "billing",
        datetime(2026, 9, 1),
    ),
    (
        "Invoice PDF download failures on app v2.4.0 are a known bug; workaround pending the v2.4.1 fix (ticket #4837).",
        "technical",
        datetime(2026, 9, 3),
    ),
    (
        "API rate-limit complaints on the Starter plan were resolved by the Growth upgrade path.",
        "technical",
        datetime(2026, 8, 22),
    ),
    (
        "SSO SAML certificate-mismatch errors are resolved by runbook RB-114 in about 40 minutes.",
        "technical",
        datetime(2026, 9, 6),
    ),
    (
        "CSV export timeouts on large ranges are worked around with date-range filters under 6 months.",
        "technical",
        datetime(2026, 8, 30),
    ),
    (
        "Customers contacting us twice about the same issue escalate fast; recall the earlier ticket number and state its status up front.",
        "support",
        datetime(2026, 9, 19),
    ),
]


async def seed(memory: MemoryLayer) -> dict:
    """Idempotently load the synthetic customers and playbook into Hindsight."""
    if await memory.is_seeded():
        return {
            "customers": [c["customer_id"] for c in CUSTOMERS],
            "playbook_facts": len(PLAYBOOK_FACTS),
            "skipped": True,
        }
    await memory.ensure_playbook_bank()
    for customer in CUSTOMERS:
        await memory.ensure_customer_bank(customer["customer_id"], customer["name"], customer["plan"])
        bank_id = f"customer-{customer['customer_id']}"
        for content, context, ts in customer["facts"]:
            try:
                await memory.retain_fact(bank_id, content, context, ts)
            except Exception as exc:
                log.warning("seed retain failed for %s: %s", bank_id, exc)
    for content, context, ts in PLAYBOOK_FACTS:
        try:
            await memory.retain_fact("support-playbook", content, context, ts)
        except Exception as exc:
            log.warning("seed retain failed for playbook: %s", exc)
    await memory.mark_seeded()
    return {
        "customers": [c["customer_id"] for c in CUSTOMERS],
        "playbook_facts": len(PLAYBOOK_FACTS),
        "skipped": False,
    }
