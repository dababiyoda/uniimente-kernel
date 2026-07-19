"""Approval queue: the human command channel for judgment.

Extracted from DALEOBANKS ``services/operator_line.py`` (kernel Phase 2)
into the kernel SDK package. Organs contact the operator only when judgment is
required. Commands arrive over any transport the organ wires in
(DALEOBANKS: SMS via Twilio webhook, or the dashboard); every path runs
through :meth:`ApprovalQueue.handle_command`.

Command grammar (first word, case-insensitive; ``<code>`` is the
request's 4-character approval code, also accepted as a unique id
prefix), preserved exactly from the organ original:

    YES <code>          approve exactly that request — never standing
                        autonomy (a bare YES works only when exactly one
                        P1 request is pending; otherwise it is rejected)
    NO [<code>]         reject the request
    EDIT [<code>] <text> approve with the operator's replacement text
    WHY [<code>]        explain why the system is asking
    HOLD [<code>]       park the request for later (YES/NO still work on it)
    FREEZE              immediately disarm all outbound action (kill switch)
    NEWS                a short briefing of what the system has been sensing
    INTERVIEW           the question the system most wants answered now
    OPINION: <thought>  store the thought as a self-signal, never doctrine

Doctrine: duplicate pending requests (same kind and payload) collapse —
the queue never manufactures approval demand. Requests expire; silence is
never consent. Every prompt and command is ledgered.

Generalization points versus the DALEOBANKS original:

- No ORM. ``ApprovalRecord`` is a plain dataclass; storage sits behind
  the two-method ``ApprovalStore`` protocol (``InMemoryApprovalStore``
  for tests and local runs).
- The SMS notifier, live-state reader, news provider, interview provider,
  and opinion recorder are injected callables. Kernel defaults work off
  the store alone; organs inject their richer versions.
"""

from __future__ import annotations

import os
import secrets
import string
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from uniimente_kernel.ledger import DecisionLedger, KillSwitch

HELP_TEXT = (
    "Commands: YES <code>, NO [code], EDIT [code] <text>, WHY [code], "
    "HOLD [code], FREEZE, NEWS, INTERVIEW, OPINION: <thought>"
)

_DECIDABLE = ("pending", "held")


def _new_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(4))


@dataclass
class ApprovalRecord:
    kind: str
    summary: str
    payload: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    priority: str = "P2"
    strongest_objection: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    code: str = field(default_factory=_new_code)
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_via: Optional[str] = None


class ApprovalStore(Protocol):
    def all(self) -> List[ApprovalRecord]: ...
    def put(self, record: ApprovalRecord) -> None: ...


class InMemoryApprovalStore:
    def __init__(self) -> None:
        self._records: Dict[str, ApprovalRecord] = {}

    def all(self) -> List[ApprovalRecord]:
        return list(self._records.values())

    def put(self, record: ApprovalRecord) -> None:
        self._records[record.id] = record


def _default_ttl_hours() -> int:
    try:
        return int(os.getenv("APPROVAL_TTL_HOURS", "72"))
    except ValueError:
        return 72


