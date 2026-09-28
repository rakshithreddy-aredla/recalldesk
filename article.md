# My support agent finally stopped asking customers to repeat themselves

Last month a customer of ours contacted support for the third time about the same broken feature. Each time, a fresh chatbot session asked her to explain her problem from scratch. Nothing carried over — not the ticket number, not the workaround we'd already sent her, not the fact that she was, by then, understandably furious. She wasn't angry about the bug. She was angry about repeating herself.

That experience is what pushed me to build RecallDesk, a support copilot with a persistent memory layer. It's a FastAPI service with a vanilla-JS chat interface, and the interesting part is the memory: every conversation is stored with [Hindsight agent memory](https://vectorize.io/what-is-agent-memory), and the agent recalls each customer's full history before it says a word.

## What the system does

RecallDesk is small by design. A FastAPI backend exposes one main endpoint — `POST /chat` — which takes a customer ID, the customer's message, and a memory mode. A vanilla JavaScript frontend renders the chat plus a "Memory Lens" panel that shows, live, which memories the agent used in its last reply.

The memory layer is organized as **two levels of banks**:

- One bank per customer (`customer-<id>`), holding that customer's complete history
- One shared `support-playbook` bank, holding what has worked across *all* customers

That second bank is the decision I'd defend hardest. A per-customer memory alone answers "what happened with Priya?" A playbook answers "what has actually resolved billing complaints before?" — knowledge the agent gains from other customers' outcomes. The first bank makes the agent polite; the second makes it competent.

Both banks are configured with a mission, directives, and a disposition:

```python
client.create_bank(
    bank_id="customer-1042",
    name="Priya Sharma",
    mission=(
        "You are the complete support memory of Priya Sharma (cust-1042), "
        "an SMB customer on the Growth plan. Track every issue, its "
        "resolution, the customer's environment, and their frustration level."
    ),
    disposition={"skepticism": 2, "literalism": 2, "empathy": 4},
)
```

Directives are the rules the reasoning step must never violate: never promise a refund without human approval, always cite the past ticket number when referencing previous issues, and escalate if the customer has been angry in two consecutive messages.

## Writing memory down, properly

Every chat exchange is retained with a real timestamp, the session ID, and the customer's frustration level at that moment:

```python
self._client.retain(
    bank_id=f"customer-{customer_id}",
    content=f"Customer: {user_message}\nSupport agent: {assistant_reply}",
    context=f"live chat, frustration={frustration}",
    timestamp=_utcnow(),
    document_id=f"chat-{session_id}",
    metadata={"frustration": frustration, "channel": "recalldesk-web"},
)
```

The timestamp matters more than it looks. Support conversations are temporal objects: "it broke again" means "find the earlier incident," and "again" only resolves if the search understands time. This is where simple vector similarity falls flat — cosine distance has no concept of last Tuesday.

On the read side, recall is a single call. Hindsight's [TEMPR retrieval](https://hindsight.vectorize.io/) runs four searches in parallel — semantic, keyword (BM25), graph, and temporal — and fuses the results:

```python
results = self._client.recall(
    bank_id=f"customer-{customer_id}",
    query=user_message,
    types=["world", "observation", "experience"],
    budget="mid",
    max_tokens=4096,
)
```

Each result carries its text, a memory type, and a relevance score. The backend numbers them into the system prompt, and the frontend surfaces them in the Memory Lens panel with type tags and score bars — so you can see exactly what the agent based its reply on.

## The before/after moment

With memory off, the agent replies from a deliberately generic prompt: it greets the customer and asks them to describe the issue from scratch. With memory on, the same message gets a different answer entirely. A customer saying "My invoice download is broken AGAIN" gets:

> Hi Priya — this is the invoice PDF bug from ticket #4837, which failed on app v2.4.0. The fix shipped in v2.4.1; could you confirm your version? If it's still failing on the latest build, I'll flag it for a specialist right away.

Same model. Same temperature. The only difference is what the memory layer put into the prompt. That contrast — replayed live with a toggle — is the clearest argument for the architecture I know how to make.

The playbook bank earns its keep here too: "invoice PDF download failures on v2.4.0 are a known bug, fix pending in v2.4.1" is a fact learned from *another* customer's ticket. The agent knew this customer's issue before she finished typing, and knew the industry-wide resolution status too.

## Consolidation: the part I didn't have to build

The piece that most surprised me was what I *didn't* write. As facts accumulate, Hindsight's worker consolidates them into observations — deduplicated, evidence-grounded beliefs with source counts and preserved history. "Priya's invoice download failed" and "Priya reported the same issue again" become one observation with two sources, not two rows in a table that someone has to reconcile.

Support is exactly the domain where this matters. The same edge cases recur constantly, and a naive store piles up near-duplicates until the useful signal drowns. Here, the agent's beliefs stay grounded and current, and the Memory Lens panel shows them with "2 sources" attached — which turned out to be the most persuasive screen in the whole product.

## What I learned

**The biggest UX win wasn't smarter answers — it was never asking the customer to repeat themselves.** I expected the memory to show up as better phrasing. It showed up as not needing the question.

**Timestamps are load-bearing.** Half the value of "again" and "still" comes from temporal retrieval. If you're storing conversations without real dates, you're throwing away the queries customers actually ask.

**A second, cross-entity bank doubles the payoff for one extra retain call.** Per-subject memory personalizes; cross-subject memory teaches. The playbook bank is one bank and a handful of experience facts, and it changed the agent's answers as much as the customer history did.

**Graceful degradation is non-negotiable.** The memory server is a separate process and the LLM is a remote API — both will be down at the worst moment. Every memory call in RecallDesk degrades to a no-op with a flag instead of raising, so the support flow keeps working without memory and the UI says so honestly.

**The honest limitation:** the system is only as good as what gets retained. If an agent's reply is vague, the memory inherits the vagueness. Garbage in, consolidated garbage out. The fix is directive-driven reply discipline — "cite ticket numbers, be specific" — which improves the replies *and* the memory they generate. I consider that an open loop, and it's the first thing I'd work on next.

## Try it

RecallDesk is a small, auditable codebase: one file for memory, one for the LLM, one FastAPI app, a vanilla-JS UI. If you're building agents that need to remember, the [Hindsight GitHub repository](https://github.com/vectorize-io/hindsight) and its [documentation](https://hindsight.vectorize.io/) are the right place to start — and reading [what agent memory actually is](https://vectorize.io/what-is-agent-memory) first will save you the vector-search detour I described above.
