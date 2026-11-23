"""A restored package capability whose catalog candidate is gone can never serve (review of #201/#230 on #196).

#230 lets a founder-DETACHED capability stay DETACHED across a restart even when its pins changed, so the founder can
re-attach it; each adapter re-checks its pins before it runs. A package whose catalog candidate was removed had no
adapter to re-check anything: it was registered with a no-op that returned None, which a founder attach from DETACHED
could reach until the next restart. It now refuses.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from greg.capabilities import CapabilityError
from greg.genesis import Genesis


def test_a_package_without_its_catalog_candidate_is_restored_with_an_adapter_that_refuses():
    registered = {}
    owner = SimpleNamespace(
        registry=SimpleNamespace(register=lambda manifest, adapter, state: registered.update(adapter=adapter,
                                                                                               state=state)),
        _restored_state=lambda cid, state, why, key: state)
    manifest = SimpleNamespace(provenance={"version": "1", "package_digest": "d", "common_mode": "m"})
    origin = {"function": "no.such.function", "runner": "no-such-runner", "distribution": "no-such-distribution"}
    Genesis._restore_package(owner, "cap:gone", manifest, origin, "DETACHED")
    assert registered["state"] == "DETACHED"
    with pytest.raises(CapabilityError, match="no package candidate"):
        registered["adapter"]({}, None)
