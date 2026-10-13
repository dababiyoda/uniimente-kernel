"""Provider-independent model routing: GREG is not married to one model vendor.

One interface over the Anthropic API, OpenAI API, the founder's installed Claude Code CLI,
and an explicitly selected locally installed Ollama model.
The router tries routes in preference order, demotes a route that keeps failing, and
records which route actually produced each answer, so a planner draft or a built
capability always names its true author.

What routing never does:

* **Shop a refusal.** A model that declines is an answer, not an outage. The router
  stops there; it does not re-ask another vendor to get around a safety decision. The
  same holds when the *provider's* policy filter rejects the request before the model
  answers with affirmative policy evidence: a documented policy code
  (``content_policy_violation``, ``moderation_blocked``, ``cyber_policy`` ...) or unmistakable
  policy wording. A bare ``invalid_prompt`` is NOT such evidence (OpenAI's status history
  records an outage seen as elevated ``invalid_prompt`` errors): it is recorded as
  ``unconfirmed_rejection`` and another route may legitimately try.
  Fallback may improve availability; it is never a way around a policy decision.
* **Spend without a bound.** For spending contexts (Capability Genesis builds) each
  API route computes the largest output it may generate so that its worst-case cost
  fits the remaining founder-signed budget; a route whose price is unknown cannot be
  bounded and is skipped. The CLI route enforces its own ``--max-budget-usd``.
* **Take credentials from the environment.** Keys come only from declared credential
  handles (``anthropic_api_key``, ``openai_api_key``); base URLs are pinned.
* **Select a paid route by default.** Open-source-first (INTENT-20260930-open-source-first):
  with no founder selection there is no model route at all; the template route still works.
  A local open model is used when the founder selects it (``greg init --local-model`` or a
  signed ``greg model set --route ollama``). A paid route (``anthropic``, ``openai``,
  ``claude-code``) is used only when the founder's own selection names it; a stored API key
  or an installed CLI never selects one.

Models propose; they never authorize. Nothing here grants authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import http.client
import json
import math
import re
import shutil
import subprocess


# What a route failure means for routing. Only the refusal classes stop the router.
SAFETY_REFUSAL = "safety_refusal"                    # the model declined (stop reason / refusal output)
PROVIDER_POLICY_REFUSAL = "provider_policy_refusal"  # the provider's policy filter rejected the request
TRANSIENT = "transient"                              # connection, timeout, 408/409/429, 5xx
AUTH = "auth"                                        # 401/403: this route's credential or entitlement
UNAVAILABLE = "capability_unavailable"               # 404: model or endpoint absent; CLI not installed
INVALID_REQUEST = "invalid_request"                  # other 400/413/422: this route cannot take this request
BAD_OUTPUT = "bad_output"                            # empty or unreadable answer
UNCONFIRMED_REJECTION = "unconfirmed_rejection"         # a code that may mean policy OR a provider fault
UNKNOWN = "unknown"
REFUSAL_CLASSES = (SAFETY_REFUSAL, PROVIDER_POLICY_REFUSAL)
# Two separate questions: what happened (the class), and may another route try (only refusals say no).
# A refusal needs affirmative policy evidence: one of these structured codes, or unmistakable wording.
POLICY_CODES = {"content_policy_violation", "content_filter", "moderation_blocked", "cyber_policy",
                "responsible_ai_policy_violation"}
# Codes that do not by themselves prove a policy decision: terminal only together with policy wording.
AMBIGUOUS_CODES = {"invalid_prompt"}
# Wording: OpenAI's flagged-prompt message; Azure OpenAI's content filter / content management policy.
POLICY_PHRASES = ("usage policy", "usage policies", "content policy", "content management policy",
                  "content filter", "safety system", "flagged as potentially violating")


class RouteError(Exception):
    """A route could not produce an answer (outage, bad credential, bad output). Try the next."""

    def __init__(self, message: str = "", *, kind: str = UNKNOWN):
        super().__init__(message)
        self.kind = kind


class Refusal(RouteError):
    """The model or its provider declined. Terminal: never retried on another provider."""

    def __init__(self, message: str = "", *, kind: str = SAFETY_REFUSAL):
        super().__init__(message, kind=kind)


def _error_code(exc) -> str | None:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        inner = body.get("error") if isinstance(body.get("error"), dict) else body
        code = inner.get("code") or inner.get("type")
        return str(code) if code else None
    return None


def is_policy_text(text: str) -> bool:
    text = text.lower()
    return any(phrase in text for phrase in POLICY_PHRASES)


def classify(exc: BaseException) -> str:
    """Classify an SDK/network exception from any provider without importing its SDK."""
    status = getattr(exc, "status_code", None)
    code = _error_code(exc)
    if status in (400, 403, 422) and (code in POLICY_CODES or is_policy_text(str(exc))):
        return PROVIDER_POLICY_REFUSAL
    if status in (400, 403, 422) and code in AMBIGUOUS_CODES:
        return UNCONFIRMED_REJECTION
    if isinstance(exc, (TimeoutError, ConnectionError)) or type(exc).__name__ in (
            "APIConnectionError", "APITimeoutError") or status in (408, 409, 429) or (status or 0) >= 500:
        return TRANSIENT
    if status in (401, 403):
        return AUTH
    if status == 404:
        return UNAVAILABLE
    if status in (400, 413, 422):
        return INVALID_REQUEST
    return UNKNOWN


def _route_failure(exc: BaseException) -> RouteError:
    kind = classify(exc)
    message = f"{type(exc).__name__}: {exc}"[:300]
    if kind in REFUSAL_CLASSES:
        return Refusal(f"provider policy rejected the request: {message}"[:300], kind=kind)
    return RouteError(message, kind=kind)


class Unbounded(RouteError):
    """The route's worst-case cost cannot be bounded under the remaining budget."""