class ApprovalQueue:
    """Files approval requests and executes operator commands."""

    def __init__(
        self,
        store: ApprovalStore,
        ledger: DecisionLedger,
        kill_switch: KillSwitch,
        *,
        notify: Optional[Callable[[str], bool]] = None,
        live_state: Optional[Callable[[], bool]] = None,
        news_provider: Optional[Callable[[], List[str]]] = None,
        interview_provider: Optional[Callable[[], Optional[str]]] = None,
        opinion_recorder: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.store = store
        self.ledger = ledger
        self.kill_switch = kill_switch
        self._notify = notify
        self._live_state = live_state
        self._news_provider = news_provider
        self._interview_provider = interview_provider
        self._opinion_recorder = opinion_recorder

    # ------------------------------------------------------------------ #
    # Outbound: asking for judgment
    # ------------------------------------------------------------------ #
    @property
    def notifier_configured(self) -> bool:
        return self._notify is not None

    def request_approval(
        self,
        kind: str,
        summary: str,
        payload: Optional[Dict[str, Any]] = None,
        rationale: str = "",
        priority: str = "P2",
        strongest_objection: str = "",
        ttl_hours: Optional[int] = None,
    ) -> ApprovalRecord:
        """File an ApprovalRecord and prompt the operator. Duplicate pending
        requests (same kind and payload) collapse into the existing one —
        the queue must never manufacture approval demand. Requests expire;
        silence is never consent."""
        payload = payload or {}
        if payload:  # only a non-empty payload identifies the same act
            for existing in self.store.all():
                if (existing.status == "pending" and existing.kind == kind
                        and existing.payload == payload):
                    return existing

        ttl = ttl_hours if ttl_hours is not None else _default_ttl_hours()
        request = ApprovalRecord(
            kind=kind, summary=summary, payload=payload,
            rationale=rationale, priority=priority,
            strongest_objection=strongest_objection,
            expires_at=datetime.now(UTC) + timedelta(hours=ttl),
        )
        self.store.put(request)

        notified = False
        if self._notify is not None:
            notified = bool(self._notify(
                f"[{request.code}/{priority}] {summary} — reply "
                f"YES {request.code} / NO {request.code} / WHY {request.code}"
            ))
        self.ledger.record("operator_prompted", {
            "id": request.id,
            "code": request.code,
            "kind": kind,
            "priority": priority,
            "summary": summary[:120],
            "notified": notified,
        })
        return request

    def sweep_expired(self) -> int:
        """Close pending requests past their expiry. Queue overflow and
        operator silence must never become implicit approval."""
        expired = 0
        now = datetime.now(UTC)
        for request in self.store.all():
            if (request.status == "pending" and request.expires_at
                    and now >= request.expires_at):
                request.status = "expired"
                request.decided_at = now
                request.decided_via = "expiry"
                expired += 1
                self.store.put(request)
                self.ledger.record("approval_expired", {
                    "id": request.id, "code": request.code, "kind": request.kind,
                })
        return expired

    # ------------------------------------------------------------------ #
    # Inbound: executing operator commands
    # ------------------------------------------------------------------ #
    def handle_command(self, text: str, via: str = "dashboard") -> Dict[str, Any]:
        self.sweep_expired()
        raw = (text or "").strip()
        if not raw:
            return self._done("HELP", via, ok=False, reply=HELP_TEXT)

        head, _, rest = raw.partition(" ")
        cmd = head.upper().rstrip(":")
        rest = rest.strip()

        if cmd in ("YES", "NO", "HOLD"):
            return self._decide(cmd, rest, via)
        if cmd == "EDIT":
            return self._edit(rest, via)
        if cmd == "WHY":
            return self._why(rest, via)
        if cmd == "FREEZE":
            self.kill_switch.set_armed(False, reason="operator_freeze")
            return self._done(cmd, via, ok=True, reply="Frozen. All outbound action is disarmed.")
        if cmd == "NEWS":
            return self._done(cmd, via, ok=True, reply=self._news_briefing())
        if cmd == "INTERVIEW":
            return self._done(cmd, via, ok=True, reply=self._interview_question())
        if cmd == "OPINION":
            return self._opinion(rest, via)
        return self._done(cmd, via, ok=False, reply=f"Unknown command. {HELP_TEXT}")

    def _decide(self, cmd: str, arg: str, via: str) -> Dict[str, Any]:
        request, error = self._resolve(arg, command=cmd)
        if request is None:
            return self._done(cmd, via, ok=False, reply=error)

        status = {"YES": "approved", "NO": "rejected", "HOLD": "held"}[cmd]
        request.status = status
        request.decided_at = datetime.now(UTC)
        request.decided_via = via
        self.store.put(request)
        reply = f"{status.capitalize()} [{request.code}]: {request.summary}"
        if cmd == "YES":
            reply += " (this approval covers only this request)"
        return self._done(cmd, via, ok=True, reply=reply, request_id=request.id)

    def _edit(self, rest: str, via: str) -> Dict[str, Any]:
        maybe_code, _, text = rest.partition(" ")
        request, _ = self._resolve(maybe_code, command="EDIT") if maybe_code else (None, None)
        if request is None:
            # No code given — the whole rest is the replacement text.
            request, error = self._resolve("", command="EDIT")
            text = rest
            if request is None:
                return self._done("EDIT", via, ok=False, reply=error)
        text = text.strip()
        if not text:
            return self._done("EDIT", via, ok=False, reply="EDIT needs replacement text.")

        request.payload["operator_edit"] = text
        request.status = "edited"
        request.decided_at = datetime.now(UTC)
        request.decided_via = via
        self.store.put(request)
        return self._done(
            "EDIT", via, ok=True,
            reply=f"Edited and approved with your text [{request.code}]: {request.summary}",
            request_id=request.id,
        )

    def _why(self, arg: str, via: str) -> Dict[str, Any]:
        request, error = self._resolve(arg, command="WHY")
        if request is None:
            return self._done("WHY", via, ok=False, reply=error)
        reply = f"[{request.code}/{request.priority} {request.kind}] {request.summary}"
        if request.rationale:
            reply += f" — because: {request.rationale}"
        content = request.payload.get("content")
        if content:
            reply += f' — draft: "{str(content)[:200]}"'
        return self._done("WHY", via, ok=True, reply=reply, request_id=request.id)

    def _opinion(self, thought: str, via: str) -> Dict[str, Any]:
        thought = thought.strip()
        if not thought:
            return self._done("OPINION", via, ok=False, reply="OPINION needs a thought after the colon.")
        extra: Dict[str, Any] = {}
        if self._opinion_recorder is not None:
            extra["opinion_ref"] = str(self._opinion_recorder(thought))
        return self._done(
            "OPINION", via, ok=True,
            reply="Recorded as a self-signal. I will weigh it, not obey it.",
            extra=extra,
        )

    def _resolve(self, arg: str, command: str = "YES") -> Tuple[Optional[ApprovalRecord], Optional[str]]:
        """Find the request a command targets.

        With an argument, match the approval code exactly or a unique id
        prefix. Bare YES is honored only when exactly one P1 request is
        pending — everything else must name its code, so the wrong action
        can never be approved by accident. Bare NO/HOLD/WHY/EDIT work when
        exactly one request is pending (rejecting or querying the only
        request is not a spoofable act)."""
        arg = (arg or "").strip().lower()
        candidates: List[ApprovalRecord] = sorted(
            (r for r in self.store.all() if r.status in _DECIDABLE),
            key=lambda r: r.created_at, reverse=True,
        )
        if arg:
            matches = [
                r for r in candidates
                if r.code.lower() == arg or r.id.lower().startswith(arg)
            ]
            if len(matches) == 1:
                return matches[0], None
            if not matches:
                return None, f"No open request matches '{arg.upper()}'."
            return None, f"'{arg.upper()}' is ambiguous ({len(matches)} matches)."

        pending = [r for r in candidates if r.status == "pending"]
        if not pending:
            return None, "No pending requests."
        if len(pending) > 1:
            codes = ", ".join(f"{r.code}({r.priority})" for r in pending[:5])
            return None, f"{len(pending)} requests pending — name one: {codes}"

        only = pending[0]
        if command == "YES" and only.priority != "P1":
            return None, (
                f"Include the code to approve: YES {only.code} "
                f"({only.priority} requests always need their code)"
            )
        return only, None

    # ------------------------------------------------------------------ #
    # Briefings
    # ------------------------------------------------------------------ #
    def _news_briefing(self) -> str:
        lines: List[str] = []
        if self._news_provider is not None:
            try:
                lines.extend(self._news_provider() or [])
            except Exception:
                lines.append("- Briefing provider failed.")
        if not lines:
            lines.append("- Nothing sensed recently.")
        pending = [r for r in self.store.all() if r.status == "pending"]
        lines.append(f"Pending approvals: {len(pending)}.")
        if self._live_state is not None:
            try:
                armed = bool(self._live_state())
            except Exception:
                armed = False
            lines.append(f"Live mode: {'ARMED' if armed else 'disarmed'}.")
        return "\n".join(lines)

    def _interview_question(self) -> str:
        pending = sorted(
            (r for r in self.store.all() if r.status == "pending"),
            key=lambda r: r.created_at,
        )
        if pending:
            oldest = pending[0]
            return (
                f"Decide this first: {oldest.summary} "
                f"(YES {oldest.code} / NO {oldest.code})"
            )
        if self._interview_provider is not None:
            try:
                question = self._interview_provider()
            except Exception:
                question = None
            if question:
                return question
        return "What outcome would make the next 30 days a clear win for you?"

    def _done(
        self,
        command: str,
        via: str,
        ok: bool,
        reply: str,
        request_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {"command": command, "via": via, "ok": ok}
        if request_id:
            record["request_id"] = request_id
        if extra:
            record.update(extra)
        self.ledger.record("operator_command", record)
        result = {"ok": ok, "reply": reply}
        if request_id:
            result["request_id"] = request_id
        return result


__all__ = [
    "ApprovalQueue",
    "ApprovalRecord",
    "ApprovalStore",
    "InMemoryApprovalStore",
    "HELP_TEXT",
]
