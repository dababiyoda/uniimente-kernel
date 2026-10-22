"""A package GREG acquires must be legally qualified, not only technically (directive 2026-10-22, 5.3 and 6).

Before ``greg/licensing.py`` the Mechanism Card carried the license string and nothing read it again, so a
founder-signed read-only ``auto_attach`` attached an installed package whatever it declared: undeclared,
non-commercial, source-available or network-copyleft. Now the card carries an assessment parsed by
``packaging.licenses``, and only a cleared license may attach without the founder's own command.
"""
from __future__ import annotations

from email.message import Message

import pytest

from greg import licensing

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg import genesis as genesis_mod  # noqa: E402
from greg import mechanisms  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.templates import network_in_words  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402

ROUTE = "Warehouse to Hub: 4 miles. Hub to Store: 3. Warehouse to Store: 9. Shortest route from Warehouse to Store."


class FakeDist:
    """Installed-distribution metadata only, as importlib.metadata exposes it."""

    def __init__(self, name, expression=None, classifiers=(), text=None):
        self.metadata = Message()
        self.metadata["Name"] = name
        if expression:
            self.metadata["License-Expression"] = expression
        for c in classifiers:
            self.metadata["Classifier"] = c
        if text:
            self.metadata["License"] = text


class Relicensed:
    """A real installed distribution whose declared license is replaced: same files, same digest."""

    def __init__(self, dist, expression):
        self._dist = dist
        self.metadata = Message()
        for key, value in dist.metadata.items():
            if key not in ("License-Expression", "License", "Classifier"):
                self.metadata[key] = value
        self.metadata["License-Expression"] = expression

    def __getattr__(self, name):
        return getattr(self._dist, name)


@pytest.mark.parametrize("dist, verdict, cls", [
    (FakeDist("a", "MIT"), "CLEARED", licensing.PERMISSIVE),
    (FakeDist("b", "mit or apache-2.0"), "CLEARED", licensing.PERMISSIVE),
    (FakeDist("c", "MPL-2.0"), "CLEARED_WITH_OBLIGATIONS", licensing.WEAK_COPYLEFT),
    (FakeDist("d", "GPL-3.0-or-later"), "CLEARED_WITH_OBLIGATIONS", licensing.STRONG_COPYLEFT),
    (FakeDist("e", "GPL-2.0-only WITH Classpath-exception-2.0"), "CLEARED_WITH_OBLIGATIONS", licensing.WEAK_COPYLEFT),
    (FakeDist("f", "AGPL-3.0-only"), "FOUNDER_REVIEW", licensing.NETWORK_COPYLEFT),
    (FakeDist("g", "BUSL-1.1"), "FOUNDER_REVIEW", licensing.NOT_OPEN),
    (FakeDist("h", "LicenseRef-Acme-Internal"), "FOUNDER_REVIEW", licensing.UNKNOWN),
    (FakeDist("i", "MIT AND SSPL-1.0"), "FOUNDER_REVIEW", licensing.NOT_OPEN),       # AND: every term applies
    (FakeDist("j", "MIT OR SSPL-1.0"), "CLEARED", licensing.PERMISSIVE),             # OR: GREG may choose MIT
    (FakeDist("k", "(MIT OR AGPL-3.0-only) AND BUSL-1.1"), "FOUNDER_REVIEW", licensing.NOT_OPEN),
    (FakeDist("l", "not an expression ((("), "FOUNDER_REVIEW", licensing.UNKNOWN),
    (FakeDist("m"), "FOUNDER_REVIEW", licensing.UNKNOWN),                             # undeclared
    (FakeDist("n", classifiers=["License :: OSI Approved :: BSD License"]), "CLEARED", licensing.PERMISSIVE),
    (FakeDist("o", classifiers=["License :: OSI Approved :: MIT License",
                                "License :: Other/Proprietary License"]), "FOUNDER_REVIEW", licensing.NOT_OPEN),
    (FakeDist("p", classifiers=["License :: OSI Approved"]), "FOUNDER_REVIEW", licensing.UNKNOWN),
    (FakeDist("q", text="3-Clause BSD License"), "CLEARED", licensing.PERMISSIVE),
    (FakeDist("r", text="Copyright (c) 2026 Acme. All rights reserved."), "FOUNDER_REVIEW", licensing.UNKNOWN),
    (FakeDist("s", text="Apache-2.0"), "CLEARED", licensing.PERMISSIVE),             # SPDX in a legacy field
])
def test_a_declared_license_is_parsed_classified_and_fails_closed(dist, verdict, cls):
    assessment = licensing.assess(dist)
    assert (assessment["verdict"], assessment["class"]) == (verdict, cls)
    assert assessment["auto_attach"] is (verdict != "FOUNDER_REVIEW")
    assert "not a legal review" in assessment["limits"] and assessment["parser"].startswith("packaging.licenses")


