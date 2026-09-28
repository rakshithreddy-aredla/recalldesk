/* RecallDesk — chat UI + Memory Lens. Vanilla JS, no build step. */

const CUSTOMERS = [
  { id: "cust-1042", name: "Priya Sharma", plan: "Growth plan" },
  { id: "cust-1043", name: "Arjun Patel", plan: "Starter plan" },
  { id: "cust-1044", name: "Meera Iyer", plan: "Enterprise" },
  { id: "cust-1045", name: "Vikram Rao", plan: "Growth plan" },
];

const DEMO_STEPS = [
  { memory: false, message: "Hi, I need help with my billing" },
  { memory: true, message: "Hi, I need help with my billing" },
  { memory: true, message: "My invoice download is broken AGAIN" },
];

const state = {
  customerId: CUSTOMERS[0].id,
  memoryMode: true,
  busy: false,
  demoRunning: false,
};

const el = {
  thread: document.getElementById("thread"),
  chips: document.getElementById("customer-chips"),
  form: document.getElementById("chat-form"),
  input: document.getElementById("chat-input"),
  send: document.getElementById("send-btn"),
  toggle: document.getElementById("memory-toggle"),
  banner: document.getElementById("mode-banner"),
  demoBtn: document.getElementById("demo-btn"),
  healthDot: document.getElementById("health-dot"),
  healthLabel: document.getElementById("health-label"),
  toast: document.getElementById("toast"),
  tabs: Array.from(document.querySelectorAll(".tab")),
  tabUsed: document.getElementById("tab-used"),
  tabObservations: document.getElementById("tab-observations"),
  tabHistory: document.getElementById("tab-history"),
};

const TYPE_LABELS = { world: "fact", experience: "experience", observation: "observation" };
const TYPE_CLASSES = { world: "tag-world", experience: "tag-experience", observation: "tag-observation" };

function nowTime() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function escapeless(node, text) {
  node.textContent = text;
  return node;
}

function toast(message) {
  escapeless(el.toast, message);
  el.toast.classList.remove("hidden");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => el.toast.classList.add("hidden"), 4000);
}

/* ---------- rendering ---------- */

function renderChips() {
  el.chips.innerHTML = "";
  for (const customer of CUSTOMERS) {
    const chip = document.createElement("button");
    chip.className = "chip" + (customer.id === state.customerId ? " chip-active" : "");
    chip.type = "button";
    escapeless(chip, `${customer.name} · ${customer.plan}`);
    chip.addEventListener("click", () => {
      state.customerId = customer.id;
      renderChips();
      el.thread.innerHTML = "";
      refreshLens();
      updateBanner();
    });
    el.chips.appendChild(chip);
  }
}

function updateBanner() {
  el.banner.classList.toggle("banner-off", !state.memoryMode);
  el.banner.classList.toggle("banner-on", state.memoryMode);
  el.banner.textContent = state.memoryMode
    ? `Memory ON — recalling ${state.customerId}'s history + cross-customer playbook`
    : "Memory OFF — the agent cannot recall this customer's history";
}

function addStepLabel(text) {
  const label = document.createElement("div");
  label.className = "step-label";
  escapeless(label, `— ${text} —`);
  el.thread.appendChild(label);
  scrollThread();
}

