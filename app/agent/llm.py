"""Local inference only. This client can reach localhost and nothing else.

There is deliberately no base-URL parameter and no API-key handling here: the one
place in this codebase that may talk to a remote model is app/escalate/external.py,
and it takes a minimized envelope. If you find yourself wanting to point this file at
a hosted endpoint, that is the bug.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from config import settings

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


class NonLocalInference(RuntimeError):
    pass


def _assert_local(url: str) -> None:
    host = urlparse(url).hostname or ""
    if host not in _LOCAL_HOSTS:
        raise NonLocalInference(
            f"planner inference must stay on the box; refusing host '{host}'"
        )


@dataclass
class LLMReply:
    text: str
    model: str
    ms: int


async def available_models() -> list[str]:
    s = settings()
    _assert_local(s.ollama_url)
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{s.ollama_url}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


async def resolve_model() -> str | None:
    """Prefer the configured model; fall back through the list the box actually has."""
    s = settings()
    have = await available_models()
    if not have:
        return None
    wanted = [s.ollama_model] + [m.strip() for m in s.ollama_fallbacks.split(",") if m.strip()]
    for w in wanted:
        for h in have:
            if h == w or h.split(":")[0] == w.split(":")[0]:
                return h
    return have[0]


async def chat(system: str, user: str, *, json_mode: bool = False,
               model: str | None = None) -> LLMReply:
    import time

    s = settings()
    _assert_local(s.ollama_url)
    mdl = model or await resolve_model()
    if not mdl:
        raise RuntimeError("no local model available — is ollama running?")

    body: dict = {
        "model": mdl,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 8192},
    }
    if json_mode:
        body["format"] = "json"

    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=s.ollama_timeout_s) as c:
        r = await c.post(f"{s.ollama_url}/api/chat", json=body)
        r.raise_for_status()
        data = r.json()
    return LLMReply(
        text=(data.get("message") or {}).get("content", ""),
        model=mdl,
        ms=int((time.monotonic() - t0) * 1000),
    )


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> dict | None:
    """Small models wrap JSON in prose or fences more often than not."""
    if not text:
        return None
    for candidate in (text, *(m.strip() for m in _FENCE.findall(text))):
        try:
            val = json.loads(candidate)
            if isinstance(val, dict):
                return val
        except json.JSONDecodeError:
            pass
    start, depth, in_str, esc = None, 0, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    val = json.loads(text[start:i + 1])
                    if isinstance(val, dict):
                        return val
                except json.JSONDecodeError:
                    pass
                start = None
    return None
