# RecallDesk — 3-Minute Demo Script

Screen recording with voiceover. 1080p minimum, bigger fonts, notifications off.

## 0:00–0:30 — Intro
- On camera (optional) or voiceover: "Hi, I'm [name]. This is RecallDesk — a customer support copilot that never forgets. It's built on Hindsight, a memory system that lets the agent remember every past conversation and get better over time."
- **On screen:** open http://localhost:8000 — show the top bar: green "Hindsight up" dot, "Agent memory" toggle, the four customer chips.

## 0:30–1:00 — The problem (memory OFF)
- Click **Run demo scenario** — step 1 runs with memory OFF.
- Voiceover: "Here's the same support chatbot you've used a hundred times. It has no memory. A returning customer says 'Hi, I need help with my billing' — and it asks her to explain everything from scratch, even though she's contacted us three times before."
- **On screen:** the amber "Memory OFF" banner, the generic reply, the Memory Lens "Used in reply" tab showing "No memories used — the agent is guessing."

## 1:00–2:45 — The demo (memory ON)
- Let step 2 run: same question, memory ON.
- Voiceover: "Now with memory on — same question, zero re-explaining. Every conversation was retained with real timestamps. Hindsight recall runs four searches in parallel — semantic, keyword, graph, and temporal — so 'billing' pulls up last month's invoice issue instantly."
- **On screen:** Memory Lens "Used in reply" fills with cards (fact / experience / observation tags + score bars).
- Let step 3 run: "My invoice download is broken AGAIN".
- Voiceover: "Watch the word 'again'. The agent recalls ticket #4837 from two weeks ago, cites it directly, and the cross-customer playbook bank knows the fix shipped in v2.4.1 — that's learning from other customers' outcomes."
- **On screen:** the "frustrated" badge on the user bubble, the reply citing #4837.
- Open the **Observations** tab.
- Voiceover: "And this is my favorite part — Hindsight consolidates repeated facts into observations with source counts. These aren't raw notes; they're beliefs with evidence. That's what the agent reasons over."
- **On screen:** observation cards with "2 sources" proof counts.
- (Optional) flip the **Memory ON/OFF** toggle mid-chat one more time to show the contrast live.

## 2:45–3:15 — Wrap up
- Voiceover: "The whole memory layer is one auditable file — retain on every turn, recall on every message, and the observations do the rest. What surprised me: the biggest UX win wasn't smarter answers, it was never asking the customer to repeat themselves."
- **On screen:** the chat panel + Memory Lens side by side, then end on the repo README.

## Recording notes
- OBS (free) or Loom; window capture at 1080p; increase browser font to 125% first.
- If you make a mistake, keep going — authenticity beats polish.
- Upload public to YouTube; generate a 16:9 thumbnail before posting.
