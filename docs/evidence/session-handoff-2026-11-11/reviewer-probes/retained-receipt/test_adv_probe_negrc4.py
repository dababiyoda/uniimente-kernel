"""Reviewer's scratch: the body dies INSIDE the Gate, after the receipt and before the Gate's own outcome record."""
from __future__ import annotations

import pytest

from greg.body import Body
from greg.capabilities import InvocationContext
from greg.lightcone import LightCone
from tests.greg_fixtures import horizon, make_body, workspace

MID = "m:adv4"


class Killed(BaseException):
    pass


def act(body, home, data, path):
    manifest = body.registry.manifests["fs.read"]
    cone = LightCone(capabilities=frozenset({"fs.read"}), targets=("fs:*",), max_consequence_class="read_only",
                     budget_usd=0.0, horizon=horizon())
    ctx = InvocationContext(workspace=workspace(home, MID), read_roots=(data,), secrets=body.secrets,
                            manifest=manifest, journal=body.journal, artifact_root=body.layout.artifacts)
    return body.office.act(mission_id=MID, cone=cone, command_digest="sha256:" + "0" * 64, manifest=manifest,
                           adapter=body.registry.adapters["fs.read"], ctx=ctx, params={"path": str(path)},
                           target="fs:" + path.name, cost_usd=0.0, expected_outcome="observation captured",
                           evidence_refs=[], attempt="same", spent_usd=0.0, approved_scopes=set())


@pytest.mark.parametrize("inside", [True, False])
def test_p10_killed_inside_the_gate_after_the_receipt(tmp_path, capsys, inside):
    home, _, _, data = make_body(tmp_path)
    path = (data / "in.txt") if inside else (tmp_path / "outside.txt")
    path.write_text("hello")
    with Body(home) as body:
        append = body.ledger.append

        def dies(record_type, payload, *a, **k):
            if record_type == "outcome":
                raise Killed("SIGKILL after the receipt, before the Gate's outcome record")
            return append(record_type, payload, *a, **k)
        body.ledger.append = dies
        with pytest.raises(Killed):
            act(body, home, data, path)
        receipts = [r.payload["result"]["result_class"] for r in body.ledger.by_type("receipt")]
        outcomes = len(body.ledger.by_type("outcome"))
    out = []
    for _ in range(2):
        with Body(home) as body:
            again = act(body, home, data, path)
            out.append((again.status, again.reasons[:1], bool(again.receipt_hash),
                        len(body.ledger.by_type("grant_dispatch")), len(body.ledger.by_type("receipt"))))
    with capsys.disabled():
        print(f"\nP10 inside={inside}: kept receipts {receipts}, gate outcomes {outcomes}; asked again twice: {out}")
    assert [o[0] for o in out] == (["DONE", "DONE"] if inside else ["REFUSED", "REFUSED"])
    assert out[0][3:] == out[1][3:] == (1, 1)
