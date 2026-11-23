"""Acceptance C.G1: creation without a prewritten answer, re-verified from the retained live build.

On 2026-09-26 a real Claude Code builder (not scripted by GREG) wrote ``markdown.unchecked_count`` for a Body
mission. The run was retained as tests/evidence/greg-product/genesis-live-claude-code.json. This file re-verifies
that artifact from its own bytes, every run:

* the retained source is the one the ledger hashed, and it is not any candidate this repository prewrote;
* the builder's prompt digest recomputes from the contract's public part only (function, description, return
  type, public examples), so the held-out vectors were never shown to it;
* the source passes the static screen and the founder's frozen oracle (2 public + 4 held-out vectors) in the
  separate no-network interpreter;
* the record names the held-out oracle as verifier and the original mission as what resumed.

Each claim has a negative control that the same check rejects. Honest tier: SANDBOX re-verification of a retained
artifact. It is not a new live build (that is C.G2).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from greg import builders
from tests.unit.test_greg_genesis_builder import CONTRACT, ESCAPE, GOOD, OVERFIT, WRONG

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/evidence/greg-product/genesis-live-claude-code.json"
PUBLIC = ("function", "description", "returns", "examples")


def _record() -> dict:
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _prompt_digest(request: dict) -> str:
    return "sha256:" + _sha(builders.build_prompt(request, None))


def test_the_retained_source_is_the_one_hashed_and_no_prewritten_candidate():
    record = _record()
    [source], [built] = record["source"], record["built"]
    assert built["builder"] == "claude-code" and built["attempt"] == 1
    assert _sha(source) == built["source_sha256"]
    assert _sha(source + " ") != built["source_sha256"]                    # control: one byte more breaks it
    assert source not in (GOOD, WRONG, OVERFIT, ESCAPE)
    # Not prewritten anywhere in the code tree: no Python file outside the evidence holds its body.
    body = [line.strip() for line in source.splitlines() if line.strip().startswith(("pattern", "return"))]
    assert body
    for path in list((ROOT / "greg").rglob("*.py")) + list((ROOT / "tests").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        assert not all(line in text for line in body), f"{path} holds the built source"


def test_the_prompt_digest_recomputes_from_the_public_contract_only():
    [built] = _record()["built"]
    public = {k: CONTRACT[k] for k in PUBLIC}
    assert _prompt_digest(public) == built["prompt_sha256"], (
        "builders.build_prompt or the test contract changed since the retained 2026-09-26 build; the retained "
        "digest is evidence of what the builder saw then and must not be edited to match")
    assert built["sees"] == "description, signature, public examples only"
    # Controls: a prompt that showed any held-out vector, or feedback, has a different digest.
    for vector in CONTRACT["held_out"]:
        leaked = dict(public, examples=public["examples"] + [vector])
        assert _prompt_digest(leaked) != built["prompt_sha256"]
    assert "sha256:" + _sha(builders.build_prompt(public, ["a public check failed"])) != built["prompt_sha256"]


def test_the_retained_source_passes_the_screen_and_the_frozen_oracle_in_isolation(tmp_path):
    record = _record()
    [source] = record["source"]
    vectors = CONTRACT["examples"] + CONTRACT["held_out"]
    assert builders.screen(source) == []
    path = tmp_path / "retained.py"
    path.write_text(source)
    ok, report = builders.verify(path, vectors)
    assert ok and report["cases"] == 6 and report["failures"] == []
    # Control: the same oracle rejects a candidate that passes neither the public nor the held-out vectors.
    wrong = tmp_path / "wrong.py"
    wrong.write_text(WRONG)
    ok, report = builders.verify(wrong, vectors)
    assert not ok and report["failures"]
    assert builders.screen(ESCAPE)                                         # control: the screen does refuse
    [verified], [resolved] = record["verified"], record["resolved"]
    assert verified["passed"] is True and verified["report"]["cases"] == 6
    assert "held-out oracle" in verified["verifier"] and "never saw held-out" in verified["verifier"]
    assert resolved["resume"] == "original mission"
    assert resolved["capability_id"] == f"built.{CONTRACT['function']}.{record['built'][0]['source_sha256'][:12]}"
    assert record["appraisal"] == ["VERIFIED"] and record["achieved"] == [resolved["mission_id"]]
