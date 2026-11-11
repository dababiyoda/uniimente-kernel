"""The authority office runs a capability's own registered adapter, or nothing.

Attach state is keyed by capability id (tests/unit/test_greg_authority_attach_state.py). The id alone does not
settle what runs: ``AuthorityOffice.act`` executes the adapter its caller hands it. Before this, a founder-DETACHED
``artifact.store`` (internal_write) ran through the office when its adapter was presented under the ATTACHED
``artifact.inspect`` manifest (read_only): DONE, an artifact retained, and a grant and receipt in the name of the
read-only capability. These tests drive the office directly on a real body, as that file does.
"""
from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from greg.artifacts import ArtifactStore
from greg.authority import AuthorityOffice
from greg.body import Body
from greg.capabilities import CapabilityError, CapabilityManifest, InvocationContext
from greg.lightcone import LightCone
from tests.greg_fixtures import horizon, make_body, signed, workspace

RAW = b"bytes a detached capability must not retain\n"
ADDRESS = "sha256:36e23d6cf2b7eafa664d41ee529106249e119fe6ac20f7d700adbbe1c4080b53"


def _office_act(body: Body, home: Path, data: Path, *, manifest, adapter, ctx_manifest, params, attempt="direct",
                **extra):
    cone = extra.pop("cone", None) or LightCone(
        capabilities=frozenset({manifest.capability_id}), targets=("artifact:reports",),
        max_consequence_class="read_only", budget_usd=0.0, horizon=horizon())
    target = extra.pop("target", "artifact:reports")
    ctx = InvocationContext(workspace=workspace(home, "m:direct-office"), read_roots=(data,), secrets=body.secrets,
                            manifest=ctx_manifest, journal=body.journal, artifact_root=body.layout.artifacts)
    return body.office.act(mission_id="m:direct-office", cone=cone, command_digest="sha256:" + "0" * 64,
                           manifest=manifest, adapter=adapter, ctx=ctx, params=params, target=target,
                           cost_usd=0.0, expected_outcome="observation captured", evidence_refs=[],
                           attempt=attempt, spent_usd=0.0, approved_scopes=set(), **extra)


def _events(body, kind):
    return [r.payload for r in body.ledger.by_type("event") if r.payload.get("type") == kind]


def _retained(body) -> bool:
    try:
        ArtifactStore(body.layout.artifacts).read(ADDRESS)
    except CapabilityError:
        return False
    return True


@pytest.fixture
def world(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    source = data / "report.bin"
    source.write_bytes(RAW)
    with Body(home) as body:
        body.boot()
        yield body, key, body_id, home, data, source


def test_a_detached_adapter_does_not_run_under_an_attached_manifest(world):
    """The reproduced defect: the write capability the founder detached, presented as the read-only one."""
    body, key, body_id, home, data, source = world
    body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "artifact.store"}))
    inspect = body.registry.manifests["artifact.inspect"]
    grants_before = len(_events(body, "greg.authority.grant_issued"))
    out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.store"],
                      ctx_manifest=body.registry.manifests["artifact.store"],
                      params={"namespace": "reports", "path": str(source)})
    assert out.status == "REFUSED" and "adapter presented for artifact.inspect" in out.reasons[0]
    assert out.receipt_hash is None and not _retained(body)                       # no effect
    assert len(_events(body, "greg.authority.grant_issued")) == grants_before      # no passport, grant or dispatch
    [event] = _events(body, "greg.authority.refused_unattached")
    assert event["capability"] == "artifact.inspect" and event["proposal_id"] == out.proposal_id


def test_an_attached_adapter_does_not_run_under_another_attached_manifest(world):
    """Both attached: the receipt would still name a capability that did not run, at a class it does not have."""
    body, _, _, home, data, source = world
    out = _office_act(body, home, data, manifest=body.registry.manifests["artifact.inspect"],
                      adapter=body.registry.adapters["artifact.store"],
                      ctx_manifest=body.registry.manifests["artifact.store"],
                      params={"namespace": "reports", "path": str(source)})
    assert out.status == "REFUSED" and not _retained(body)


