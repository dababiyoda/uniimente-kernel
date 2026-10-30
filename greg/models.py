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
* **Let the provider pick the model.** No request sends server-side ``fallbacks: "default"``
  (which re-runs a refused request on a provider-chosen model and keeps the conversation
  there for about an hour). Substitution is possible only through an explicit, priced
  ``anthropic_fallback_models`` list in the founder's configuration. An Anthropic answer
  carries ``requested_model``, the provider-reported ``served_model`` and ``substituted``
  (``None`` when the provider names no model); an answer from a model outside that list is
  withheld as ``model_substitution`` (terminal, like a refusal). Routes that do not check
  model identity (OpenAI, Claude Code) report ``substituted`` as ``None`` (not checked), never
  as ``False``.
* **Spend without a bound.** For spending contexts (Capability Genesis builds) each
  API route computes the largest output it may generate so that its worst-case cost
  (across every attempt of a configured fallback chain) fits the remaining founder-signed
  budget; a route whose price is unknown cannot be bounded and is skipped. The CLI route
  enforces its own ``--max-budget-usd``.
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
import os
from pathlib import Path
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
MODEL_SUBSTITUTION = "model_substitution"     # served by a model outside the founder's policy
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
    """A route could not produce an answer (outage, bad credential, bad output). Try the next.

    ``cost_usd`` is what the failed attempt was still billed (a refusal after billed attempts, an
    empty answer whose reasoning used every output token, a reported CLI error), so the router books
    it and bounds the next route by what truly remains."""

    def __init__(self, message: str = "", *, kind: str = UNKNOWN, cost_usd=None):
        super().__init__(message)
        self.kind, self.cost_usd = kind, cost_usd


class Refusal(RouteError):
    """The model or its provider declined. Terminal: never retried on another provider."""

    def __init__(self, message: str = "", *, kind: str = SAFETY_REFUSAL, cost_usd=None):
        super().__init__(message, kind=kind, cost_usd=cost_usd)


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


class ModelSubstitution(RouteError):
    """The provider answered with a model the founder did not select. Terminal: the answer is
    withheld, and no other route is asked (the substitution may itself follow a refusal)."""

    def __init__(self, message: str = "", *, requested=None, served=None, cost_usd=None):
        super().__init__(message, kind=MODEL_SUBSTITUTION)
        # The withheld answer was still billed: its cost is carried so the budget books it.
        self.requested, self.served, self.cost_usd = requested, served, cost_usd


class Unbounded(RouteError):
    """The route's worst-case cost cannot be bounded under the remaining budget."""


# USD per million tokens (input, output). Anthropic prices from the Claude API reference;
# other providers' prices are supplied by the founder's configuration, never guessed.
ANTHROPIC_PRICES = {"claude-opus-5": (5.0, 25.0), "claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5": (2.0, 10.0),
                    "claude-sonnet-5-5": (2.0, 10.0), "claude-opus-4-8": (5.0, 25.0),
                    "claude-fable-5-1": (10.0, 50.0), "claude-haiku-4-5": (1.0, 5.0), "claude-haiku-5-5": (0.10, 0.50)}
# Long-prompt rate cards: above this many prompt tokens the whole request bills at the upper price.
ANTHROPIC_LONG_PROMPT_PRICES = {"claude-haiku-5-5": (100_000, (0.50, 2.50))}
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


def _dearest(*prices):
    """Per-component maximum of (input, output) prices: a bound or a booking that is never under."""
    prices = [p for p in prices if p]
    return (max(p[0] for p in prices), max(p[1] for p in prices)) if prices else None


def _tiered(model: str, price, prompt_tokens: int):
    """A model's price for a prompt of this size (some models bill a long prompt on a higher rate card)."""
    tier = ANTHROPIC_LONG_PROMPT_PRICES.get(model)
    return _dearest(price, tier[1]) if price and tier and prompt_tokens > tier[0] else price


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