# USD per million tokens (input, output). Anthropic prices from the Claude API reference;
# other providers' prices are supplied by the founder's configuration, never guessed.
ANTHROPIC_PRICES = {"claude-opus-5": (5.0, 25.0), "claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5": (2.0, 10.0),
                    "claude-fable-5-1": (10.0, 50.0), "claude-haiku-4-5": (1.0, 5.0)}
MAX_OUTPUT_TOKENS = 16000


def _price(value):
    """(input, output) USD per million tokens, both finite and positive; anything else is 'no price'."""
    try:
        price_in, price_out = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    ok = all(0 < v < 10_000 for v in (price_in, price_out))
    return (price_in, price_out) if ok else None
MIN_OUTPUT_TOKENS = 1024


def _estimate_tokens(text: str) -> int:
    return len(text) // 3 + 1   # conservative (over-counts): ~4 chars/token in practice


def _output_bound(price, system: str, user: str, budget_usd):
    """Largest max-output-tokens whose worst-case cost fits the budget; None = unlimited context."""
    if budget_usd is None:
        return MAX_OUTPUT_TOKENS
    if price is None:
        raise Unbounded("no configured price; cannot bound spend under a signed budget")
    price_in, price_out = price
    remaining = budget_usd - _estimate_tokens(system + user) * price_in / 1e6
    tokens = int(remaining * 1e6 / price_out) if remaining > 0 else 0
    if tokens < MIN_OUTPUT_TOKENS:
        raise Unbounded(f"budget ${budget_usd:.4f} cannot cover a minimal answer on this route")
    return min(tokens, MAX_OUTPUT_TOKENS)