def test_a_dependency_that_runs_in_the_same_interpreter_is_assessed_with_the_package():
    assessment = licensing.assess(FakeDist("engine", "MIT"), [FakeDist("helper", "Elastic-2.0")])
    assert assessment["verdict"] == "FOUNDER_REVIEW" and "helper: Elastic-2.0" in assessment["reason"]


def test_the_engines_genesis_already_uses_are_cleared_from_their_own_metadata():
    for function, distribution in (("graph.shortest_path", "networkx"), ("graph.max_flow", "scipy"),
                                   ("lp.optimize", "ortools")):
        candidate = next(c for c in genesis_mod.CATALOG[function]["candidates"] if c.distribution == distribution)
        dist = mechanisms.installed(distribution)
        if dist is None:
            continue
        card = mechanisms.card(candidate, function, dist)
        assessment = card["license_assessment"]
        assert assessment["auto_attach"] is True, assessment
        # common-mode dependencies (numpy, protobuf) are part of the assessment
        assert [p["distribution"].lower() for p in assessment["parts"][1:]] == \
            [d.lower() for d in candidate.common_mode if mechanisms.installed(d)]


def _run_route(tmp_path, monkeypatch, expression):
    real = mechanisms.installed
    if expression:
        monkeypatch.setattr(mechanisms, "installed",
                            lambda name: Relicensed(real(name), expression) if name == "networkx" else real(name))
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=ROUTE, auto_attach=True)))
    clock = Clock()
    body = Body(home, clock=clock)
    body.__enter__()
    body.boot()
    states = []
    for _ in range(3):
        states.append(body.tick()["missions"][0]["state"])
        clock.advance(31)
    return body, key, body_id, clock, states


def test_a_cleared_package_still_attaches_under_the_signed_read_only_scope(tmp_path, monkeypatch):
    body, *_, states = _run_route(tmp_path, monkeypatch, None)
    try:
        assert "ACHIEVED" in states
        [attached] = [e.payload for e in body.journal.replay("capability.state") if e.payload["state"] == "ATTACHED"]
        assert attached["by"] == genesis_mod.AUTO_ATTACH
    finally:
        body.__exit__(None, None, None)


@pytest.mark.parametrize("expression", ["BUSL-1.1", "AGPL-3.0-only", "LicenseRef-Proprietary"])
def test_a_package_whose_license_is_not_cleared_waits_for_the_founder_and_says_why(tmp_path, monkeypatch, expression):
    body, key, body_id, clock, states = _run_route(tmp_path, monkeypatch, expression)
    try:
        assert "ACHIEVED" not in states
        assert not [e for e in body.journal.replay("capability.state") if e.payload["state"] == "ATTACHED"]
        whys = [e.payload["why"] for e in body.journal.replay("deficit.awaiting_attach")
                if e.payload["capability_id"] == "acquired.graph.shortest_path.networkx"]
        assert whys and whys[0].startswith("its license needs your decision") and expression in whys[0]
        # technically qualified and registered: the founder still decides, and can attach it
        verified = next(e.payload for e in body.journal.replay("genesis.verified")
                        if e.payload["capability_id"] == "acquired.graph.shortest_path.networkx")
        assert verified["passed"] and verified["mechanism"]["license_assessment"]["verdict"] == "FOUNDER_REVIEW"
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH",
                          {"capability_id": "acquired.graph.shortest_path.networkx"}))
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
    finally:
        body.__exit__(None, None, None)


