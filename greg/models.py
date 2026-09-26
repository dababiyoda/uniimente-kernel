"""Provider-independent model routing: GREG is not married to one model vendor.

One interface (``complete(system, user) -> text``) over every model route the body can
reach: the Anthropic API, the OpenAI API, and the founder's installed Claude Code CLI.
The router tries routes in preference order, demotes a route that keeps failing, and
records which route actually produced each answer, so a planner draft or a built
capability always names its true author.

What routing never does:

* **Shop a refusal.** A model that declines is an answer, not an outage. The router
  stops there; it does not re-ask another vendor to get around a safety decision.
* **Spend without a bound.** For spending contexts (Capability Genesis builds) each
  API route computes the largest output it may generate so that its worst-case cost
  fits the remaining founder-signed budget; a route whose price is unknown cannot be
  bounded and is skipped. The CLI route enforces its own ``--max-budget-usd``.
* **Take credentials from the environment.** Keys come only from declared credential
  handles (``anthropic_api_key``, ``openai_api_key``); base URLs are pinned.

Models propose; they never authorize. Nothing here grants authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import shutil
import subprocess


class RouteError(Exception):
    """A route could not produce an answer (outage, bad credential, bad output). Try the next."""


class Refusal(RouteError):
    """The model declined. Terminal: never retried on another provider."""


class Unbounded(RouteError):
    """The route's worst-case cost cannot be bounded under the remaining budget."""


# Provider error codes/messages that mean "declined by policy", not "unavailable". An SDK raises these
# as ordinary HTTP errors (e.g. OpenAI 400 content_policy_violation); treating them as outages would
# let the router re-ask another vendor, which is exactly the policy bypass routing must never do.
POLICY_MARKERS = ("content_policy", "policy_violation", "invalid_prompt", "safety", "moderation", "refusal")


def _classify(exc: Exception) -> RouteError:
    """Availability failure (fallback allowed) or policy refusal (terminal)."""
    code = str(getattr(exc, "code", "") or "")
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        code += " " + str((body.get("error") or {}).get("code", "") if isinstance(body.get("error"), dict) else "")
    text = f"{code} {exc}".lower()
    if any(marker in text for marker in POLICY_MARKERS):
        return Refusal(f"provider declined by policy: {type(exc).__name__}: {exc}"[:300])
    return RouteError(f"{type(exc).__name__}: {exc}"[:300])


# USD per million tokens (input, output). Anthropic prices from the Claude API reference;
# other providers' prices are supplied by the founder's configuration, never guessed.
ANTHROPIC_PRICES = {"claude-opus-5": (5.0, 25.0), "claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5": (2.0, 10.0),
                    "claude-fable-5-1": (10.0, 50.0), "claude-haiku-4-5": (1.0, 5.0)}
MAX_OUTPUT_TOKENS = 16000
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
        # Economic metadata is configuration: a configured price wins over the built-in table, so a
        # price change is corrected without code; an unknown model has no price and is skipped with money at stake.
        self.price = tuple(price) if price else ANTHROPIC_PRICES.get(model)
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
        except Exception as exc:   # SDK/network errors: an outage, unless the provider says "policy"
            raise _classify(exc) from exc
        if response.stop_reason == "refusal":
            category = getattr(getattr(response, "stop_details", None), "category", None)
            raise Refusal(f"model declined (refusal: {category})")
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = getattr(response, "usage", None)
        cost = None
        if usage is not None and self.price:
            cost = (usage.input_tokens * self.price[0] + usage.output_tokens * self.price[1]) / 1e6
        return {"text": text, "cost_usd": cost}


class OpenAIRoute:
    """OpenAI models via the official ``openai`` SDK Responses API (optional dependency)."""
    provider = "openai"

    def __init__(self, api_key: str, *, model: str = "gpt-5.5", price=None, client=None):
        self.model, self.name, self.price = model, f"openai:{model}", tuple(price) if price else None
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1", max_retries=2)
        self.client = client

    def complete(self, system: str, user: str, *, budget_usd=None) -> dict:
        max_tokens = _output_bound(self.price, system, user, budget_usd)
        try:
            response = self.client.responses.create(model=self.model, instructions=system, input=user,
                                                    max_output_tokens=max_tokens)
        except Exception as exc:
            raise _classify(exc) from exc
        refusals = [part for item in (getattr(response, "output", None) or [])
                    for part in (getattr(item, "content", None) or []) if getattr(part, "type", "") == "refusal"]
        if refusals:
            raise Refusal(f"model declined: {getattr(refusals[0], 'refusal', '')}"[:300])
        text = getattr(response, "output_text", "") or ""
        if not text:
            raise RouteError(f"empty response (status {getattr(response, 'status', 'unknown')})")
        usage = getattr(response, "usage", None)
        cost = None
        if usage is not None and self.price:
            cost = (usage.input_tokens * self.price[0] + usage.output_tokens * self.price[1]) / 1e6
        return {"text": text, "cost_usd": cost}


class ClaudeCodeRoute:
    """The founder's installed Claude Code CLI, headless: no tools, no MCP, no disk, a spend cap."""
    provider = "claude-code"

    def __init__(self, binary: str | None = None, *, model: str | None = None, max_budget_usd: float = 0.50,
                 timeout: int = 300, runner=subprocess.run):
        self.binary = binary or shutil.which("claude")
        if not self.binary:
            raise RouteError("Claude Code CLI is not installed")
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
                raise RouteError(f"{type(exc).__name__}: {exc}"[:300]) from exc
        if proc.returncode:
            raise RouteError(f"Claude Code exited {proc.returncode}: {(proc.stderr or proc.stdout)[-300:]}")
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RouteError("Claude Code produced unreadable output") from exc
        if result.get("is_error"):
            raise RouteError(f"Claude Code reported an error: {str(result.get('result'))[:300]}")
        return {"text": str(result.get("result", "")), "cost_usd": result.get("total_cost_usd")}


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
            except Refusal as exc:
                tried.append({"route": route.name, "outcome": "refused", "why": str(exc)[:200]})
                self._note(route, "refused", at, str(exc))
                self.last = {"route": route.name, "tried": tried, "cost_usd": spent}
                raise
            except Unbounded as exc:
                tried.append({"route": route.name, "outcome": "skipped", "why": str(exc)[:200]})
                continue
            except RouteError as exc:
                tried.append({"route": route.name, "outcome": "failed", "why": str(exc)[:200]})
                self._note(route, "failed", at, str(exc))
                continue
            spent += float(result.get("cost_usd") or 0.0)
            tried.append({"route": route.name, "outcome": "ok"})
            self._note(route, "ok", at, None)
            self.last = {"route": route.name, "tried": tried, "cost_usd": spent}
            return {"text": result["text"], "route": route.name, "cost_usd": spent, "tried": tried}
        self.last = {"route": None, "tried": tried, "cost_usd": spent}
        raise RouteError("every model route failed: " + "; ".join(f"{t['route']}: {t.get('why', '')}"
                                                                  for t in tried)[:600])

    def _note(self, route, outcome, at, why):
        event = {"route": route.name, "provider": route.provider, "outcome": outcome, "at": at,
                 "why": (why or "")[:200]}
        self.observe(event)
        if self.record is not None:
            self.record(event)


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
    }
    routes, unavailable = [], {}
    for name in config.get("order", ["anthropic", "openai", "claude-code"]):
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
