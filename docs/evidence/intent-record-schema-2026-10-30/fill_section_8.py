"""The one-time section 8 fill of greg/path.json (2026-10-30), kept as evidence of where every value came from.

Run once from the repository root at the commit before it landed: ``python -B <this file>``. For every horizon
whose feasibility is not CURRENTLY_BUILDABLE it appends ``enabling_interfaces``, ``feasible_when`` and
``falsified_by`` (greg/path.py SECTION_8_FIELDS):

* ``feasible_when`` is the horizon's own ``prerequisite`` (``recorded_as``), for every horizon;
* ``falsified_by`` is recorded only where text already states a failure or falsification condition for that
  capability: the nearest falsifiable experiment of its frontier backcasts and the ``falsification`` of the
  cognition P-node it names (``recorded_as``, never copied), PR #155's destination falsifiers in
  greg/cognition/advantage.py, and directive 2026-10-28 sentences phrased as failure (sections 39 and 44);
* ``enabling_interfaces`` is recorded only where the path or the directive names a protocol, API, contract,
  record type, decision kind or channel for that capability, copied verbatim;
* everything else is ``{"unrecorded": "<reason>"}``.

The script refuses a horizon that already carries a section 8 field. tests/unit/test_horizon_section_8.py checks
every copied value against its source.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path.cwd()
PATH = ROOT / "greg/path.json"
DIRECTIVE = "docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md"
ADVANTAGE = "greg/cognition/advantage.py#DESTINATIONS"
HERE = "greg/path.json#"

NO_INTERFACE = ("no interface for this capability is named on the path, in its founder sources or in the 2026-10-28 "
                "directive; section 8 asks for its enabling interfaces")
NO_FALSIFIER = ("no condition that would falsify this capability is recorded on the path, in its founder sources, "
                "in PR #155's destination falsifiers or in the 2026-10-28 directive; section 8 asks for one")


def nfe(backcast: str) -> dict:
    return {"recorded_as": f"frontier_backcasts/{backcast}/nearest_falsifiable_experiment"}


def p_node(node: str) -> dict:
    return {"recorded_as": f"workstreams/cognition_cortex/nodes/{node}/falsification"}


INTERFACES = {
    "remote_interface_iphone": {"value": ["verified HTTPS path", "Ed25519 WebCrypto"],
                                "source": [HERE + "prerequisite", HERE + "activation_evidence"]},
    "computer_use": {"value": ["APIs", "native application interfaces", "CLI", "filesystem", "browser protocols",
                               "OS automation", "Accessibility", "scripting", "screen understanding", "pointer input",
                               "keyboard input", "computer-use models"],
                     "source": DIRECTIVE + "#31-computer-use"},
    "mac_support": {"value": ["launchd plist", "sandbox-exec", "Keychain"], "source": HERE + "current_reality"},
    "community_feedback": {"value": "an authorized public channel (DALEOBANKS)", "source": HERE + "prerequisite"},
    "human_work_fabric": {"value": "greg.asks", "source": HERE + "frontier_backcasts/"
                          "large_scale_human_machine_coordination/nearest_falsifiable_experiment"},
    "research_in_organ": {"value": "a typed contract consumed by one GREG mission",
                          "source": HERE + "activation_evidence"},
    "compute_growth": {"value": "a recorded BODY_AVAILABILITY or COMPUTE decision", "source": HERE + "prerequisite"},
    "multi_body": {"value": "NODE_ENROLL", "source": HERE + "current_reality"},
    "sensors_actuators": {"value": "the same Gate and receipts", "source": HERE + "intended_effect"},
    "robotics": {"value": "a simulated actuator contract",
                 "source": HERE + "frontier_backcasts/advanced_robotic_embodiment/nearest_falsifiable_experiment"},
    "situational_awareness": {"value": "a typed contract to the HUD tool", "source": HERE + "prerequisite"},
    "jarvis_integration": {"value": "one interface, one ledger, one Gate", "source": HERE + "current_reality"},
    "cognitive_ecology": {"value": "contracts/cortex-receipt.schema.json",
                          "source": HERE + "frontier_backcasts/substrate_adaptive_cognition/current_precursor"},
    "immune_function": {"value": "a ledgered incident record type for detection, containment and recovery",
                        "source": HERE + "prerequisite"},
}

FALSIFIERS = {
    "agent_organizations": [{"value": "If the swarm does not outperform the simpler form under the same constraints, "
                                      "retain the simpler form.", "source": DIRECTIVE + "#39-organizational-morphogenesis"}],
    "persistent_organs": [nfe("robust_unscripted_organ_formation"),
                          {"value": "a formed capability is used once and never again, or bypasses founder attach",
                           "source": ADVANTAGE}],
    "human_work_fabric": [nfe("large_scale_human_machine_coordination")],
    "business_operation": [{"value": ["Revenue generated through deception is failure.",
                                      "Engagement that destroys trust is failure."],
                            "source": DIRECTIVE + "#44-business-objective-function"}],
    "decision_relevant_knowledge": [{"value": "a founder decision made with a material fact GREG had authorized access "
                                              "to but did not surface", "source": ADVANTAGE}],
    "daleobanks_media_engine": [{"value": "Engagement that destroys trust is failure.",
                                 "source": DIRECTIVE + "#44-business-objective-function"}],
    "economic_compounding": [nfe("self_financed_research_infrastructure")],
    "multi_body": [nfe("reliable_multi_body_agency")],
    "continuity": [{"value": "a restore drill loses founder intent, ledger history or the ability to swap the model",
                    "source": ADVANTAGE}],
    "robotics": [nfe("advanced_robotic_embodiment")],
    "situational_awareness": [nfe("persistent_spatial_ecology"),
                              {"value": "a public, available warning relevant to the founder's consented location is "
                                        "not surfaced", "source": ADVANTAGE}],
    "developmental_research": [nfe("generalized_morphogenetic_repair"), nfe("cross_substrate_developmental_compilation"),
                               nfe("substrate_independent_developmental_intelligence"), p_node("P10")],
    "jarvis_integration": [nfe("jarvis_environmental_awareness")],
    "learned_cognitive_routing": [p_node("P4")],
    "cognitive_ecology": [nfe("automatic_invention_of_intelligence_families"), nfe("substrate_adaptive_cognition"),
                          nfe("open_ended_cognitive_organization_generation")] + [
                             p_node(p) for p in ("P6", "P8", "P9", "P10", "P11", "P12")],
    "immune_function": [{"value": "a replayed incident is missed, or legitimate novelty is quarantined",
                         "source": ADVANTAGE}],
}


def main() -> int:
    text = PATH.read_text()
    data = json.loads(text)
    assert json.dumps(data, indent=2) + "\n" == text, "greg/path.json is not in its canonical layout"
    distant = [h for h in data["horizons"] if h["feasibility"] != "CURRENTLY_BUILDABLE"]
    assert set(INTERFACES) | set(FALSIFIERS) <= {h["id"] for h in distant}
    for horizon in distant:
        assert not {"enabling_interfaces", "feasible_when", "falsified_by"} & set(horizon), horizon["id"]
        horizon["enabling_interfaces"] = INTERFACES.get(horizon["id"], {"unrecorded": NO_INTERFACE})
        horizon["feasible_when"] = {"recorded_as": "prerequisite"}
        found = FALSIFIERS.get(horizon["id"])
        horizon["falsified_by"] = (found[0] if len(found) == 1 else found) if found else {"unrecorded": NO_FALSIFIER}
    PATH.write_text(json.dumps(data, indent=2) + "\n")
    print(f"{len(distant)} horizons; interfaces recorded {len(INTERFACES)}, falsifiers recorded {len(FALSIFIERS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
