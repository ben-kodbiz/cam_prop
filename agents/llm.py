"""Local LLM access (Phase 3, agentodo §25).

Talks to an OpenAI-compatible endpoint (llama.cpp / Ollama / LM Studio)
configured via .env (OE_LLM_*). Never a hard-coded provider or key.

The LLM may summarize, classify, extract, compare and draft — it must
never invent evidence, statistics, quotations or sources. Everything it
produces is a *proposal* stored for human review (claim_drafts), never
an assertion written into published content.

`client` is injectable: tests pass a fake, production passes an
HttpClient. No network calls happen in tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.config import LLMConfig


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    """Minimal interface the rest of the code depends on."""

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str: ...


@dataclass
class OpenAICompatClient:
    """Minimal OpenAI-compatible chat client (llama.cpp, Ollama, LM Studio)."""

    endpoint: str
    model: str
    api_key: str = ""
    timeout: float = 60.0

    def complete(self, system: str, user: str, *, json_mode: bool = False) -> str:
        try:
            import httpx
        except ImportError as e:  # pragma: no cover - httpx is a core dep
            msg = "httpx is required for LLM access"
            raise LLMError(msg) from e
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        url = self.endpoint.rstrip("/") + "/chat/completions"
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])
        except Exception as e:
            msg = f"LLM request failed ({url}): {e}"
            raise LLMError(msg) from e


def client_from_config(cfg: LLMConfig) -> OpenAICompatClient:
    """Build the client from .env config."""
    return OpenAICompatClient(endpoint=cfg.endpoint, model=cfg.model, api_key=cfg.api_key)


def parse_json_block(raw: str) -> Any:
    """Tolerantly parse a JSON object from an LLM reply.

    Models sometimes wrap JSON in prose or code fences; extract the first
    balanced object. Raises LLMError when nothing parses.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    start = -1
    msg = f"could not parse JSON from LLM reply: {raw[:200]!r}"
    raise LLMError(msg)
