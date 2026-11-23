"""S22.A2 / S35.A3: a built candidate is attacked before it registers (hostile input, resources, determinism).

Before this, a candidate that passed the static screen and the founder-frozen oracle registered at once. A candidate
with a bug on any long input (LENGTH_BUG) passed every short frozen vector and was attached, and the first real
document broke it in service. Now the same isolated interpreter attacks it with shapes no vector covers, runs each
twice, and reads each input's CPU before the candidate counts. The builder learns the shape and the failure class,
never an input's text, and the next candidate is judged the same way.
"""
import json
from pathlib import Path

import pytest

from greg import builders
from tests.greg_fixtures import drop, make_body, signed
from tests.unit.test_greg_genesis_builder import CONTRACT, GOOD, _mission, _run

# Correct on every frozen vector (all short); raises on any input longer than 400 characters.
LENGTH_BUG = ("import re\n\ndef run(text):\n"
              "    if len(text) > 400:\n        raise ValueError('too long')\n"
              "    return len(re.findall(r'^[ \\t]*[-*+] \\[ \\]', text, re.M))\n")
# Correct on short input; on long input its answer depends on the interpreter's per-process hash seed.
NONDETERMINISTIC = ("import re\n\ndef run(text):\n"
                    "    if len(text) > 1000:\n        return hash(text) % 1000003\n"
                    "    return len(re.findall(r'^[ \\t]*[-*+] \\[ \\]', text, re.M))\n")
# Correct on every vector, but answers a string where the contract's examples answer integers.
WRONG_KIND = ("import re\n\ndef run(text):\n"
              "    if text.isspace():\n        return 'none'\n"
              "    return len(re.findall(r'^[ \\t]*[-*+] \\[ \\]', text, re.M))\n")


def _candidate(tmp_path, source):
    path = tmp_path / "candidate.py"
    path.write_text(source)
    return path


def test_a_correct_candidate_survives_every_attack(tmp_path):
    report = builders.attack(_candidate(tmp_path, GOOD), CONTRACT["examples"])
    assert report["passed"] is True and report["inputs"] == len(builders.attack_inputs(CONTRACT["examples"]))
    assert report["failures"] == report["wrong_kind"] == report["nondeterministic"] == report["slow"] == []


@pytest.mark.parametrize("source, field", [(LENGTH_BUG, "failures"), (NONDETERMINISTIC, "nondeterministic"),
                                          (WRONG_KIND, "wrong_kind")])
def test_each_attack_class_refuses_a_candidate_the_frozen_oracle_accepts(tmp_path, source, field):
    path = _candidate(tmp_path, source)
    passed, _ = builders.verify(path, CONTRACT["examples"] + CONTRACT["held_out"])
    assert passed is True                                                   # the oracle alone would register it
    report = builders.attack(path, CONTRACT["examples"])
    assert report["passed"] is False and report[field], report


def test_an_input_that_spends_more_than_its_cpu_share_is_slow(tmp_path, monkeypatch):
    real = builders.execute

    def costly(source_path, inputs, *, timeout=builders.RUN_TIMEOUT):
        results = real(source_path, inputs, timeout=timeout)
        return [dict(r, cpu=builders.ATTACK_CPU_SECONDS + 1) if len(t) == 0 else r for r, t in zip(results, inputs)]

    monkeypatch.setattr(builders, "execute", costly)
    report = builders.attack(_candidate(tmp_path, GOOD), CONTRACT["examples"])
    assert report["passed"] is False and [s["input"] for s in report["slow"]] == ["empty"]


def test_attack_inputs_are_deterministic_bounded_and_the_feedback_carries_no_input_text(tmp_path):
    first, second = builders.attack_inputs(CONTRACT["examples"]), builders.attack_inputs(CONTRACT["examples"])
    assert first == second and len({label for label, _ in first}) == len(first)
    assert all(len(text) <= builders.MAX_INPUT for _, text in first)
    report = builders.attack(_candidate(tmp_path, LENGTH_BUG), CONTRACT["examples"])
    feedback = builders.attack_feedback(report)
    assert "ValueError" in feedback and "half the input ceiling" in feedback
    for example in CONTRACT["examples"] + CONTRACT["held_out"]:
        if example["input_text"]:
            assert example["input_text"] not in feedback


def test_genesis_refuses_the_length_bug_before_registration_and_registers_the_next_candidate(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    builder = builders.StaticBuilder(LENGTH_BUG, GOOD, identity="static-test")
    body, states = _run(home, builder)
    assert "ACHIEVED" in states
    j = body.journal
    verified = [e.payload for e in j.replay("genesis.verified")]
    assert [v["passed"] for v in verified] == [False, True]
    attacked = verified[0]["report"]
    assert attacked["failed_cases"] == 0 and attacked["attack"]["passed"] is False      # oracle green, attack red
    assert verified[1]["report"]["attack"]["passed"] is True
    registered = [e.payload["manifest"]["capability_id"] for e in j.replay("capability.registered")]
    assert len(registered) == 1 and registered[0].endswith(verified[1]["capability_id"].split(":")[1][:12])
    assert any("failed the attack stage" in e.payload["result"] for e in j.replay("genesis.route"))
    feedback = builder.calls[1]["feedback"][0]
    assert "adversarial input" in feedback
    assert all(ex["input_text"] not in json.dumps(builder.calls[1]) for ex in CONTRACT["held_out"] if ex["input_text"])
    body.close()


SHAPES = ["empty", "whitespace only", "one newline", "NUL", "control characters", "decode-replacement characters",
          "mixed scripts, emoji and bidi marks", "one line at half the input ceiling", "many blank lines",
          "examples joined with CRLF", "examples joined with NUL", "examples without the trailing newline",
          "examples repeated to half the input ceiling"]


@pytest.mark.parametrize("shape", SHAPES)
def test_every_declared_shape_is_run_and_alone_refuses_a_candidate_that_breaks_only_on_it(tmp_path, shape):
    import hashlib
    attacks = dict(builders.attack_inputs(CONTRACT["examples"]))
    assert list(attacks) == SHAPES                                          # no shape silently dropped or added
    target = hashlib.sha256(attacks[shape].encode("utf-8", "surrogatepass")).hexdigest()
    source = GOOD.replace("def run(text):\n", "import hashlib\n\ndef run(text):\n"
                          f"    if hashlib.sha256(text.encode('utf-8', 'surrogatepass')).hexdigest() == '{target}':\n"
                          "        raise KeyError('only this shape')\n")
    report = builders.attack(_candidate(tmp_path, source), CONTRACT["examples"])
    assert report["passed"] is False and [f["input"] for f in report["failures"]] == [shape]
