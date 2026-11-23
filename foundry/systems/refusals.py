"""The refusal probe the Foundry systems' ``exercise`` demonstrations share.

An exercise shows that a system refuses what it must refuse: it runs a call, and records the system's
reason when one of the expected errors stops it, or a fixed value when the call goes through. Eleven
systems carried the same six-line closure for this. They differ only in what they record, so each call
site states its rule here instead of carrying a copy:

* ``errors``: the exception class, or tuple of classes, that counts as a refusal;
* ``accepted``: what a call that went through records (``None`` in most systems, ``False`` in some);
* ``limit``: how many characters of the reason are kept (``None`` keeps all of it).

Every exercise result is hashed as execution evidence, so these rules are part of that evidence; an
unexpected exception still propagates. ``business_compiler``, ``registry`` and ``shell`` record
something else (problem lists, the exception type, a shell verb) and keep their own probes.
"""
from __future__ import annotations

from typing import Any, Callable


def refusal_recorder(errors: type[BaseException] | tuple[type[BaseException], ...], *, accepted: Any = None,
                     limit: int | None = None) -> tuple[dict, Callable[[str, Callable[[], Any]], None]]:
    """Return ``(refusals, refused)``: ``refused(label, fn)`` runs ``fn`` and records its outcome under ``label``."""
    refusals: dict = {}

    def refused(label: str, fn: Callable[[], Any]) -> None:
        try:
            fn()
            refusals[label] = accepted
        except errors as exc:
            refusals[label] = str(exc)[:limit]

    return refusals, refused
