"""The ledger records WHICH kind of device a designation and a closure ran on, without redefining VEPMC.

device_class is information beside platform: it is forgeable, never identity or ownership, and never a
VEPMC condition. Which device is the first VEPMC body (Mac or Chromebook) stays the founder's ruling.
"""
import pytest

from events.spine import EventSpine
from greg import doctor, metrics
from greg.body import Body
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import Clock, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_missions import run, submit
from tests.unit.test_greg_one_machine_gates import closure

NINE = ("founder_signed", "interface_detached", "persistent_runtime", "real_capability", "approval_boundary",
        "interruption_survived", "appraised_verified", "founder_accepted", "founder_body")


@pytest.mark.parametrize("crostini, expected", [(True, "chromeos_linux"), (False, "linux_other")])
def test_designation_and_closure_record_device_class_and_vepmc_conditions_are_unchanged(
        tmp_path, monkeypatch, crostini, expected):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor, "is_crostini", lambda markers=None: crostini)
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        designated = body.apply(signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}))
    assert designated["result"]["device_class"] == expected
    note = workspace(home, "m:device") / "n.txt"
    submit(home, key, body_id, "MISSION", mission("m:device", checks=[note_check("n", note, "x")],
                                                  strategies=[write_strategy("w", "n.txt", "x", ["n"])],
                                                  capabilities=["fs.read", "fs.write"]))
    run(home, Clock(), ticks=4)
    with Body(home) as body:
        [context] = [e.payload for e in body.journal.replay("mission.closure_context")]
        result = metrics.vepmc(body.journal)
    assert context["device_class"] == expected
    assert tuple(result["conditions"]) == NINE and "device_class" not in metrics.CONDITIONS   # not redefined
    row = result["missions"][0]
    assert row["device_class"] == row["designated_device_class"] == expected
    assert "device_class" not in row["missing"] and "designated_device_class" not in row["missing"]


def test_old_record_shapes_still_count_and_a_forged_designation_lends_no_device_class(tmp_path):
    """Journal records are append-only: closures recorded before the field read as unknown and still
    count (device_class is no condition), and an unaccepted designation never supplies one."""
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "4" * 64, path=str(tmp_path / "l.jsonl"))),
                      actor="spiffe://uniimente.internal/test/device-class")
    journal.record("body.designated", {"command_digest": "forged", "body_id": "b1", "platform": "Linux",
                                       "device_class": "macos", "purpose": "first_founder_body"}, key=["forged"])
    closure(journal, "m:closure", {"verdict": "ACCEPTED"})     # every record in its pre-device_class shape
    result = metrics.vepmc(journal)
    [row] = result["missions"]
    assert result["VEPMC"] == 1 and row["missing"] == []
    assert row["device_class"] is None and row["designated_device_class"] is None


@pytest.mark.parametrize("system, crostini, expected", [("Darwin", True, "macos"), ("Linux", True, "chromeos_linux"),
                                                         ("Linux", False, "linux_other"), ("Windows", False, "other")])
def test_device_class_reads_the_running_system(monkeypatch, system, crostini, expected):
    monkeypatch.setattr(doctor.platform, "system", lambda: system)
    monkeypatch.setattr(doctor, "is_crostini", lambda markers=None: crostini)
    assert doctor.device_class() == expected