def test_the_context_cannot_name_a_different_capability(world):
    """An adapter learns which capability it runs as from ``ctx.manifest``; the caller does not choose that."""
    body, _, _, home, data, _ = world
    inspect = body.registry.manifests["artifact.inspect"]
    out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=body.registry.manifests["artifact.store"],
                      params={"namespace": "reports", "address": ADDRESS})
    assert out.status == "REFUSED" and "invocation context names artifact.store" in out.reasons[0]


def test_a_manifest_that_differs_from_the_registered_one_is_refused(world):
    """Same id, different declared facts: not the capability this body registered and the founder attached."""
    body, _, _, home, data, _ = world
    registered = body.registry.manifests["artifact.inspect"]
    forged = replace(registered, description=registered.description + " (edited)")
    out = _office_act(body, home, data, manifest=forged, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=forged, params={"namespace": "reports", "address": ADDRESS})
    assert out.status == "REFUSED" and "not the one registered" in out.reasons[0]


def test_the_registered_capability_still_runs(world):
    body, _, _, home, data, _ = world
    inspect = body.registry.manifests["artifact.inspect"]
    out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=inspect, params={"namespace": "reports", "address": ADDRESS})
    assert out.status == "DONE" and out.receipt_hash
    assert not _events(body, "greg.authority.refused_unattached")


def test_an_equal_copy_of_the_registered_manifest_still_runs(world):
    """Identity is by content: a manifest rebuilt from its record (as a restart rebuilds them) is the same one."""
    body, _, _, home, data, _ = world
    inspect = body.registry.manifests["artifact.inspect"]
    copy = replace(inspect)
    assert copy is not inspect
    out = _office_act(body, home, data, manifest=copy, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=copy, params={"namespace": "reports", "address": ADDRESS})
    assert out.status == "DONE"


def test_a_detach_survives_a_restart_at_the_office(tmp_path):
    """Founder detaches -> the body stops -> a new process boots: the office still refuses, and says so again."""
    home, key, body_id, data = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "artifact.inspect"}))
    with Body(home) as body:
        body.boot()
        assert body.registry.state["artifact.inspect"] == "DETACHED"
        inspect = body.registry.manifests["artifact.inspect"]
        out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                          ctx_manifest=inspect, params={"namespace": "reports", "address": ADDRESS})
        assert out.status == "REFUSED" and "DETACHED" in out.reasons[0]
        assert _events(body, "greg.authority.refused_unattached")
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "artifact.inspect"}))
        again = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                            ctx_manifest=inspect, params={"namespace": "reports", "address": ADDRESS}, attempt="b")
        assert again.status == "DONE"


def test_around_shapes_the_dispatch_of_the_registered_adapter(world):
    """A caller that runs a long worker off the body's turn wraps the dispatch; the office hands its wrapper the
    registered adapter, so the wrapper decides how it is called and never which adapter is."""
    body, _, _, home, data, _ = world
    inspect, registered = body.registry.manifests["artifact.inspect"], body.registry.adapters["artifact.inspect"]
    seen = []

    def around(adapter):
        def shaped(params, ctx):
            seen.append(adapter)
            return adapter(params, ctx)
        return shaped

    out = _office_act(body, home, data, manifest=inspect, adapter=registered, ctx_manifest=inspect,
                      params={"namespace": "reports", "address": ADDRESS}, around=around)
    assert out.status == "DONE" and seen == [registered]


def test_around_is_never_applied_to_a_refused_act(world):
    body, key, body_id, home, data, _ = world
    body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "artifact.inspect"}))
    inspect = body.registry.manifests["artifact.inspect"]
    called = []
    out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=inspect, params={"namespace": "reports", "address": ADDRESS},
                      around=lambda adapter: called.append(adapter) or adapter)
    assert out.status == "REFUSED" and not called


AROUND_CALLERS = {"greg/missions.py"}       # the mission engine's one strategy dispatch (background workers)


def test_only_the_listed_callers_may_shape_a_dispatch():
    """``around`` is the one place a caller's code runs inside the office's dispatch. A new caller is a review
    decision: add it here with its reason."""
    root = Path(__file__).resolve().parents[2]
    users = set()
    for path in sorted((root / "greg").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "act"
                    and any(k.arg == "around" for k in node.keywords)):
                users.add(path.relative_to(root).as_posix())
    assert users <= AROUND_CALLERS, f"unlisted callers pass around= to the office: {sorted(users - AROUND_CALLERS)}"


