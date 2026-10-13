"""The replay client runs the frozen baseline arms from recorded replies and
records where those replies came from. It never invents a reply."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.evaluation import arms as A
from cortex.evaluation import replay as RP
from cortex.evaluation import run as R

PROV = {"model": "test-model", "invocation": "unit test", "tool_use": "none",
        "prompt_fidelity": "exact", "limitations": "canned replies"}


def _transcript(tmp_path: Path, partition: str, reply: str, *, drop_last: bool = False) -> Path:
    replies = {}
    for item in R.load_items(partition):
        user = A._prompt(item)
        replies[RP.prompt_key(A.BASELINE_SYSTEM, user)] = reply
        for role in A.COMMITTEE_ROLES:
            replies[RP.prompt_key(f"Act as {role}. " + A.BASELINE_SYSTEM, user)] = reply
    if drop_last:
        replies.pop(sorted(replies)[-1])
    path = tmp_path / "transcript.json"
    path.write_text(json.dumps({"schema": RP.REPLAY_SCHEMA, "replies": replies}), encoding="utf-8")
    return path


def test_replayed_arms_run_through_the_frozen_harness(tmp_path):
    path = _transcript(tmp_path, "smoke", json.dumps({"disposition": "abstain", "answer": {}, "confidence": 0.5}))
    results = RP.run_replay("smoke", ["always_llm", "llm_committee", "always_abstain"], path, PROV)
    assert results["arms"]["always_llm"]["status"] == "RUN"
    assert results["arms"]["llm_committee"]["status"] == "RUN"
    assert all(i["disposition"] == "abstain" for i in results["arms"]["always_llm"]["items"])
    prov = results["arm_provenance"]
    assert prov["replayed_arms"] == ["always_llm", "llm_committee"]
    assert prov["prompts_missing"] == 0 and prov["prompts_served"] == 4 * results["item_count"]
    assert prov["model"] == "test-model" and prov["transcript_sha256"].startswith("sha256:")
    assert "REPLAYED" in results["resource_disclosure"]["always_llm"]
    assert "local model" not in results["resource_disclosure"]["llm_committee"]


def test_missing_reply_is_an_error_on_that_item_not_a_guess(tmp_path):
    path = _transcript(tmp_path, "smoke", json.dumps({"disposition": "abstain", "answer": {}, "confidence": 0.5}),
                       drop_last=True)
    results = RP.run_replay("smoke", ["always_llm", "llm_committee"], path, PROV)
    errors = [i for arm in ("always_llm", "llm_committee") for i in results["arms"][arm]["items"] if i["error"]]
    assert len(errors) == 1
    assert results["arm_provenance"]["prompts_missing"] == 1


def test_transcript_and_provenance_are_validated(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "other", "replies": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        RP.TranscriptClient.from_file(bad)
    with pytest.raises(ValueError, match="empty"):
        RP.TranscriptClient({})
    with pytest.raises(ValueError, match="64-hex"):
        RP.TranscriptClient({"short": "x"})
    with pytest.raises(ValueError, match="missing"):
        RP.validate_provenance({"model": "m"})
    client = RP.TranscriptClient({"0" * 64: "{}"})
    assert client.complete(RP.PROBE_SYSTEM, RP.PROBE_USER) == "{\"ok\": true}"
    with pytest.raises(ValueError, match="no recorded reply"):
        client.complete("system", "user")


def test_replay_does_not_touch_the_freeze():
    assert "cortex/evaluation/replay.py" not in R.FROZEN_CODE
    manifest = json.loads(R.MANIFEST.read_text(encoding="utf-8"))
    assert manifest["inputs"] == R.freeze_inputs()
