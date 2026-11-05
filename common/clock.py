"""UTC clock helpers.

``utc_now_iso`` renders ``+00:00`` as ``Z``, matching the timestamps already
written to ledgers and capsules. Modules import these under their historical
private name (``from common.clock import utc_now as _now``) so existing
monkeypatch points and call sites keep working.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Timezone-aware current time in UTC."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Current UTC time as RFC 3339 text with a ``Z`` suffix."""
    return utc_now().isoformat().replace("+00:00", "Z")