class _APIRoute:
    """A paid API route: the vendor SDK in the body process, or, on a body with confined egress (#26), in a confined
    child behind the relay (``greg.model_child``). Either way one function calls the SDK and normalises its answer."""
    provider = ""

    def _setup(self, api_key: str, client, egress):
        if egress is not None and client is not None:
            raise ValueError("a confined route calls its SDK in a confined child; an in-process client contradicts it")
        self.egress = egress
        self._api_key = api_key if egress is not None else None   # held only to hand to the confined child
        if client is None and egress is None:
            from greg import model_child
            client = model_child.client(self.provider, api_key)
        self.client = client

    def _answer(self, system: str, user: str, max_tokens: int, *, fallbacks=(), fallback_beta=None) -> dict:
        """One call, in process or confined. ``fallbacks`` is only ever the founder's explicit allowlist."""
        if self.egress is not None:
            return confined_call(self.provider, self._api_key, self.model, system, user, max_tokens, self.egress,
                                 fallbacks=fallbacks, fallback_beta=fallback_beta)
        from greg import model_child
        try:
            return model_child.call(self.provider, self.client, self.model, system, user, max_tokens,
                                    fallbacks=fallbacks, fallback_beta=fallback_beta)
        except Exception as exc:   # SDK/network errors, classified: a policy verdict is not an outage
            raise _route_failure(exc) from exc

    def _cost(self, answer: dict):
        if self.price and answer.get("input_tokens") is not None and answer.get("output_tokens") is not None:
            return (answer["input_tokens"] * self.price[0] + answer["output_tokens"] * self.price[1]) / 1e6
        return None


