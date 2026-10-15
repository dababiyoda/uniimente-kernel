"""The one place a paid API route's vendor SDK is called and its answer normalised.

``greg.models`` uses it two ways: in the body process (an unconfined body, or a test's injected client), and, on a body
with confined egress (#26), as ``python -I`` inside a bubblewrap network namespace whose only way out is the relay
door, allowlisted for the route's pinned provider host. There the key arrives on stdin, never in argv or the
environment, and only normalised fields (or a failure's status, body and message) come back on stdout. Standard
library plus the vendor SDK only; nothing here decides authority or classifies failures (``greg.models`` does both).
"""
from __future__ import annotations

import json
import sys

BASE_URLS = {"anthropic": "https://api.anthropic.com", "openai": "https://api.openai.com/v1"}


def client(provider: str, api_key: str):
    """The vendor SDK client at the pinned base URL."""
    if provider == "anthropic":
        import anthropic
        return anthropic.Anthropic(api_key=api_key, base_url=BASE_URLS["anthropic"], max_retries=2)
    if provider == "openai":
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=BASE_URLS["openai"], max_retries=2)
    raise ValueError(f"no paid API route named {provider!r}")


def call(provider: str, sdk, model: str, system: str, user: str, max_tokens: int) -> dict:
    """One completion, normalised: refusal (bool), refusal_detail, text, status, input/output tokens, served model."""
    if provider == "anthropic":
        response = sdk.beta.messages.create(
            model=model, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}],
            thinking={"type": "adaptive"}, output_config={"effort": "high"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        refusal = response.stop_reason == "refusal"
        detail = getattr(getattr(response, "stop_details", None), "category", None)
        text = "".join(block.text for block in response.content if block.type == "text")
        status = response.stop_reason
    elif provider == "openai":
        response = sdk.responses.create(model=model, instructions=system, input=user, max_output_tokens=max_tokens)
        refusals = [part for item in (getattr(response, "output", None) or [])
                    for part in (getattr(item, "content", None) or []) if getattr(part, "type", "") == "refusal"]
        refusal, detail = bool(refusals), (getattr(refusals[0], "refusal", "") if refusals else None)
        text, status = getattr(response, "output_text", "") or "", getattr(response, "status", "unknown")
    else:
        raise ValueError(f"no paid API route named {provider!r}")
    usage = getattr(response, "usage", None)
    return {"refusal": refusal, "refusal_detail": detail, "text": text, "status": status,
            "input_tokens": getattr(usage, "input_tokens", None), "output_tokens": getattr(usage, "output_tokens", None),
            "served_model": getattr(response, "model", None)}


def failure(exc: BaseException) -> dict:
    """What ``greg.models.classify`` reads from a failure, in a form that crosses a pipe."""
    body = getattr(exc, "body", None)
    try:
        json.dumps(body)
    except (TypeError, ValueError):
        body = None
    status = getattr(exc, "status_code", None)
    return {"type": type(exc).__name__, "status_code": status if isinstance(status, int) else None,
            "body": body if isinstance(body, dict) else None, "message": str(exc)[:500]}


def main():
    """Child entry: one JSON request on stdin, one JSON answer on stdout."""
    request = json.loads(sys.stdin.read())
    try:
        answer = {"ok": True, "result": call(request["provider"], client(request["provider"], request["api_key"]),
                                             request["model"], request["system"], request["user"],
                                             int(request["max_tokens"]))}
    except Exception as exc:   # every failure goes back to the parent to be classified there
        answer = {"ok": False, "error": failure(exc)}
    sys.stdout.write(json.dumps(answer))
