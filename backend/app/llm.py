"""Groq LLM wrapper with retries and a graceful fallback reply.

We intentionally avoid function calling in the support flow; if a provider
injects tool-call fragments into a completion anyway, that attempt is
discarded and retried, so the agent always ends up with plain text.
"""

import logging
import time

from groq import Groq

log = logging.getLogger("recalldesk.llm")

FALLBACK_REPLY = (
    "I'm having trouble reaching my reasoning service right now. I've noted your "
    "message and a specialist will follow up shortly."
)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30.0


class LLM:
    def __init__(self, api_key: str | None, model: str | None) -> None:
        self._client = Groq(api_key=api_key, timeout=REQUEST_TIMEOUT) if api_key else None
        self._model = model or "openai/gpt-oss-120b"

    @property
    def available(self) -> bool:
        return self._client is not None

    def support_reply(
        self, system_prompt: str, history: list[dict[str, str]], user_message: str
    ) -> str:
        """Generate a support-agent reply. Returns the fallback reply on failure."""
        if self._client is None:
            return FALLBACK_REPLY
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=600,
                )
                choice = response.choices[0].message
                content = getattr(choice, "content", None)
                has_tool_calls = getattr(choice, "tool_calls", None) is not None
                if content and content.strip() and not has_tool_calls:
                    return content.strip()
                log.warning("LLM attempt %d returned unusable output", attempt + 1)
            except Exception as exc:
                log.warning("LLM attempt %d/%d failed: %s", attempt + 1, MAX_RETRIES, exc)
            time.sleep(0.5 * (2**attempt))
        return FALLBACK_REPLY

    def classify_frustration(self, message: str) -> str:
        """One-shot classification, used only if the cheap heuristic is ambiguous."""
        if self._client is None:
            return "calm"
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Classify the customer's frustration level. Answer with "
                            "exactly one word: calm, frustrated, or angry."
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                temperature=0.0,
                max_tokens=4,
            )
            word = (response.choices[0].message.content or "").strip().lower()
            if word in {"calm", "frustrated", "angry"}:
                return word
        except Exception as exc:
            log.warning("frustration classification failed: %s", exc)
        return "calm"