class AnthropicRoute(_APIRoute):
    """Claude via the official Anthropic SDK (optional dependency ``anthropic``).

    Model identity is the founder's choice, not the provider's. The request names one model
    and sends no server-side ``fallbacks``, so a classifier refusal comes back as a refusal
    instead of being re-run on a provider-selected substitute (which would be refusal
    shopping by another name). Substitution exists only as an explicit, priced allowlist
    (``fallback_models``), sent in the array form so the provider cannot pick the model; the
    spend bound then covers the whole chain (every permitted model may run as its own attempt)
    at the most expensive listed model, the cost is every billed attempt, and every answer
    records requested, served and substituted. An answer served by any model outside
    {requested} ∪ allowlist is withheld (``ModelSubstitution``), never returned as the
    requested model's work; a response that names no model is reported as unknown, never as
    the requested one. On a body with confined egress (#26) the same request runs in a confined child
    (``greg.model_child``) behind the relay; the policy and the accounting below are identical.
    """
    provider = "anthropic"
    FALLBACK_BETA = "server-side-fallback-2026-06-01"   # the array form; the "default" scalar form is never sent

    def __init__(self, api_key: str, *, model: str = "claude-opus-5", price=None, client=None,
                 fallback_models=(), fallback_prices=None, egress=None):
        self.model, self.name = model, f"anthropic:{model}"
        # Prices are operational evidence, not constants: a configured price supersedes the built-in
        # snapshot without a code change. A malformed configured price is not silently replaced by the
        # (possibly stale) snapshot: the route has no price, so a spending context skips it (Unbounded).
        self.price = _price(price) if price is not None else ANTHROPIC_PRICES.get(model)
        listed = isinstance(fallback_models, (list, tuple))   # a bare string (e.g. "default") is not a list
        if not listed or not all(isinstance(m, str) and m for m in fallback_models):
            raise ValueError("fallback_models must be an explicit list of model ids (the 'default' form is refused)")
        if model in fallback_models or len(set(fallback_models)) != len(fallback_models):
            raise ValueError("fallback_models must be distinct and must not repeat the requested model")
        if fallback_prices is not None and not isinstance(fallback_prices, dict):   # never silently the snapshot
            raise ValueError("fallback_prices must map each fallback model id to its (input, output) price")
        fallback_prices = fallback_prices or {}
        self.fallback_models = tuple(fallback_models)
        self.fallback_price = {m: (_price(fallback_prices[m]) if m in fallback_prices else ANTHROPIC_PRICES.get(m))
                               for m in self.fallback_models}
        unpriced = [m for m, p in self.fallback_price.items() if p is None]
        if unpriced:   # an unpriced substitute could not be bounded or billed truthfully
            raise ValueError(f"fallback model(s) without a known price: {', '.join(unpriced)}")
        self._setup(api_key, client, egress)

    def _price_of(self, model: str, prompt_tokens: int = 0):
        return _tiered(model, self.price if model == self.model else self.fallback_price[model], prompt_tokens)

    def _bound_price(self, prompt_tokens: int = 0):
        """The worst-case per-token price across every model that may answer a prompt of this size."""
        if self.price is None:
            return None
        return _dearest(*(self._price_of(m, prompt_tokens) for m in (self.model, *self.fallback_models)))

    def _same_model(self, served: str, wanted: str) -> bool:
        # the API may report a dated snapshot of the alias that was requested
        return served == wanted or re.fullmatch(re.escape(wanted) + r"-\d{8}", served or "") is not None

    @staticmethod
    def _attempts_cost(attempts, price):
        """Every attempt the provider may bill: the per-attempt usage (``iterations``) is the source of truth (top-level
        usage covers only the attempt that produced the message, and a declined attempt can be billed); top-level
        usage is used only when the response reports no iterations. Unknown token counts make the cost unknown."""
        if not price or not attempts or any(a.get("input_tokens") is None or a.get("output_tokens") is None
                                            for a in attempts):
            return None
        return sum(a["input_tokens"] * price[0] + a["output_tokens"] * price[1] for a in attempts) / 1e6

    def complete(self, system: str, user: str, *, budget_usd=None) -> dict:
        prompt_tokens = _estimate_tokens(system + user)
        # The server-side chain may run every permitted model as its own attempt, each re-reading the prompt
        # and inheriting this max_tokens, so the signed budget is divided across the whole chain.
        attempts = 1 + len(self.fallback_models)
        max_tokens = _output_bound(self._bound_price(prompt_tokens), system, user,
                                   None if budget_usd is None else budget_usd / attempts)
        answer = self._answer(system, user, max_tokens, fallbacks=self.fallback_models,
                              fallback_beta=self.FALLBACK_BETA)
        served = answer.get("served_model") or None          # the provider's report; never filled in by us
        iterations = list(answer.get("iterations") or [])
        fell_back = any(i.get("type") == "fallback_message" for i in iterations)
        usage = {"input_tokens": answer.get("input_tokens"), "output_tokens": answer.get("output_tokens")}
        billed_prompt = max([a.get("input_tokens") or 0 for a in (iterations or [usage])], default=0)
        if answer["refusal"]:
            # Declined, but every attempt was billed (#178); which permitted model declined is not reliably
            # reported, so each attempt is booked at the dearest permitted price (never under-booked).
            raise Refusal(f"model declined (refusal: {answer['refusal_detail']})", kind=SAFETY_REFUSAL,
                          cost_usd=self._attempts_cost(iterations or [usage], self._bound_price(billed_prompt)))
        withheld = False
        if served is None and (self.fallback_models or not fell_back):
            # No served model reported: unknown, not proof that the requested model answered. The request
            # permitted only {requested} ∪ allowlist, so it is billed at the dearest of those.
            answered_by, price = None, self._bound_price(billed_prompt)
        elif self._same_model(served, self.model) and not fell_back:
            answered_by, price = self.model, self._price_of(self.model, billed_prompt)
        else:
            answered_by = next((m for m in self.fallback_models if self._same_model(served, m)), None)
            if answered_by is not None:
                price = self._price_of(answered_by, billed_prompt)
            else:
                # Billed at the served model's list price when known, else at the dearest known price:
                # an unknown substitute is over-booked, never under-booked.
                known = next((m for m in ANTHROPIC_PRICES if self._same_model(served, m)), None)
                price = (_tiered(known, ANTHROPIC_PRICES[known], billed_prompt) if known else
                         _dearest(self._bound_price(billed_prompt), *ANTHROPIC_PRICES.values()))
                withheld = True
        if len(iterations) > 1:
            # Conservative and simple: an iteration does not reliably name the model that ran it (a declined
            # attempt is a plain "message"), so every attempt of a multi-attempt answer is priced at the
            # dearest of the answer's price and every permitted model's price: over-booked, never under.
            price = _dearest(price, self._bound_price(billed_prompt))
        cost = self._attempts_cost(iterations or [usage], price)
        if withheld:
            raise ModelSubstitution(f"requested {self.model}, served {served}: outside the founder's model "
                                    f"policy; the answer is withheld", requested=self.model, served=served,
                                    cost_usd=cost)
        # the provider's own report of the model that answered, next to the one we asked for; unknown stays None
        substituted = (True if fell_back else None) if answered_by is None else answered_by != self.model
        return {"text": answer["text"], "cost_usd": cost, "served_model": served, "requested_model": self.model,
                "substituted": substituted, "fallback_policy": list(self.fallback_models)}


