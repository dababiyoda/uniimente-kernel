"""The founder-trace check accepts both orders a real body produces, and nothing else.

Defect (job 1 on #295 at d0bf3c74, reproduced 1 run in 10 here): the goal asks for the out-of-cone move ahead of the
mission loop. When the founder's approve lands before the loop reaches the move, the mission never blocks, and the
shared check required exactly one block, so the real-process test failed with "not enough values to unpack".
"""
from __future__ import annotations

import pytest

from tests.integration.test_whole_machine_trace import founder_trace

RID, RECEIPT = "req-1", "sha256:shipped"


def _spans(*kinds: str) -> list[dict]:
    spans = []
    for kind in kinds:
        span = {"kind": kind}
        if kind == "decision.requested":
            span.update(request_id=RID, capability="fs.write")
        elif kind == "decision.answered":
            span.update(request_id=RID, answer="approve", latency_s=1.5)
        elif kind == "mission.blocked":
            span.update(capability="fs.write", reason="decision")
        elif kind == "mission.action":
            span.update(receipt=RECEIPT, capability="fs.write", status="DONE")
        spans.append(span)
    return spans


LOOP_FIRST = _spans("decision.requested", "mission.blocked", "decision.answered", "mission.unblocked",
                    "mission.action")
ANSWER_FIRST = _spans("decision.requested", "decision.answered", "mission.action")


def test_a_body_process_may_finish_either_order():
    assert founder_trace(LOOP_FIRST, RID, RECEIPT, blocked=None) is True
    assert founder_trace(ANSWER_FIRST, RID, RECEIPT, blocked=None) is False


def test_a_ticked_body_still_requires_the_block():
    assert founder_trace(LOOP_FIRST, RID, RECEIPT) is True
    with pytest.raises(AssertionError):
        founder_trace(ANSWER_FIRST, RID, RECEIPT)


@pytest.mark.parametrize("kinds", [
    ("mission.blocked", "decision.requested", "decision.answered", "mission.action"),          # block before the ask
    ("decision.requested", "decision.answered", "mission.blocked", "mission.action"),          # block after the answer
    ("decision.requested", "mission.blocked", "mission.blocked", "decision.answered", "mission.action"),  # two blocks
    ("decision.requested", "mission.action", "decision.answered"),                             # wrote before approve
])
def test_an_order_no_body_should_produce_is_refused(kinds):
    with pytest.raises(AssertionError):
        founder_trace(_spans(*kinds), RID, RECEIPT, blocked=None)


def test_a_block_that_awaited_something_else_is_refused():
    spans = _spans("decision.requested", "mission.blocked", "decision.answered", "mission.action")
    spans[1]["capability"] = "venture.assess"
    with pytest.raises(AssertionError):
        founder_trace(spans, RID, RECEIPT, blocked=None)