class AnthropicRoute:
    """Claude via the official Anthropic SDK (optional dependency ``anthropic``)."""
    provider = "anthropic"

    def __init__(self, api_key: str, *, model: str = "claude-opus-5", price=None, client=None):
        self.model, self.name = model, f"anthropic:{model}"
        # Prices are operational evidence, not constants: a configured price supersedes the built-in
        # snapshot without a code change. A malformed configured price is not silently replaced by the
        # (possibly stale) snapshot: the route has no price, so a spending context skips it (Unbounded).
        self.price = _price(price) if price is not None else ANTHROPIC_PRICES.get(model)
        if client is None:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, base_url="https://api.anthropic.com", max_retries=2)
        self.client = client

    def complete(self, system: str, user: str, *, budget_usd=None) -> dict:
        max_tokens = _output_bound(self.price, system, user, budget_usd)
        try:
            response = self.client.beta.messages.create(
                model=self.model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
                thinking={"type": "adaptive"}, output_config={"effort": "high"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        except Exception as exc:   # SDK/network errors, classified: a policy verdict is not an outage
            raise _route_failure(exc) from exc
        if response.stop_reason == "refusal":
            category = getattr(getattr(response, "stop_details", None), "category", None)
            raise Refusal(f"model declined (refusal: {category})", kind=SAFETY_REFUSAL)
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = getattr(response, "usage", None)
        cost = None
        if usage is not None and self.price:
            cost = (usage.input_tokens * self.price[0] + usage.output_tokens * self.price[1]) / 1e6
        # the provider's own report of the model that answered (server-side fallback may substitute one)
        return {"text": text, "cost_usd": cost, "served_model": getattr(response, "model", None) or self.model}


class OpenAIRoute:
    """OpenAI models via the official ``openai`` SDK Responses API (optional dependency)."""
    provider = "openai"

    def __init__(self, api_key: str, *, model: str = "gpt-5.5", price=None, client=None):
        self.model, self.name, self.price = model, f"openai:{model}", _price(price)
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1", max_retries=2)
        self.client = client

    def complete(self, system: str, user: str, *, budget_usd=None) -> dict:
        max_tokens = _output_bound(self.price, system, user, budget_usd)
        try:
            response = self.client.responses.create(model=self.model, instructions=system, input=user,
                                                    max_output_tokens=max_tokens)
        except Exception as exc:   # classified: HTTP 400 invalid_prompt is a policy verdict, not an outage
            raise _route_failure(exc) from exc
        refusals = [part for item in (getattr(response, "output", None) or [])
                    for part in (getattr(item, "content", None) or []) if getattr(part, "type", "") == "refusal"]
        if refusals:
            raise Refusal(f"model declined: {getattr(refusals[0], 'refusal', '')}"[:300], kind=SAFETY_REFUSAL)
        text = getattr(response, "output_text", "") or ""
        if not text:
            raise RouteError(f"empty response (status {getattr(response, 'status', 'unknown')})", kind=BAD_OUTPUT)
        usage = getattr(response, "usage", None)
        cost = None
        if usage is not None and self.price:
            cost = (usage.input_tokens * self.price[0] + usage.output_tokens * self.price[1]) / 1e6
        return {"text": text, "cost_usd": cost, "served_model": getattr(response, "model", None) or self.model}


class OllamaRoute:
    """Only the fixed loopback Ollama native API; never discovers, pulls or selects a cloud model.

    The local server is a trusted operator dependency. Its /api/tags response is local
    inventory evidence, not proof that a malicious/reconfigured server cannot relay data.
    Run Ollama with cloud features disabled for a genuinely offline installation.
    """
    provider = "ollama"
    MAX_RESPONSE_BYTES = 1 << 20

    def __init__(self, model: str, *, port: int = 11434, timeout_seconds: float = 120, max_tokens: int = 8192, json_output: bool = False, response_schema: dict | None = None):
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model):
            raise ValueError("an explicit Ollama model name is required")
        if model.endswith(":cloud") or model.endswith("-cloud"):
            raise ValueError("cloud model cannot be used as a local Ollama route")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("invalid Ollama loopback port")
        self.model, self.name, self.port = model, f"ollama:{model}", port
        if not 0 < timeout_seconds <= 120 or type(max_tokens) is not int or not 1 <= max_tokens <= 8192:
            raise ValueError("invalid local inference resource ceiling")
        self.timeout_seconds, self.max_tokens = timeout_seconds, max_tokens
        self.json_output = json_output
        self.response_schema = response_schema

    def _request(self, method: str, path: str, data=None) -> dict:
        # HTTPConnection uses a fixed numeric loopback address: no DNS, redirects,
        # proxy environment, remote base URL or inherited credentials.
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=min(self.timeout_seconds, 120 if data is not None else 5))
        try:
            conn.request(method, path, body=json.dumps(data) if data is not None else None,
                         headers={"Content-Type": "application/json"} if data is not None else {})
            response = conn.getresponse()
            raw = response.read(self.MAX_RESPONSE_BYTES + 1)
            if len(raw) > self.MAX_RESPONSE_BYTES:
                raise RouteError("Ollama response exceeds size limit", kind=BAD_OUTPUT)
            try:
                result = json.loads(raw)
            except (UnicodeError, ValueError) as exc:
                raise RouteError("Ollama returned invalid JSON", kind=BAD_OUTPUT) from exc
            if not isinstance(result, dict):
                raise RouteError("Ollama returned an invalid response", kind=BAD_OUTPUT)
            if response.status >= 400:
                error = result.get("error", "request failed")
                if isinstance(error, dict):
                    error = error.get("message", str(error))
                failure = Exception(str(error)[:250])
                failure.status_code = response.status
                failure.body = result
                raise _route_failure(failure)
            return result
        except (TimeoutError, OSError, http.client.HTTPException) as exc:
            raise RouteError(f"Ollama unavailable: {type(exc).__name__}: {exc}"[:300], kind=TRANSIENT) from exc
        finally:
            conn.close()

    def complete(self, system: str, user: str, *, budget_usd=None) -> dict:
        if budget_usd is not None and (not isinstance(budget_usd, (float, int)) or
                                       not math.isfinite(budget_usd) or budget_usd < 0):
            raise Unbounded("invalid local model budget")
        inventory = self._request("GET", "/api/tags")
        items = inventory.get("models")
        if not isinstance(items, list):
            raise RouteError("Ollama returned an invalid local model inventory", kind=BAD_OUTPUT)
        installed = next((item for item in items if isinstance(item, dict)
                          and self.model in (item.get("name"), item.get("model"))
                          and type(item.get("size")) is int and item["size"] > 0
                          and isinstance(item.get("details"), dict)
                          and item["details"].get("format") == "gguf"), None)
        if installed is None:
            raise RouteError(f"{self.model} is not installed locally in Ollama", kind=UNAVAILABLE)
        digest = installed.get("digest")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            raise RouteError("local model has no valid artifact digest", kind=BAD_OUTPUT)
        answer = self._request("POST", "/api/chat", {
            "model": self.model, "stream": False, "think": False,
            **({"format": self.response_schema or "json"} if self.json_output else {}),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"num_predict": self.max_tokens}})
        served = answer.get("model")
        if served != self.model:
            raise RouteError("Ollama served a different model than requested", kind=BAD_OUTPUT)
        message = answer.get("message")
        if isinstance(message, dict) and message.get("refusal"):
            raise Refusal("local model declined; no fallback is permitted")
        content = message.get("content") if isinstance(message, dict) else None
        if not answer.get("done") or not isinstance(content, str) or not content.strip():
            raise RouteError("Ollama returned no completed text answer", kind=BAD_OUTPUT)
        return {"text": content, "cost_usd": 0.0, "served_model": served, "model_digest": digest}