class OpenAIRoute(_APIRoute):
    """OpenAI models via the official ``openai`` SDK Responses API (optional dependency)."""
    provider = "openai"

    def __init__(self, api_key: str, *, model: str = "gpt-5.5", price=None, client=None, egress=None):
        self.model, self.name, self.price = model, f"openai:{model}", _price(price)
        self._setup(api_key, client, egress)

    def complete(self, system: str, user: str, *, budget_usd=None) -> dict:
        # classified on failure: HTTP 400 invalid_prompt is a policy verdict, not an outage
        answer = self._answer(system, user, _output_bound(self.price, system, user, budget_usd))
        cost = self._cost(answer)   # a refusal or an empty answer was still billed (#178)
        if answer["refusal"]:
            raise Refusal(f"model declined: {answer['refusal_detail'] or ''}"[:300], kind=SAFETY_REFUSAL,
                          cost_usd=cost)
        if not answer["text"]:     # e.g. status incomplete: reasoning used every output token, and it was billed
            raise RouteError(f"empty response (status {answer.get('status', 'unknown')})", kind=BAD_OUTPUT,
                             cost_usd=cost)
        # the provider's report or None: a missing report is not filled in with the model we asked for
        return {"text": answer["text"], "cost_usd": cost, "served_model": answer.get("served_model") or None}


CONFINED_CALL_SECONDS = 660   # the SDK's own 600 s timeout, plus its retries' backoff


def _namespace(scratch: str, *, readonly=()) -> list:
    """A bubblewrap network namespace (no privilege): read-only root with the founder's and the body's homes hidden,
    private /tmp, and the call's scratch directory. ``readonly`` re-exposes what the call needs (a trust anchor, the
    CLI itself). Refused (fail closed) without namespaces."""
    from foundry.systems.relay_door import namespace_argv
    from greg.worker_isolation import WorkerIsolationError, _backend
    try:
        _backend(require_bubblewrap=True)
    except WorkerIsolationError as exc:
        raise RouteError(f"confined egress needs bubblewrap network namespaces here: {exc}", kind=UNAVAILABLE) from None
    return namespace_argv(writable=[scratch], readonly=readonly, chdir=scratch)


def _scoped_relay(relay, identity: str, host: str):
    """A per-call relay sharing the body relay's journal and mandated proxy, allowing exactly one provider host."""
    from foundry.systems.segmentation import Relay
    return Relay({identity: {"allow": [[host, 443]], "external": True}}, relay.journal,
                 connect=relay.connect, proxy=relay.proxy)


CLI_LOGIN = ".claude/.credentials.json"   # the one file of the founder's home the Claude Code CLI needs


def cli_home(scratch: str) -> tuple[dict, list]:
    """A private home for the Claude Code CLI inside the call's scratch directory, holding a copy of its login and
    nothing else of the founder's home; returns the environment that points the CLI at it and the read-only paths
    its installation needs (the CLI's own directory and, for an npm install, the Node runtime)."""
    import os
    home = Path(scratch) / "home"
    source = Path.home() / CLI_LOGIN
    (home / CLI_LOGIN).parent.mkdir(parents=True, exist_ok=True)
    if source.is_file() and not source.is_symlink():
        shutil.copyfile(source, home / CLI_LOGIN)
        (home / CLI_LOGIN).chmod(0o600)
    node = shutil.which("node")
    return {**os.environ, "HOME": str(home)}, [str(Path(node).resolve().parent.parent)] if node else []


class _ChildFailure(Exception):
    """A confined child's failure, rebuilt with the fields ``classify`` reads (status, body, class name)."""


def _rebuilt(error: dict) -> BaseException:
    name = str(error.get("type") or "Exception")
    base = (ConnectionError if name in ("ConnectionError", "ConnectionRefusedError", "ConnectionResetError",
                                        "ConnectionAbortedError", "BrokenPipeError")
            else TimeoutError if name == "TimeoutError" else _ChildFailure)
    exc = type(name if name.isidentifier() else "ChildFailure", (base,), {})(str(error.get("message", ""))[:500])
    exc.status_code, exc.body = error.get("status_code"), error.get("body")
    return exc


