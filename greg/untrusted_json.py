"""One reader for JSON that GREG did not write: a worker's report, a built candidate's output, an organ's message,
a model's reply, an inbox file.

``json.loads`` fails two ways on a document nested deeper than the interpreter's recursion limit (about 1,000
levels). On some shapes (a deep array) it raises RecursionError, not ValueError, so a caller that refused
unreadable output with ``except ValueError`` or ``except json.JSONDecodeError`` let it escape, and untrusted output
of a few kilobytes stopped the body or left an appraisal UNCERTAIN instead of refused (re-checks of 48d66f5f and
bdfca22d). On others (a deep object) it succeeds, and the value raises RecursionError later, wherever it is hashed,
printed or written back (``repr``, ``json.dumps``, the ledger's digest). This reader refuses both as
``json.JSONDecodeError``, so every existing handler for unreadable output refuses them as unreadable output."""

from __future__ import annotations

import json

MAX_DEPTH = 200     # far deeper than any record GREG reads; far shallower than the recursion limit


class TooDeep(json.JSONDecodeError):
    """A document nested deeper than MAX_DEPTH, refused as unreadable output."""


def loads(data):
    """``json.loads``, with a document nested deeper than MAX_DEPTH raised as TooDeep (a ``json.JSONDecodeError``)."""
    doc = data if isinstance(data, str) else ""
    try:
        value = json.loads(data)
    except RecursionError:
        raise TooDeep("document nested too deeply to read", doc, 0) from None
    if not isinstance(value, (dict, list)):
        return value
    stack = [(value, 1)]
    while stack:        # iterative: a recursive walk would fail on exactly the documents it is meant to refuse
        item, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise TooDeep(f"document nested deeper than {MAX_DEPTH} levels", doc, 0)
        children = item.values() if isinstance(item, dict) else item
        # only containers are pushed: a wide array of scalars costs one pass over it, not a stack entry per number
        # (re-check of 6933be8c, F5: 2M ints took 0.48 s and 146 MB on top of a 0.09 s parse)
        stack.extend((child, depth + 1) for child in children if isinstance(child, (dict, list)))
    return value