class ClaudeCodeRoute:
    """The founder's installed Claude Code CLI, headless: no tools, no MCP, no disk, a spend cap."""
    provider = "claude-code"

    def __init__(self, binary: str | None = None, *, model: str | None = None, max_budget_usd: float = 0.50,
                 timeout: int = 300, runner=subprocess.run):
        self.binary = binary or shutil.which("claude")
        if not self.binary:
            raise RouteError("Claude Code CLI is not installed", kind=UNAVAILABLE)
        self.model, self.max_budget_usd, self.timeout, self.runner = model, max_budget_usd, timeout, runner
        self.name = "claude-code" + (f":{model}" if model else "")

    def complete(self, system: str, user: str, *, budget_usd=None) -> dict:
        import tempfile
        cap = self.max_budget_usd if budget_usd is None else min(self.max_budget_usd, budget_usd)
        if cap <= 0:
            raise Unbounded("no budget remains for a Claude Code call")
        argv = [self.binary, "-p", "--output-format", "json", "--tools", "", "--no-session-persistence",
                "--strict-mcp-config", "--max-budget-usd", f"{cap:.2f}", "--system-prompt", system]
        if self.model:
            argv += ["--model", self.model]
        with tempfile.TemporaryDirectory(prefix="greg-model-") as empty:   # nothing to read or write
            try:
                proc = self.runner(argv, input=user, capture_output=True, text=True, timeout=self.timeout, cwd=empty)
            except (subprocess.TimeoutExpired, OSError) as exc:
                raise RouteError(f"{type(exc).__name__}: {exc}"[:300], kind=TRANSIENT) from exc
        if proc.returncode:
            detail = (proc.stderr or proc.stdout)[-300:]
            if is_policy_text(detail):
                raise Refusal(f"Claude Code: provider policy rejected the request: {detail}"[:300],
                              kind=PROVIDER_POLICY_REFUSAL)
            raise RouteError(f"Claude Code exited {proc.returncode}: {detail}", kind=UNKNOWN)
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RouteError("Claude Code produced unreadable output", kind=BAD_OUTPUT) from exc
        if result.get("is_error"):
            detail = str(result.get("result"))[:300]
            if is_policy_text(detail):
                raise Refusal(f"Claude Code: provider policy rejected the request: {detail}"[:300],
                              kind=PROVIDER_POLICY_REFUSAL)
            raise RouteError(f"Claude Code reported an error: {detail}", kind=UNKNOWN)
        return {"text": str(result.get("result", "")), "cost_usd": result.get("total_cost_usd"),
                "served_model": self.model or "claude-code default"}


