"""
core/llm_backend.py
-------------------
Unified LLM backend abstraction.

Supported providers
-------------------
"claude"           – Anthropic Messages API (cloud)
"lmstudio"         – LM Studio local server, text-only  (OpenAI-compatible)
"lmstudio_vision"  – LM Studio local server, vision     (OpenAI-compatible, image input)

Configuration is held in a LLMConfig dataclass and can be changed at runtime.
All providers expose the same call signature:

    backend.chat(system: str, user: str, image_b64: str | None = None) -> str

Vision notes
------------
LM Studio exposes an OpenAI-compatible /v1/chat/completions endpoint.
For vision, load a multimodal model (e.g. llava, bakllava, moondream) in LM
Studio and pass image_b64 as a base64-encoded PNG/JPEG string.  The backend
automatically wraps it in the correct content-array format.

Typical LM Studio base URL: http://localhost:1234
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from typing import Optional

import requests


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class LLMConfig:
    provider: str = "claude"          # "claude" | "lmstudio" | "lmstudio_vision"
    # LM Studio settings
    lmstudio_base_url: str  = "http://localhost:1234"
    lmstudio_model:    str  = ""      # e.g. "lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF"
                                      # leave blank to use whichever is loaded
    lmstudio_vision_model: str = ""   # vision model name (may differ from text model)
    # Shared
    timeout: int = 60
    max_tokens: int = 1000
    temperature: float = 0.0          # 0 = deterministic, good for structured output


# Global singleton config — updated by the settings dialog
_config: LLMConfig = LLMConfig()


def get_config() -> LLMConfig:
    return _config


def set_config(cfg: LLMConfig) -> None:
    global _config
    _config = cfg


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove markdown code fences and trim whitespace."""
    return re.sub(r"```(?:json)?|```", "", text).strip()


def _parse_json_ops(raw: str) -> list[dict]:
    raw = _strip_fences(raw)
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        parsed = [parsed]
    return parsed


# ── Provider implementations ──────────────────────────────────────────────────

def _call_claude(system: str, user: str, image_b64: Optional[str] = None,
                 cfg: LLMConfig = None) -> str:
    """Call Anthropic Messages API."""
    cfg = cfg or _config
    content: list = []
    if image_b64:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_b64,
            },
        })
    content.append({"type": "text", "text": user})

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"Content-Type": "application/json"},
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": cfg.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": content}],
        },
        timeout=cfg.timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")


def _call_lmstudio(system: str, user: str, image_b64: Optional[str] = None,
                   cfg: LLMConfig = None) -> str:
    """Call LM Studio via OpenAI-compatible /v1/chat/completions."""
    cfg = cfg or _config
    is_vision = image_b64 is not None

    # Choose model name
    if is_vision and cfg.lmstudio_vision_model:
        model = cfg.lmstudio_vision_model
    elif cfg.lmstudio_model:
        model = cfg.lmstudio_model
    else:
        model = "local-model"   # LM Studio ignores this if only one model is loaded

    # Build user message content
    if is_vision:
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_b64}",
                },
            },
            {"type": "text", "text": user},
        ]
    else:
        user_content = user

    payload = {
        "model": model,
        "max_tokens": cfg.max_tokens,
        "temperature": cfg.temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ],
    }

    base = cfg.lmstudio_base_url.rstrip("/")
    resp = requests.post(
        f"{base}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=cfg.timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ── Public chat interface ─────────────────────────────────────────────────────

def chat(system: str, user: str, image_b64: Optional[str] = None,
         cfg: LLMConfig = None) -> str:
    """
    Send a message to the configured LLM and return the response text.

    Parameters
    ----------
    system    : system prompt
    user      : user message text
    image_b64 : optional base64-encoded PNG/JPEG for vision models
    cfg       : override config (uses global singleton if None)
    """
    cfg = cfg or _config

    if cfg.provider == "claude":
        return _call_claude(system, user, image_b64, cfg)
    elif cfg.provider in ("lmstudio", "lmstudio_vision"):
        return _call_lmstudio(system, user, image_b64, cfg)
    else:
        raise ValueError(f"Unknown provider: '{cfg.provider}'")


def chat_json(system: str, user: str, image_b64: Optional[str] = None,
              cfg: LLMConfig = None) -> list[dict]:
    """
    Like chat() but parses the response as a JSON array of operation dicts.
    Strips markdown fences before parsing.
    """
    raw = chat(system, user, image_b64, cfg)
    return _parse_json_ops(raw)


# ── Connection test ───────────────────────────────────────────────────────────

def test_connection(cfg: LLMConfig) -> tuple[bool, str]:
    """
    Ping the configured backend with a trivial request.
    Returns (success: bool, message: str).
    """
    try:
        if cfg.provider == "claude":
            result = _call_claude(
                system="You are a helpful assistant.",
                user="Reply with exactly: OK",
                cfg=cfg,
            )
            ok = "ok" in result.lower()
            return ok, result.strip()

        elif cfg.provider in ("lmstudio", "lmstudio_vision"):
            # First check if the server is reachable
            base = cfg.lmstudio_base_url.rstrip("/")
            models_resp = requests.get(f"{base}/v1/models", timeout=5)
            models_resp.raise_for_status()
            models = [m["id"] for m in models_resp.json().get("data", [])]
            if not models:
                return False, "LM Studio is running but no models are loaded."
            # Quick chat test
            result = _call_lmstudio(
                system="You are a helpful assistant.",
                user="Reply with exactly: OK",
                cfg=cfg,
            )
            ok = "ok" in result.lower()
            loaded = ", ".join(models[:3])
            return ok, f"Connected. Loaded model(s): {loaded}. Response: {result.strip()[:60]}"

        else:
            return False, f"Unknown provider: {cfg.provider}"

    except requests.exceptions.ConnectionError:
        return False, (
            "Could not connect to LM Studio. "
            f"Is it running at {cfg.lmstudio_base_url}? "
            "Enable the local server in LM Studio → Developer → Start Server."
        )
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        return False, str(e)


def list_lmstudio_models(base_url: str, timeout: int = 5) -> list[str]:
    """Return list of model IDs currently loaded in LM Studio."""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/v1/models", timeout=timeout)
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", [])]
    except Exception:
        return []