# -- a dispatch wrapper is caller code: it must not run before the act is authorized -------------------------

class _Wrapper:
    """A dispatch wrapper that records every moment caller code runs and what the ledger held then."""

    def __init__(self, body):
        self.body, self.built, self.called = body, [], []

    def __call__(self, adapter):
        self.built.append(len(_events(self.body, "greg.authority.grant_issued")))

        def shaped(params, ctx):
            self.called.append(len(_events(self.body, "greg.authority.grant_issued")))
            return adapter(params, ctx)
        return shaped


def _inspect_act(body, home, data, wrapper, **extra):
    inspect = body.registry.manifests["artifact.inspect"]
    return _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                       ctx_manifest=inspect, params={"namespace": "reports", "address": ADDRESS}, around=wrapper,
                       **extra)


def test_caller_code_first_runs_after_the_grant_for_this_act_is_issued(world):
    body, _, _, home, data, _ = world
    wrapper, before = _Wrapper(body), len(_events(body, "greg.authority.grant_issued"))
    out = _inspect_act(body, home, data, wrapper)
    assert out.status == "DONE"
    assert wrapper.built == [before + 1] and wrapper.called == [before + 1]     # once, and only after the grant


def test_a_wrapper_never_runs_for_a_target_the_capability_does_not_admit(world):
    body, _, _, home, data, _ = world
    wrapper = _Wrapper(body)
    out = _inspect_act(body, home, data, wrapper, target="fs:/etc/passwd")
    assert out.status == "REFUSED" and "outside capability prefix" in out.reasons[0]
    assert wrapper.built == [] and wrapper.called == []


def test_a_wrapper_never_runs_for_an_act_outside_the_light_cone(world):
    body, _, _, home, data, _ = world
    wrapper = _Wrapper(body)
    cone = LightCone(capabilities=frozenset({"fs.read"}), targets=("artifact:reports",),
                     max_consequence_class="read_only", budget_usd=0.0, horizon=horizon())
    out = _inspect_act(body, home, data, wrapper, cone=cone)
    assert out.status == "OUTSIDE_SCOPE"
    assert wrapper.built == [] and wrapper.called == []


def test_a_wrapper_never_runs_while_the_act_waits_for_a_human_decision(world):
    """Policy always asks for a human on an irreversible act (policy/engine.py ALWAYS_HUMAN_CLASSES). Nothing of
    the caller's runs until the founder answers."""
    body, _, _, home, data, _ = world
    manifest = CapabilityManifest(capability_id="demo.contact", version="1.0.0", provider="test",
                                  function="demo.contact", description="cannot be undone", route="api",
                                  consequence_class="irreversible", inputs={"x": "str"}, outputs={"ok": "bool"},
                                  target_prefix="artifact:", strengthens=("proof",))
    ran = []

    def contact(params, ctx):
        ran.append(params)
        return {"ok": True}
    body.registry.register(manifest, contact, state="ATTACHED")
    wrapper = _Wrapper(body)
    cone = LightCone(capabilities=frozenset({"demo.contact"}), targets=("artifact:reports",),
                     max_consequence_class="read_only", budget_usd=0.0, horizon=horizon())
    # no cone holds an irreversible act; the signed mission's own pre-approved step admits it past the cone, and
    # policy then still requires the founder's exact-scope decision
    scope = AuthorityOffice.scope_digest(mission_id="m:direct-office", capability_id="demo.contact",
                                         params={"x": "y"}, target="artifact:reports",
                                         consequence_class="irreversible", cost_usd=0.0, spent_usd=0.0,
                                         budget_usd=0.0)
    out = _office_act(body, home, data, manifest=manifest, adapter=contact, ctx_manifest=manifest,
                      params={"x": "y"}, around=wrapper, cone=cone, signed_scopes=frozenset({scope}))
    assert out.status == "NEEDS_DECISION", (out.status, out.reasons)
    assert wrapper.built == [] and wrapper.called == [] and ran == []