class ModelRouter:
    """Preference order, demotion after consecutive failures, a cooldown, and a true author per answer."""

    def __init__(self, routes, *, demote_after: int = 2, cooldown=timedelta(minutes=10), clock=None, record=None):
        self.routes = list(routes)
        if not self.routes:
            raise RouteError("no model route is available")
        self.demote_after, self.cooldown = demote_after, cooldown
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.record = record                     # optional callback(dict): durable routing evidence
        self.health = {r.name: {"consecutive_failures": 0, "last_failure": None} for r in self.routes}
        self.name = "router[" + ",".join(r.name for r in self.routes) + "]"
        self.last = None                         # {"route", "tried", "cost_usd"} of the latest call

    def observe(self, event: dict):
        """Replay retained routing evidence (e.g. after a restart) into route health."""
        h = self.health.get(event.get("route"))
        if h is None:
            return
        if event.get("outcome") == "ok":
            h.update(consecutive_failures=0)
        elif event.get("outcome") == "failed":
            h.update(consecutive_failures=h["consecutive_failures"] + 1, last_failure=event.get("at"))

    def order(self):
        now = self.clock()

        def demoted(route):
            h = self.health[route.name]
            if h["consecutive_failures"] < self.demote_after or not h["last_failure"]:
                return False
            return now - datetime.fromisoformat(h["last_failure"]) < self.cooldown
        return [r for r in self.routes if not demoted(r)] + [r for r in self.routes if demoted(r)]

    def complete(self, system: str, user: str, *, budget_usd=None) -> dict:
        tried, spent = [], 0.0
        for route in self.order():
            remaining = None if budget_usd is None else budget_usd - spent
            at = self.clock().isoformat()
            try:
                result = route.complete(system, user, budget_usd=remaining)
            except Refusal as exc:   # terminal: the next vendor is never asked the same thing
                tried.append({"route": route.name, "outcome": "refused", "class": exc.kind, "why": str(exc)[:200]})
                self._note(route, "refused", at, str(exc), exc.kind)
                self.last = {"route": route.name, "tried": tried, "cost_usd": spent, "refusal_class": exc.kind}
                raise
            except Unbounded as exc:
                tried.append({"route": route.name, "outcome": "skipped", "why": str(exc)[:200]})
                continue
            except RouteError as exc:   # availability failure: fall back
                tried.append({"route": route.name, "outcome": "failed", "class": exc.kind, "why": str(exc)[:200]})
                self._note(route, "failed", at, str(exc), exc.kind)
                continue
            spent += float(result.get("cost_usd") or 0.0)
            tried.append({"route": route.name, "outcome": "ok"})
            self._note(route, "ok", at, None)
            served = result.get("served_model")
            self.last = {"route": route.name, "tried": tried, "cost_usd": spent, "served_model": served,
                         "model_digest": result.get("model_digest")}
            return {"text": result["text"], "route": route.name, "served_model": served, "cost_usd": spent,
                    "tried": tried, "model_digest": result.get("model_digest")}
        self.last = {"route": None, "tried": tried, "cost_usd": spent}
        raise RouteError("every model route failed: " + "; ".join(f"{t['route']}: {t.get('why', '')}"
                                                                  for t in tried)[:600])

    def _note(self, route, outcome, at, why, kind=None):
        event = {"route": route.name, "provider": route.provider, "outcome": outcome, "at": at,
                 "why": (why or "")[:200]}
        if kind is not None:
            event["class"] = kind
        self.observe(event)
        if self.record is not None:
            self.record(event)