def confined_call(provider: str, api_key: str, model: str, system: str, user: str, max_tokens: int, relay, *,
                  fallbacks=(), fallback_beta=None) -> dict:
    """Run ``greg.model_child`` in a network namespace behind the relay door. The key crosses only stdin."""
    import os
    import sys
    import tempfile
    import urllib.parse
    from pathlib import Path
    from foundry.systems.relay_door import Door, door_argv
    from greg import model_child
    host = urllib.parse.urlsplit(model_child.BASE_URLS[provider]).hostname
    identity = f"model.{provider}"
    root = str(Path(__file__).resolve().parents[1])
    child = [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {root!r}); "
                                         "from greg.model_child import main; main()"]
    request = json.dumps({"provider": provider, "api_key": api_key, "model": model, "system": system, "user": user,
                          "max_tokens": max_tokens, "fallbacks": list(fallbacks), "fallback_beta": fallback_beta})
    trust = {k: os.environ[k] for k in ("SSL_CERT_FILE", "SSL_CERT_DIR") if os.environ.get(k)}
    if os.environ.get("GREG_EGRESS_CAFILE"):          # the operator's trust anchor for a TLS-intercepting proxy
        trust["SSL_CERT_FILE"] = os.environ["GREG_EGRESS_CAFILE"]
    with tempfile.TemporaryDirectory(prefix="greg-model-") as scratch:
        argv = _namespace(scratch, readonly=tuple(trust.values()))
        with Door(_scoped_relay(relay, identity, host), identity) as door:
            try:
                proc = subprocess.run(argv + door_argv(sys.executable, door.fd, child), pass_fds=[door.fd],
                                      input=request, capture_output=True, text=True, timeout=CONFINED_CALL_SECONDS,
                                      env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": scratch, **trust})
            except subprocess.TimeoutExpired as exc:
                raise RouteError(f"confined {provider} call did not finish", kind=TRANSIENT) from exc
    try:
        answer = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RouteError(f"confined {provider} call failed: {proc.stderr[-300:]}", kind=UNKNOWN) from None
    if not answer.get("ok"):
        raise _route_failure(_rebuilt(answer.get("error") or {}))
    return answer["result"]


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


# The CLI's own model swaps (a refused turn re-run on a fallback model, or any other substitution) are off: GREG
# routes between models itself, never shops a refusal, and names the model that wrote each answer.
CLI_NO_MODEL_FALLBACK = {"CLAUDE_CODE_NO_MODEL_FALLBACK": "1", "CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK": "1"}


def cli_report(proc) -> dict | None:
    """The Claude Code CLI's JSON result on stdout, or None when there is none.

    The CLI prints it, with what the run cost and why it stopped, whether or not it succeeded: it exits 1 on every
    ``is_error`` result (a refusal, an API error, an exhausted ``--max-budget-usd``), so the exit status alone says
    neither what was billed nor whether the model declined. With verbose output on in the founder's Claude Code
    settings it prints every message as a JSON array, the result object last."""
    try:
        result = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(result, list):
        result = next((m for m in reversed(result) if isinstance(m, dict) and m.get("type") == "result"), None)
    return result if isinstance(result, dict) else None


def cli_cost(result: dict, cap: float) -> float:
    """What a CLI run cost: its own finite, non-negative ``total_cost_usd``, else the cap it ran under. Missing
    billing is never booked as zero (the CLI prints null when its session cost is not a number), as
    ``workers.worker_spend`` reserves the whole cap for the same evidence."""
    billed = result.get("total_cost_usd")
    if isinstance(billed, bool) or not isinstance(billed, (int, float)) or not math.isfinite(billed) or billed < 0:
        return float(cap)
    return float(billed)


def cli_reason(result: dict) -> str:
    """Why the CLI says the run ended: ``result`` on success, ``errors`` on every ``error_*`` subtype."""
    if result.get("result") is not None:
        return str(result["result"])
    errors = result.get("errors")
    return "; ".join(map(str, errors)) if isinstance(errors, list) and errors else str(result.get("subtype") or "")


def cli_authors(result: dict) -> list[str]:
    """The models the CLI's report says wrote the turn (``modelUsage``), its auxiliary haiku calls left out."""
    usage = result.get("modelUsage")
    return sorted(k for k in usage if "haiku" not in k) if isinstance(usage, dict) else []


class ClaudeCodeRoute:
    """The founder's installed Claude Code CLI, headless: no tools, no MCP, no disk, a spend cap."""
    provider = "claude-code"

    def __init__(self, binary: str | None = None, *, model: str | None = None, max_budget_usd: float = 0.50,
                 timeout: int = 300, runner=subprocess.run, egress=None):
        self.binary = binary or shutil.which("claude")
        if not self.binary:
            raise RouteError("Claude Code CLI is not installed", kind=UNAVAILABLE)
        self.model, self.max_budget_usd, self.timeout, self.runner = model, max_budget_usd, timeout, runner
        self.egress = egress          # #26: on a confined body the CLI runs behind the relay door
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
                proc = (self.runner(argv, input=user, capture_output=True, text=True, timeout=self.timeout, cwd=empty,
                                    env={**os.environ, **CLI_NO_MODEL_FALLBACK})
                        if self.egress is None else self._behind_door(argv, user, empty))
            except (subprocess.TimeoutExpired, OSError) as exc:
                # A CLI killed at the timeout may have spent up to its cap: booked, never as zero.
                raise RouteError(f"{type(exc).__name__}: {exc}"[:300], kind=TRANSIENT,
                                 cost_usd=cap if isinstance(exc, subprocess.TimeoutExpired) else None) from exc
        result = cli_report(proc)
        if result is None:
            if proc.returncode:
                detail = (proc.stderr or proc.stdout)[-300:]
                if is_policy_text(detail):
                    raise Refusal(f"Claude Code: provider policy rejected the request: {detail}"[:300],
                                  kind=PROVIDER_POLICY_REFUSAL)
                raise RouteError(f"Claude Code exited {proc.returncode}: {detail}", kind=UNKNOWN)
            raise RouteError("Claude Code produced unreadable output", kind=BAD_OUTPUT)
        billed = cli_cost(result, cap)                 # what the run cost, failed or not; unknown books the cap
        detail = cli_reason(result)[:300]
        if result.get("stop_reason") == "refusal":
            # The model declined, as AnthropicRoute reads the same stop reason: an answer, never shopped elsewhere.
            raise Refusal(f"Claude Code: the model declined: {detail}"[:300], kind=SAFETY_REFUSAL, cost_usd=billed)
        if result.get("is_error") or proc.returncode:
            if is_policy_text(detail):
                raise Refusal(f"Claude Code: provider policy rejected the request: {detail}"[:300],
                              kind=PROVIDER_POLICY_REFUSAL, cost_usd=billed)
            exited = f" (exit {proc.returncode})" if proc.returncode else ""
            raise RouteError(f"Claude Code reported an error{exited}: {detail}", kind=UNKNOWN, cost_usd=billed)
        authors = cli_authors(result)
        if self.model and any(self.model not in a for a in authors):
            # Another model wrote the answer (a CLI swap the variables above did not stop): withheld, billed.
            raise ModelSubstitution(f"Claude Code: requested {self.model}, the report names {authors}"[:300],
                                    requested=self.model, served=authors, cost_usd=billed)
        return {"text": str(result.get("result", "")), "cost_usd": billed,
                "served_model": self.model or (", ".join(authors) or "claude-code default")}

    def _behind_door(self, argv: list, user: str, scratch: str):
        """The CLI in a network namespace whose only way out is the relay, allowlisted for the Anthropic API host. Its
        home is a private one holding a copy of its login; the founder's home and the body's are hidden."""
        import sys
        import urllib.parse
        from pathlib import Path
        from foundry.systems.relay_door import Door, door_argv
        from greg import model_child
        env, runtime = cli_home(scratch)
        namespace = _namespace(scratch, readonly=(str(Path(self.binary).resolve().parent), *runtime))
        host = urllib.parse.urlsplit(model_child.BASE_URLS["anthropic"]).hostname
        with Door(_scoped_relay(self.egress, "model.claude-code", host), "model.claude-code") as door:
            return self.runner(namespace + door_argv(sys.executable, door.fd, argv), input=user, capture_output=True,
                               text=True, timeout=self.timeout, cwd=scratch, pass_fds=[door.fd],
                               env={**env, **CLI_NO_MODEL_FALLBACK})


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
                spent += float(exc.cost_usd or 0.0)    # declined, but billed
                tried.append({"route": route.name, "outcome": "refused", "class": exc.kind, "why": str(exc)[:200],
                              **({"cost_usd": exc.cost_usd} if exc.cost_usd is not None else {})})
                self._note(route, "refused", at, str(exc), exc.kind)
                self.last = {"route": route.name, "tried": tried, "cost_usd": spent, "refusal_class": exc.kind}
                raise
            except ModelSubstitution as exc:   # terminal: an unselected model's answer is not ours to use
                spent += float(exc.cost_usd or 0.0)    # withheld, but billed: the budget still books it
                tried.append({"route": route.name, "outcome": "substituted", "class": exc.kind,
                              "requested": exc.requested, "served": exc.served, "cost_usd": exc.cost_usd,
                              "why": str(exc)[:200]})
                self._note(route, "substituted", at, str(exc), exc.kind)
                self.last = {"route": route.name, "tried": tried, "cost_usd": spent, "refusal_class": exc.kind}
                raise
            except Unbounded as exc:
                tried.append({"route": route.name, "outcome": "skipped", "why": str(exc)[:200]})
                continue
            except RouteError as exc:   # availability failure: fall back (a billed failure is still booked)
                spent += float(exc.cost_usd or 0.0)
                tried.append({"route": route.name, "outcome": "failed", "class": exc.kind, "why": str(exc)[:200],
                              **({"cost_usd": exc.cost_usd} if exc.cost_usd is not None else {})})
                self._note(route, "failed", at, str(exc), exc.kind)
                continue
            spent += float(result.get("cost_usd") or 0.0)
            tried.append({"route": route.name, "outcome": "ok"})
            self._note(route, "ok", at, None)
            served = result.get("served_model")
            self.last = {"route": route.name, "tried": tried, "cost_usd": spent, "served_model": served,
                         "model_digest": result.get("model_digest")}
            return {"text": result["text"], "route": route.name, "served_model": served, "cost_usd": spent,
                    "tried": tried, "model_digest": result.get("model_digest"),
                    "requested_model": result.get("requested_model"),
                    "substituted": result.get("substituted")}   # None = the route did not (or could not) check
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


def admitted_ollama_route(model: str):
    """The local route only when its license permits GREG's use.

    ``licensing.ollama_model`` reads the installed weights' license, and
    ``qualify_use`` judges that assessment against GREG's use. Anything that is
    not a permitting verdict — no store, no license, an unreadable layer, an
    unclassified text, a restricted license — fails closed. The route that is
    returned carries the assessment and the use qualification.
    """
    route = OllamaRoute(model)
    try:
        from greg import licensing
    except Exception as exc:
        raise RouteError(f"license: license check unavailable ({type(exc).__name__})") from exc
    try:
        assessment = licensing.ollama_model(model)
    except Exception as exc:
        raise RouteError(f"license: license check failed ({type(exc).__name__})") from exc
    if not isinstance(assessment, dict):
        raise RouteError("license: no assessment for this model; it is not selected")
    subject = assessment.get("subject") if isinstance(assessment.get("subject"), dict) else {}
    try:
        qualification = licensing.qualify_use([assessment], licensing.GREG_USE, subject)
    except Exception as exc:
        raise RouteError(f"license: use qualification failed ({type(exc).__name__})") from exc
    if not isinstance(qualification, dict) or qualification.get("verdict") != licensing.COMPATIBLE:
        why = str(qualification.get("reason") or "") if isinstance(qualification, dict) else ""
        raise RouteError("license: " + (why or str(assessment.get("reason") or "license does not permit this use")))
    route.license_assessment = assessment
    route.license_use = qualification
    return route


def available_routes(secrets=None, *, config: dict | None = None, claude_budget_usd: float = 0.50,
                     egress=None) -> tuple:
    """Every model route this body can reach, in the founder's preference order.

    ``egress`` is the body's #26 relay when the founder enabled confined egress: every paid route then reaches its
    provider only through it. Returns (routes, unavailable) where unavailable names each missing route and why.
    An Ollama model whose license does not permit GREG's use is unavailable, with that reason, and is not selected."""
    config = config or {}
    builders = {
        "anthropic": lambda: AnthropicRoute(secrets.resolve("anthropic_api_key", declared=("anthropic_api_key",)),
                                            model=config.get("anthropic_model", "claude-opus-5"),
                                            price=config.get("anthropic_price_per_mtok"),
                                            fallback_models=config.get("anthropic_fallback_models", ()),
                                            fallback_prices=config.get("anthropic_fallback_prices_per_mtok"), egress=egress),
        "openai": lambda: OpenAIRoute(secrets.resolve("openai_api_key", declared=("openai_api_key",)),
                                      model=config.get("openai_model", "gpt-5.5"),
                                      price=config.get("openai_price_per_mtok"), egress=egress),
        "claude-code": lambda: ClaudeCodeRoute(max_budget_usd=claude_budget_usd, egress=egress),
        "ollama": lambda: admitted_ollama_route(config.get("ollama_model")),
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
        try:
            admitted_ollama_route(body["ollama_model"])
        except RouteError as exc:
            raise ValueError(str(exc)) from exc
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