def test_a_wrapper_does_not_run_again_when_a_retained_receipt_is_reused(world):
    body, _, _, home, data, _ = world
    wrapper = _Wrapper(body)
    assert _inspect_act(body, home, data, wrapper, attempt="kept").status == "DONE"
    again = _inspect_act(body, home, data, wrapper, attempt="kept")
    assert again.status == "DONE" and "retained receipt" in again.reasons[0]
    assert len(wrapper.built) == 1 and len(wrapper.called) == 1


def test_a_wrapper_does_not_run_again_for_a_dispatch_whose_outcome_is_unknown(world):
    """A dispatch that died mid-effect is UNCERTAIN; the same attempt is never dispatched blind a second time."""
    body, _, _, home, data, _ = world
    inspect, real = body.registry.manifests["artifact.inspect"], body.registry.adapters["artifact.inspect"]

    def exploding(params, ctx):
        raise RuntimeError("power lost mid-effect")
    body.registry.adapters["artifact.inspect"] = exploding
    wrapper = _Wrapper(body)
    try:
        first = _office_act(body, home, data, manifest=inspect, adapter=exploding, ctx_manifest=inspect,
                            params={"namespace": "reports", "address": ADDRESS}, around=wrapper, attempt="u")
        again = _office_act(body, home, data, manifest=inspect, adapter=exploding, ctx_manifest=inspect,
                            params={"namespace": "reports", "address": ADDRESS}, around=wrapper, attempt="u")
    finally:
        body.registry.adapters["artifact.inspect"] = real
    assert first.status == "UNCERTAIN" and again.status == "UNCERTAIN"
    assert len(wrapper.built) == 1 and len(wrapper.called) == 1


# -- an office that cannot check a registry runs nothing ----------------------------------------------------

def test_an_office_cannot_be_built_without_naming_a_registry(world):
    body = world[0]
    with pytest.raises(TypeError):
        AuthorityOffice(compiled=body.compiled, passports=body.passports, signer=body.office.signer,
                        ledger=body.ledger)


def test_an_office_built_with_no_registry_refuses_every_act(world):
    """Fail closed: without a registry the office cannot tell what is attached, so it runs nothing."""
    body, _, _, home, data, _ = world
    office = AuthorityOffice(compiled=body.compiled, passports=body.passports, signer=body.office.signer,
                             ledger=body.ledger, registry=None)
    body.office = office
    inspect = body.registry.manifests["artifact.inspect"]
    grants_before = len(_events(body, "greg.authority.grant_issued"))
    out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=inspect, params={"namespace": "reports", "address": ADDRESS})
    assert out.status == "REFUSED" and "without a capability registry" in out.reasons[0]
    assert len(_events(body, "greg.authority.grant_issued")) == grants_before
    assert _events(body, "greg.authority.refused_unattached")


def test_a_running_office_whose_registry_is_removed_refuses_every_act(world):
    body, _, _, home, data, _ = world
    body.office.registry = None
    inspect = body.registry.manifests["artifact.inspect"]
    out = _office_act(body, home, data, manifest=inspect, adapter=body.registry.adapters["artifact.inspect"],
                      ctx_manifest=inspect, params={"namespace": "reports", "address": ADDRESS})
    assert out.status == "REFUSED"


OFFICE_BUILDERS = {"greg/body.py"}          # the body builds the one office, with its own registry


def test_only_the_body_builds_an_authority_office_and_it_names_its_registry():
    """A second construction site is a second place the registry could be left out. Adding one is a review
    decision: list it here with its reason."""
    root = Path(__file__).resolve().parents[2]
    sites = {}
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("tests/", ".")) or "/node_modules/" in rel or "/site-packages/" in rel:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) \
                    == "AuthorityOffice":
                sites.setdefault(rel, []).append(node)
    assert set(sites) <= OFFICE_BUILDERS, f"unlisted code builds an AuthorityOffice: {sorted(set(sites) - OFFICE_BUILDERS)}"
    assert sites, "the scan found no construction site at all; it is reading the wrong tree"
    for rel, calls in sites.items():
        for call in calls:
            named = [k for k in call.keywords if k.arg == "registry"]
            assert named and not (isinstance(named[0].value, ast.Constant) and named[0].value.value is None), \
                f"{rel}:{call.lineno} builds an AuthorityOffice without a registry"