# INTENT-20260930-open-source-first: no route unless the founder selects one; paid routes only by name.
DEFAULT_ROUTE_ORDER: tuple = ()
PAID_ROUTE_NAMES = frozenset(("anthropic", "openai", "claude-code"))


def available_routes(secrets=None, *, config: dict | None = None, claude_budget_usd: float = 0.50) -> tuple:
    """Every model route this body can reach, in the founder's preference order.

    Returns (routes, unavailable) where unavailable names each missing route and why."""
    config = config or {}
    builders = {
        "anthropic": lambda: AnthropicRoute(secrets.resolve("anthropic_api_key", declared=("anthropic_api_key",)),
                                            model=config.get("anthropic_model", "claude-opus-5"),
                                            price=config.get("anthropic_price_per_mtok")),
        "openai": lambda: OpenAIRoute(secrets.resolve("openai_api_key", declared=("openai_api_key",)),
                                      model=config.get("openai_model", "gpt-5.5"),
                                      price=config.get("openai_price_per_mtok")),
        "claude-code": lambda: ClaudeCodeRoute(max_budget_usd=claude_budget_usd),
        "ollama": lambda: OllamaRoute(config.get("ollama_model")),
    }
    routes, unavailable = [], {}
    for name in config.get("order", DEFAULT_ROUTE_ORDER):
        if name in ("anthropic", "openai") and secrets is None:
            unavailable[name] = "no credential store"
            continue
        try:
            routes.append(builders[name]())
        except KeyError:
            unavailable[name] = "unknown route"
        except Exception as exc:   # missing key, SDK not installed, CLI absent
            unavailable[name] = f"{type(exc).__name__}: {exc}"[:160]
    return routes, unavailable


MODEL_ROUTE_NAMES = frozenset(("ollama", "anthropic", "openai", "claude-code"))


def validate_route_selection(body: dict) -> dict:
    """A founder-signed cognition selection; no credentials, URLs, policies or grants."""
    if not isinstance(body, dict) or set(body) - {"order", "ollama_model"} or "order" not in body:
        raise ValueError("model route selection needs only order and optional ollama_model")
    order = body["order"]
    if not isinstance(order, list) or len(order) > len(MODEL_ROUTE_NAMES) or any(
            not isinstance(name, str) or name not in MODEL_ROUTE_NAMES for name in order) or len(set(order)) != len(order):
        raise ValueError("model route order must name distinct registered adapters")
    if "ollama" in order:
        if "ollama_model" not in body:
            raise ValueError("selected Ollama route requires an explicit model")
        OllamaRoute(body["ollama_model"])
    elif "ollama_model" in body:
        raise ValueError("cannot retain an Ollama model when its route is detached")
    return {"order": list(order), **({"ollama_model": body["ollama_model"]} if "ollama" in order else {})}


def effective_route_config(initial: dict | None, journal) -> dict:
    """Rebuild current route selection from the canonical append-only body history."""
    config = dict(initial or {})
    changes = journal.replay("model.configured")
    if changes:
        selection = validate_route_selection(changes[-1].payload["selection"])
        config.pop("ollama_model", None)
        config.update(selection)
    return config
