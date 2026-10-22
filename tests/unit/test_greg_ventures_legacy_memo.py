"""A venture memo receipted before Track B's revenue section (on PR #184 before the 2026-10-16 merge) still renders
and verifies after it. Its inputs carry neither ``revenue`` nor ``cognition``; the merged ``render`` read
``inputs["revenue"]`` and raised KeyError, so a standing mission's later appraisal of such a memo failed."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from greg import ventures
from tests.unit.test_greg_ventures import _minimal_inputs

ROOT = Path(__file__).resolve().parents[2]
BEFORE = "f59eee4"      # PR #184's last commit before the Track B merge


def _ventures_at(commit, tmp_path):
    source = subprocess.run(["git", "show", f"{commit}:greg/ventures.py"], cwd=ROOT, capture_output=True)
    if source.returncode:
        pytest.skip(f"{commit} is not in this clone")
    path = tmp_path / "ventures_before.py"
    path.write_bytes(source.stdout)
    spec = importlib.util.spec_from_file_location("greg._ventures_before", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_a_memo_receipted_before_the_revenue_section_renders_as_it_was_receipted(tmp_path):
    legacy = _minimal_inputs()
    assert "revenue" not in legacy and "cognition" not in legacy
    before = _ventures_at(BEFORE, tmp_path)
    assert ventures.render(legacy) == before.render(legacy)
    assert "## Revenue" not in ventures.render(legacy)


def _delivered(inputs, root):
    """A receipt whose memo is exactly the render of ``inputs``, delivered under ``root`` (the flip is derived)."""
    import hashlib
    inputs = {**inputs, "flip": ventures.flip_condition(inputs["railscout"]["appraisal"],
                                                       inputs["assessment"]["go_no_go"], inputs["binding"]["verdict"])}
    text = ventures.render(inputs).encode("utf-8")
    path = root / "memo.md"
    path.write_bytes(text)
    return {"inputs": inputs, "inputs_digest": ventures.inputs_digest(inputs), "path": str(path),
            "sha256": hashlib.sha256(text).hexdigest()}


def test_the_appraiser_accepts_a_legacy_memo_and_holds_any_memo_with_receipts_to_the_rule(tmp_path):
    """The compatibility path is only for a memo with neither a conclusion nor receipts. A memo that carries a
    cognition receipt but no conclusion (one that drops the conclusion to dodge the rule) is refused."""
    root = tmp_path / "deliver"
    root.mkdir()
    gone = {k: str(tmp_path / "absent" / k) for k in ("manifest", "railscout_root", "source_root", "wmi_root")}
    legacy = {**_minimal_inputs(), "paths": gone}
    ok, why = ventures.verify_delivery(_delivered(legacy, root), root)
    # every memo-level check passed, the revenue rule included; only the organ re-derivation is left (no organs here)
    assert not ok and why.startswith("organ re-run failed"), why
    receipt = {"receipt_id": "r", "abstention_state": "NONE", "output": {"low": 1, "high": 2, "central": 1.5}}
    ok, why = ventures.verify_delivery(_delivered({**legacy, "cognition": {"revenue": receipt}}, root), root)
    assert not ok and "revenue conclusion is not the rule" in why, why
