"""`greg rehearse --path` reaches N3, then N4, then N7 on one throwaway body.

Three bodies that each meet one node do not count. The order is recomputed from prefixes of this one
ledger: at the head where N3 first holds, N4 and N7 do not; at the head where N4 first holds, N7 does
not; only the final head holds all three. The throwaway key stays below the founder tier, so `met`
stays false and the founder's path does not move.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from greg.body import Body
from greg.metrics import REHEARSAL_BODY, REHEARSAL_MARK
from greg import path as devpath
from greg import rehearsal

ROOT = Path(__file__).resolve().parents[2]
PATH_NODES = ("N3", "N4", "N7")


def _prefix(home: Path, head: str, dest: Path) -> Path:
    """A copy of the body whose ledger stops at ``head``, so the predicates can be read as of that moment."""
    shutil.copytree(home, dest)
    ledger = dest / "ledger.jsonl"
    kept = []
    found = False
    for line in ledger.read_text().splitlines():
        kept.append(line)
        if json.loads(line).get("hash") == head:
            found = True
            break
    assert found, head
    ledger.write_text("\n".join(kept) + "\n")
    heartbeat = dest / "heartbeat.json"
    if heartbeat.exists():
        heartbeat.unlink()
    return dest


def _structural(home: Path) -> dict:
    with Body(home) as body:
        measured = rehearsal._measure(body.journal)
        chain_ok, why = body.ledger.verify_chain()
    assert chain_ok, why
    return measured


def test_one_throwaway_body_reaches_n3_then_n4_then_n7_in_that_order(tmp_path):
    result = rehearsal.rehearse_path(directory=tmp_path / "one")
    home = Path(result["home"])
    assert result["one_body"] is True and result["sequence"] == list(PATH_NODES)
    assert result["counts_toward_vepmc"] is False and result["authenticates_founder"] is False
    assert result["founder_tier"] is False and result["used"]["payment_provider"] is False
    assert result["used"]["founder_key"] is False and result["used"]["money"] is False
    bodies = [p for p in Path(result["directory"]).iterdir() if p.is_dir() and (p / "body.json").is_file()]
    assert bodies == [home]
    mark = json.loads((home / "body.json").read_text())[REHEARSAL_MARK]
    assert mark["created_by"] == "greg rehearse"

    ledger = (home / "ledger.jsonl").read_text().splitlines()
    heads = [row["ledger_head"] for row in result["order"]]
    assert len(set(heads)) == 3
    indexes = [next(i for i, line in enumerate(ledger) if json.loads(line).get("hash") == head) for head in heads]
    assert indexes[0] < indexes[1] < indexes[2]

    at = {}
    for node, head in zip(PATH_NODES, heads):
        copy = _prefix(home, head, tmp_path / f"as-of-{node}")
        at[node] = _structural(copy)
    assert [n for n in PATH_NODES if at["N3"][n]["structurally_met"]] == ["N3"]
    assert [n for n in PATH_NODES if at["N4"][n]["structurally_met"]] == ["N3", "N4"]
    assert [n for n in PATH_NODES if at["N7"][n]["structurally_met"]] == ["N3", "N4", "N7"]
    for node in PATH_NODES:
        assert at[node][node]["met"] is False and at[node][node]["evidence_level"] == "STRUCTURAL_CANDIDATE"

    final = _structural(home)
    for node in PATH_NODES:
        assert final[node]["structurally_met"] is True and final[node]["met"] is False
        assert final[node]["evidence_level"] == "STRUCTURAL_CANDIDATE"
    with Body(home) as body:
        refused = devpath.venture_compounding(body.journal)["not_founder_tier"]
        assert refused and set(refused.values()) == {REHEARSAL_BODY}
        expressions = [event.payload["spec"]["founder_expression"]
                       for event in body.journal.replay("mission.registered")]
        assert expressions and all(text.startswith(rehearsal.LABEL) for text in expressions)
        assert not [record for record in body.journal.ledger.by_type("event")
                    if str(record.payload.get("type", "")).startswith("treasury.")]
        where = devpath.position(body.journal)
    assert where["active"]["id"] == "N1" and "N3" not in where["achieved"]
    assert "N4" not in where["achieved"] and "N7" not in where["achieved"]


def test_the_command_is_greg_rehearse_path(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    out = subprocess.run([sys.executable, "-m", "greg", "rehearse", "--path", "--dir", str(tmp_path / "cmd")],
                         capture_output=True, text=True, cwd=ROOT, env=env, timeout=180)
    assert out.returncode == 0, out.stderr + out.stdout
    result = json.loads(out.stdout)
    assert result["sequence"] == list(PATH_NODES) and result["one_body"] is True
    assert Path(result["home"]) == (tmp_path / "cmd" / "body").resolve()