function addBubble(role, text, frustration) {
  const row = document.createElement("div");
  row.className = `bubble-row ${role === "user" ? "row-user" : "row-agent"}`;
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role === "user" ? "bubble-user" : "bubble-agent"}`;
  escapeless(bubble, text);
  const meta = document.createElement("div");
  meta.className = "bubble-meta";
  const time = document.createElement("span");
  escapeless(time, nowTime());
  meta.appendChild(time);
  if (role === "user" && frustration && frustration !== "calm") {
    const badge = document.createElement("span");
    badge.className = frustration === "angry" ? "badge badge-angry" : "badge badge-frustrated";
    escapeless(badge, frustration === "angry" ? "angry ×2" : "frustrated");
    meta.appendChild(badge);
  }
  row.appendChild(bubble);
  row.appendChild(meta);
  el.thread.appendChild(row);
  scrollThread();
}

function showTyping() {
  const row = document.createElement("div");
  row.className = "bubble-row row-agent";
  row.id = "typing";
  const bubble = document.createElement("div");
  bubble.className = "bubble bubble-agent typing";
  for (let i = 0; i < 3; i++) bubble.appendChild(document.createElement("span"));
  row.appendChild(bubble);
  el.thread.appendChild(row);
  scrollThread();
}

function hideTyping() {
  const typing = document.getElementById("typing");
  if (typing) typing.remove();
}

function scrollThread() {
  el.thread.scrollTop = el.thread.scrollHeight;
}

/* ---------- Memory Lens ---------- */

function memoryCard(memory, showScore) {
  const card = document.createElement("div");
  card.className = "mem-card";
  const top = document.createElement("div");
  top.className = "mem-top";
  const tag = document.createElement("span");
  tag.className = "tag " + (TYPE_CLASSES[memory.type] || "tag-world");
  escapeless(tag, TYPE_LABELS[memory.type] || memory.type);
  top.appendChild(tag);
  if (showScore && typeof memory.score === "number") {
    const bar = document.createElement("span");
    bar.className = "score-bar";
    const fill = document.createElement("span");
    fill.className = "score-fill";
    fill.style.width = `${Math.max(2, Math.min(100, Math.round(memory.score * 100)))}%`;
    bar.appendChild(fill);
    top.appendChild(bar);
  }
  const text = document.createElement("p");
  escapeless(text, memory.text || "(empty memory)");
  card.appendChild(top);
  card.appendChild(text);
  return card;
}

function emptyState(text) {
  const node = document.createElement("div");
  node.className = "empty-state";
  escapeless(node, text);
  return node;
}

function renderUsed(memories, memoryOn) {
  el.tabUsed.innerHTML = "";
  if (!memories || memories.length === 0) {
    el.tabUsed.appendChild(
      emptyState(memoryOn ? "No memories recalled for this message." : "No memories used — the agent is guessing.")
    );
    return;
  }
  for (const memory of memories) el.tabUsed.appendChild(memoryCard(memory, true));
}

async function refreshLens() {
  try {
    const resp = await fetch(`/customer/${state.customerId}/memory`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const body = await resp.json();
    el.tabObservations.innerHTML = "";
    if (!body.observations || body.observations.length === 0) {
      el.tabObservations.appendChild(emptyState("No consolidated observations yet — they form as facts repeat."));
    } else {
      for (const obs of body.observations) {
        const card = document.createElement("div");
        card.className = "mem-card";
        const top = document.createElement("div");
        top.className = "mem-top";
        const tag = document.createElement("span");
        tag.className = "tag tag-observation";
        escapeless(tag, "observation");
        const proof = document.createElement("span");
        proof.className = "proof";
        escapeless(proof, `${obs.proof_count ?? 1} source${(obs.proof_count ?? 1) === 1 ? "" : "s"}`);
        top.appendChild(tag);
        top.appendChild(proof);
        const text = document.createElement("p");
        escapeless(text, obs.text || "");
        card.appendChild(top);
        card.appendChild(text);
        el.tabObservations.appendChild(card);
      }
    }
    el.tabHistory.innerHTML = "";
    const count = document.createElement("p");
    count.className = "history-count";
    escapeless(count, `${body.count ?? (body.memories || []).length} memories stored for this customer`);
    el.tabHistory.appendChild(count);
    for (const memory of body.memories || []) el.tabHistory.appendChild(memoryCard(memory, false));
  } catch (err) {
    toast(`Could not load Memory Lens: ${err.message}`);
  }
}

/* ---------- API calls ---------- */

async function sendChat(message, memoryMode) {
  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      customer_id: state.customerId,
      message: message,
      memory_mode: memoryMode ? "on" : "off",
    }),
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      if (body.detail) detail = body.detail;
    } catch (_) { /* non-JSON error body */ }
    throw new Error(detail);
  }
  return resp.json();
}

async function pollHealth() {
  try {
    const resp = await fetch("/health");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const body = await resp.json();
    const up = body.hindsight === "up";
    el.healthDot.className = "dot " + (up ? "dot-up" : "dot-down");
    el.healthLabel.textContent = up ? "Hindsight up" : "Hindsight down";
  } catch (_) {
    el.healthDot.className = "dot dot-down";
    el.healthLabel.textContent = "API unreachable";
  }
}

/* ---------- events ---------- */

el.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy || state.demoRunning) return;
  const message = el.input.value.trim();
  if (!message) return;
  el.input.value = "";
  addBubble("user", message, null);
  await runTurn(message, state.memoryMode);
});

async function runTurn(message, memoryMode) {
  state.busy = true;
  el.send.disabled = true;
  showTyping();
  try {
    const body = await sendChat(message, memoryMode);
    hideTyping();
    addBubble("agent", body.reply, null);
    addBubble("user", message, body.frustration);
    // Re-order: the user bubble with the frustration badge belongs above the reply.
    renderUsed(body.memories_used, memoryMode);
    refreshLens();
  } catch (err) {
    hideTyping();
    toast(`Chat failed: ${err.message}`);
  } finally {
    state.busy = false;
    el.send.disabled = false;
    el.input.focus();
  }
}

el.toggle.addEventListener("change", () => {
  state.memoryMode = el.toggle.checked;
  updateBanner();
});

el.demoBtn.addEventListener("click", async () => {
  if (state.demoRunning || state.busy) return;
  state.demoRunning = true;
  el.demoBtn.disabled = true;
  el.thread.innerHTML = "";
  const labels = [
    "Demo step 1: memory OFF — watch the generic reply",
    "Demo step 2: memory ON — same question, memory-powered reply",
    "Demo step 3: memory ON — recall across sessions + frustration badge",
  ];
  for (let i = 0; i < DEMO_STEPS.length; i++) {
    const step = DEMO_STEPS[i];
    state.memoryMode = step.memory;
    el.toggle.checked = step.memory;
    updateBanner();
    addStepLabel(labels[i]);
    addBubble("user", step.message, null);
    await runTurn(step.message, step.memory);
    if (i < DEMO_STEPS.length - 1) await new Promise((r) => setTimeout(r, 1200));
  }
  state.demoRunning = false;
  el.demoBtn.disabled = false;
});

el.tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    el.tabs.forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const target = tab.dataset.tab;
    el.tabUsed.classList.toggle("hidden", target !== "used");
    el.tabObservations.classList.toggle("hidden", target !== "observations");
    el.tabHistory.classList.toggle("hidden", target !== "history");
  });
});

/* ---------- init ---------- */

renderChips();
updateBanner();
renderUsed([], true);
refreshLens();
pollHealth();
setInterval(pollHealth, 15000);
