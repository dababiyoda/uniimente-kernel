"""Whether a supervised rehearsal may skip for want of supervisord.

The supervised rehearsals (tests/integration/test_greg_chromebook_rehearsal.py, test_greg_vepmc_path.py) need the
real supervisord, which stands in for the systemd user unit; no substitute supervisor is used. Where it is not on
PATH they skip, and a skip reads like a build that was exercised when it was not ("2 skipped" with the default PATH
on a machine whose supervisord sits in a virtualenv). With GREG_REQUIRE_SUPERVISOR=1 the same condition fails with
MISSING instead, so a run that must exercise the rehearsals cannot pass without them. Unset (or any other value), a
missing supervisord skips as before. GREG_REQUIRE_LANDLOCK and GREG_REQUIRE_WORKER_ISOLATION do the same for their
facilities.
"""
from __future__ import annotations

import os
import shutil

import pytest

REQUIRE = "GREG_REQUIRE_SUPERVISOR"
MISSING = ("GREG_REQUIRE_SUPERVISOR=1 and supervisord is not on PATH: the supervised rehearsal cannot run, and it "
           "may not skip (pip install -r requirements-dev.txt, or put the directory holding supervisord on PATH)")


def require_supervisord(reason: str) -> str:
    """supervisord's path on PATH. Without one, skip with ``reason``, or fail with MISSING when it is required."""
    found = shutil.which("supervisord")
    if found is None:
        if os.environ.get(REQUIRE) == "1":
            pytest.fail(MISSING, pytrace=False)
        pytest.skip(reason)
    return found