def test_ablation_without_the_license_gate_the_non_commercial_package_attaches_itself(tmp_path, monkeypatch):
    monkeypatch.setattr(genesis_mod.licensing, "auto_attach_allowed", lambda provenance: (True, ""))
    body, *_, states = _run_route(tmp_path, monkeypatch, "BUSL-1.1")
    try:
        assert "ACHIEVED" in states                         # the failure the gate exists to prevent
        assert [e for e in body.journal.replay("capability.state") if e.payload["state"] == "ATTACHED"]
    finally:
        body.__exit__(None, None, None)


def test_a_card_without_an_assessment_is_never_cleared():
    assert licensing.auto_attach_allowed({}) == (False, "no license assessment on its Mechanism Card")


def test_without_the_spdx_parser_every_license_fails_closed(monkeypatch):
    monkeypatch.setattr(licensing, "canonicalize_license_expression", None)
    assessment = licensing.assess(FakeDist("a", "MIT"))
    assert assessment["verdict"] == "FOUNDER_REVIEW" and "unavailable" in assessment["reason"]


# -- independent review of 73b19fe: each case below passed (wrongly) before its fix -------------------------

@pytest.mark.parametrize("dist, cls", [
    (FakeDist("rider", text="MIT\nsome other\nCommons Clause restriction"), licensing.NOT_OPEN),   # review 3
    (FakeDist("multi", text="MIT\nsee COPYING for the rest"), licensing.UNKNOWN),                 # review 3
    (FakeDist("t1", classifiers=["License :: OSI Approved :: BSD License"],
              text="Proprietary, non-commercial only"), licensing.NOT_OPEN),                      # review 4
    (FakeDist("t2", classifiers=["License :: OSI Approved :: MIT License"], text="SSPL-1.0"), licensing.NOT_OPEN),
    (FakeDist("t3", "MIT", text="AGPL-3.0-only"), licensing.NETWORK_COPYLEFT),
    (FakeDist("osl", "OSL-3.0"), licensing.NETWORK_COPYLEFT),                                      # review 5
    (FakeDist("eupl", "EUPL-1.2"), licensing.NETWORK_COPYLEFT),
    (FakeDist("full", classifiers=["License :: OSI Approved :: BSD License"],
              text="Copyright (c) 2001 X.\nAll rights reserved.\nRedistribution ... permitted"), licensing.PERMISSIVE),
])
def test_the_license_field_is_read_beside_every_other_declaration(dist, cls):
    assert licensing.declared(dist)["class"] == cls


def test_a_card_recorded_before_assessments_is_reassessed_from_the_installed_package():      # review 2
    import importlib.metadata
    version = importlib.metadata.version("networkx")
    assert licensing.auto_attach_allowed({"distribution": "networkx", "version": version})[0] is True
    assert licensing.auto_attach_allowed({"distribution": "networkx", "version": "0.0.0"})[0] is False
    assert licensing.auto_attach_allowed({"distribution": "no-such-distribution-greg", "version": "1"})[0] is False


def test_an_engine_is_not_attached_as_a_dependency_when_its_license_is_not_cleared():          # review 1
    class Stub:
        _form_only = None

    class Cone:
        @staticmethod
        def _capability_inside(_):
            return True

    class Mission:
        spec = {"auto_attach": {"max_consequence_class": "read_only"}}
        cone = Cone()
        mission_id = "m"

    class Manifest:
        capability_id = "acquired.lp.optimize.acme"
        provider = "installed:python:acme==1.0"
        consequence_class = "read_only"
        provenance = {"license_assessment": licensing.assess(FakeDist("acme", "BUSL-1.1"))}

    assert genesis_mod.Genesis._attach_dependency(Stub(), Mission(), Manifest(), "composed.x", None) is False


def test_an_unrecognised_short_name_beside_a_classifier_is_informational_not_blocking():
    lgpl = FakeDist("lazr", classifiers=["License :: OSI Approved :: GNU Library or Lesser General Public License "
                                         "(LGPL)"], text="LGPL v3, see the README")
    assert licensing.declared(lgpl)["class"] == licensing.WEAK_COPYLEFT
    parent = FakeDist("oauth", classifiers=["License :: OSI Approved", "License :: OSI Approved :: BSD License"])
    assert licensing.declared(parent)["class"] == licensing.PERMISSIVE
