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


# -- gaps an independent audit found: each test below fails under a mutant the first gate did not catch --------
# (audit of 7245fa5d, 2026-11-11; the mutant ids N1..N14 are the auditor's and are kept in the gate's names)

def _demo(body, cid="demo.echo", klass="read_only"):
    """A registered, attached capability whose adapter reports what its context allows and counts its calls."""
    manifest = CapabilityManifest(capability_id=cid, version="1.0.0", provider="test", function=cid,
                                  description="reports what its context allows", route="api", consequence_class=klass,
                                  inputs={"x": "str"}, outputs={"allow": "list"}, target_prefix="artifact:",
                                  strengthens=("proof",), egress_allowlist=("a.example",))
    calls = []

    def adapter(params, ctx):
        calls.append(ctx.manifest)
        return {"allow": list(ctx.manifest.egress_allowlist)}
    body.registry.register(manifest, adapter, state="ATTACHED")
    return manifest, adapter, calls


def _demo_act(body, home, data, manifest, adapter, ctx_manifest, **extra):
    return _office_act(body, home, data, manifest=manifest, adapter=adapter, ctx_manifest=ctx_manifest,
                       params={"x": "y"}, **extra)


def _nothing_was_authorized(body) -> bool:
    return not _events(body, "greg.authority.grant_issued") and not body.ledger.by_type("grant_dispatch")


@pytest.mark.parametrize("wrapped", [False, True])
def test_a_detached_write_adapter_does_not_run_when_the_context_agrees_with_the_manifest(world, wrapped):
    """N3, N14: the adapter check alone must refuse, with or without a wrapper, and nothing is written."""
    body, key, body_id, home, data, _ = world
    body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "foundry.apply"}))
    query = body.registry.manifests["foundry.query"]
    cone = LightCone(capabilities=frozenset({"foundry.query"}), targets=("foundry:*",),
                     max_consequence_class="read_only", budget_usd=0.0, horizon=horizon())
    extra = {"around": lambda adapter: adapter} if wrapped else {}
    out = _office_act(body, home, data, manifest=query, adapter=body.registry.adapters["foundry.apply"],
                      ctx_manifest=query, params={"system": 36, "op": "put", "args": {"text": "x"}},
                      target="foundry:cas", cone=cone, **extra)
    assert out.status == "REFUSED" and out.receipt_hash is None
    assert not (workspace(home, "m:direct-office") / "foundry").exists()
    assert _nothing_was_authorized(body)


def test_an_edited_manifest_of_the_same_id_in_the_context_never_reaches_the_adapter(world):
    """N1: adapters read their egress allowlist, binaries and credentials from ctx.manifest."""
    body, _, _, home, data, _ = world
    manifest, adapter, calls = _demo(body)
    out = _demo_act(body, home, data, manifest, adapter, replace(manifest, egress_allowlist=("evil.example",)))
    assert out.status == "REFUSED" and calls == []
    assert "carries a manifest for demo.echo that is not the registered one" in out.reasons[0]


def test_a_context_with_no_manifest_is_refused_before_any_dispatch(world):
    """N2: otherwise the adapter crashes after the Gate's claim and the act is UNCERTAIN."""
    body, _, _, home, data, _ = world
    manifest, adapter, calls = _demo(body)
    out = _demo_act(body, home, data, manifest, adapter, None)
    assert out.status == "REFUSED" and calls == [] and _nothing_was_authorized(body)


def test_every_identity_refusal_is_recorded(world):
    """N5: a wrong manifest and a wrong context each leave their own record."""
    body, _, _, home, data, _ = world
    manifest, adapter, _ = _demo(body)
    edited = replace(manifest, description="edited")
    _demo_act(body, home, data, edited, adapter, edited)
    _demo_act(body, home, data, manifest, adapter, body.registry.manifests["fs.read"], attempt="q")
    assert len(_events(body, "greg.authority.refused_unattached")) == 2


def test_a_detached_capability_outside_the_cone_is_refused_not_offered_for_approval(world):
    """N6: the attach check comes before the cone. OUTSIDE_SCOPE becomes a founder ask in the mission engine, and
    the founder is never asked to approve running what he detached."""
    body, _, _, home, data, _ = world
    manifest, adapter, _ = _demo(body)
    body.registry.set_state("demo.echo", "DETACHED")
    cone = LightCone(capabilities=frozenset({"fs.read"}), targets=("artifact:reports",),
                     max_consequence_class="read_only", budget_usd=0.0, horizon=horizon())
    out = _demo_act(body, home, data, manifest, adapter, manifest, cone=cone)
    assert out.status == "REFUSED" and "DETACHED" in out.reasons[0]


def test_the_registered_adapter_runs_exactly_once_under_a_wrapper(world):
    """N7."""
    body, _, _, home, data, _ = world
    manifest, adapter, calls = _demo(body)
    out = _demo_act(body, home, data, manifest, adapter, manifest, around=lambda adapter: adapter)
    assert out.status == "DONE" and len(calls) == 1


def test_no_caller_code_runs_when_the_gate_refuses_after_the_grant(world):
    """N8: 'inside the dispatch' is later than 'after grant_issued'; the Gate can still refuse in between
    (identity, grant validity, budget reservation, commit-time revalidation). Here identity lapses."""
    body, _, _, home, data, _ = world
    manifest, adapter, calls = _demo(body)
    real, built = body.passports.verify, []
    body.passports.verify = lambda pid: (False, "lapsed") if _events(body, "greg.authority.grant_issued") \
        else real(pid)
    out = _demo_act(body, home, data, manifest, adapter, manifest,
                    around=lambda adapter: built.append(1) or adapter)
    assert out.status == "REFUSED" and built == [] and calls == []


def test_an_office_with_no_registry_refuses_a_write_class_capability_too(world):
    """N9: fail closed for every consequence class, not only reads."""
    body, _, _, home, data, _ = world
    manifest, adapter, calls = _demo(body, cid="demo.write", klass="internal_write")
    body.office.registry = None
    cone = LightCone(capabilities=frozenset({"demo.write"}), targets=("artifact:reports",),
                     max_consequence_class="internal_write", budget_usd=0.0, horizon=horizon())
    out = _demo_act(body, home, data, manifest, adapter, manifest, cone=cone)
    assert out.status == "REFUSED" and calls == []


def test_an_attached_state_without_a_registered_manifest_is_refused(world):
    """N10."""
    body, _, _, home, data, _ = world
    manifest, adapter, calls = _demo(body)
    del body.registry.manifests["demo.echo"]
    out = _demo_act(body, home, data, manifest, adapter, manifest)
    assert out.status == "REFUSED" and calls == []


# -- a missing adapter or context is refused, not dispatched ---------------------------------------------------

@pytest.mark.parametrize("wrapped", [False, True])
def test_an_act_with_no_adapter_is_refused_before_any_grant(world, wrapped):
    """Before: a None adapter skipped the identity check, got a grant and a dispatch claim, and ended UNCERTAIN (a
    founder reconciliation for an act that could never run); with a wrapper, the wrapper's own function ran and
    was receipted DONE in the capability's name."""
    body, _, _, home, data, _ = world
    manifest, _, calls = _demo(body)
    ran = []
    extra = {"around": lambda adapter: (lambda params, ctx: ran.append(1) or {"allow": []})} if wrapped else {}
    out = _demo_act(body, home, data, manifest, None, manifest, **extra)
    assert out.status == "REFUSED" and ran == [] and calls == [] and _nothing_was_authorized(body)
    assert _events(body, "greg.authority.refused_unattached")


def test_an_act_with_no_context_is_refused_before_any_grant(world):
    body, _, _, home, data, _ = world
    manifest, adapter, calls = _demo(body)
    cone = LightCone(capabilities=frozenset({"demo.echo"}), targets=("artifact:reports",),
                     max_consequence_class="read_only", budget_usd=0.0, horizon=horizon())
    out = body.office.act(mission_id="m:direct-office", cone=cone, command_digest="sha256:" + "0" * 64,
                          manifest=manifest, adapter=adapter, ctx=None, params={"x": "y"}, target="artifact:reports",
                          cost_usd=0.0, expected_outcome="observation captured", evidence_refs=[], attempt="n",
                          spent_usd=0.0, approved_scopes=set())
    assert out.status == "REFUSED" and calls == [] and _nothing_was_authorized(body)


def test_a_manifest_subclass_that_vouches_for_itself_is_refused(world):
    """The check used the presented object's own digest(). A subclass can answer with the registered digest while
    declaring a wider allowlist; only the registered object or an equal copy of exactly its type passes."""
    body, _, _, home, data, _ = world
    manifest, adapter, calls = _demo(body)

    class Lying(CapabilityManifest):
        def digest(self):
            return manifest.digest()
    forged = Lying(**{**{f: getattr(manifest, f) for f in manifest.__dataclass_fields__},
                      "egress_allowlist": ("evil.example",)})
    for attempt, (m, c) in enumerate(((forged, forged), (manifest, forged))):
        out = _demo_act(body, home, data, m, adapter, c, attempt=str(attempt))
        assert out.status == "REFUSED", (attempt, out.reasons)
    assert calls == []


def test_the_adapter_is_handed_the_registered_manifest_itself(world):
    """An equal copy in the context is accepted, and the adapter still receives the registered object: what the
    caller does to its own context after the check cannot reach the adapter."""
    body, _, _, home, data, _ = world
    manifest, adapter, calls = _demo(body)
    copy = replace(manifest)
    out = _demo_act(body, home, data, copy, adapter, copy)
    assert out.status == "DONE" and len(calls) == 1 and calls[0] is manifest


# -- ratchets: who may shape a dispatch, and who may build an office ------------------------------------------

AROUND_SITES = {"greg/missions.py": 1}       # the mission engine's one strategy dispatch (background workers)
OFFICE_BUILDERS = {"greg/body.py": 1}        # the body builds the one office, with its own registry


def _production_sources(root: Path):
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("tests/", ".")) or "/node_modules/" in rel or "/site-packages/" in rel:
            continue
        try:
            yield rel, ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue


def around_sites(root: Path) -> dict:
    """Every call, anywhere outside tests, that could hand an office a dispatch wrapper: a call named ``act``
    (as an attribute or a bound name) that passes ``around=`` or a ``**`` splat. Counted per file."""
    sites = {}
    for rel, tree in _production_sources(root):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", None)) == "act" \
                    and any(k.arg in ("around", None) for k in node.keywords):
                sites[rel] = sites.get(rel, 0) + 1
    return sites


def office_builds(root: Path) -> dict:
    """Every construction of an AuthorityOffice outside tests, by its own name, an import alias or a simple
    rebinding of either: {file: [(line, registry_named)]}. A dynamic lookup (getattr, importlib) is not seen."""
    found = {}
    for rel, tree in _production_sources(root):
        names = {"AuthorityOffice"}
        for _ in range(2):                                   # aliases of aliases, one level
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    names |= {a.asname for a in node.names if a.name in names and a.asname}
                elif isinstance(node, ast.Assign) and (
                        isinstance(node.value, ast.Name) and node.value.id in names
                        or isinstance(node.value, ast.Attribute) and node.value.attr in names):
                    names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", None)) in names:
                named = [k for k in node.keywords if k.arg == "registry"]
                ok = bool(named) and not (isinstance(named[0].value, ast.Constant) and named[0].value.value is None) \
                    and not any(k.arg is None for k in node.keywords)
                found.setdefault(rel, []).append((node.lineno, ok))
    return found


REPO = Path(__file__).resolve().parents[2]


def test_only_the_listed_sites_may_shape_a_dispatch():
    """``around`` is the one place a caller's code runs inside the office's dispatch. A new site, in any package,
    is a review decision: add it here with its reason."""
    extra = {rel: n for rel, n in around_sites(REPO).items() if n > AROUND_SITES.get(rel, 0)}
    assert not extra, f"unlisted code can hand the office a dispatch wrapper: {extra}"


def test_only_the_body_builds_an_authority_office_and_it_names_its_registry():
    """A second construction site is a second place the registry could be left out or replaced."""
    builds = office_builds(REPO)
    assert builds, "the scan found no construction site at all; it is reading the wrong tree"
    extra = {rel: len(calls) for rel, calls in builds.items() if len(calls) > OFFICE_BUILDERS.get(rel, 0)}
    assert not extra, f"unlisted code builds an AuthorityOffice: {extra}"
    bad = [(rel, line) for rel, calls in builds.items() for line, ok in calls if not ok]
    assert not bad, f"an AuthorityOffice is built without naming a registry: {bad}"


@pytest.mark.parametrize("relpath,source", [
    ("egregore/zz_a.py", "def f(office, wrap, **kw):\n    return office.act(around=wrap, **kw)\n"),
    ("greg/zz_b.py", "def f(office, wrap, **kw):\n    return office.act(**{'around': wrap, **kw})\n"),
    ("greg/zz_c.py", "def f(office, wrap, **kw):\n    act = office.act\n    return act(around=wrap, **kw)\n"),
])
def test_the_wrapper_scan_sees_other_packages_splats_and_bound_names(tmp_path, relpath, source):
    target = tmp_path / relpath
    target.parent.mkdir(parents=True)
    target.write_text(source)
    assert around_sites(tmp_path) == {relpath: 1}


def test_the_wrapper_scan_counts_sites_per_file(tmp_path):
    (tmp_path / "greg").mkdir()
    (tmp_path / "greg/missions.py").write_text(
        "def a(o, w):\n    return o.act(around=w)\n\ndef b(o, w):\n    return o.act(around=w)\n")
    assert around_sites(tmp_path) == {"greg/missions.py": 2}       # one more than AROUND_SITES allows


@pytest.mark.parametrize("source,ok", [
    ("from greg.authority import AuthorityOffice as Office\n\ndef f(b):\n    return Office(compiled=1, registry=b.r)\n", True),
    ("import greg.authority as A\n\ndef f(b):\n    return A.AuthorityOffice(compiled=1, registry=None)\n", False),
    ("from greg.authority import AuthorityOffice\nMake = AuthorityOffice\n\ndef f(b, kw):\n    return Make(**kw)\n", False),
])
def test_the_builder_scan_sees_aliases_rebindings_and_missing_registries(tmp_path, source, ok):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/second.py").write_text(source)
    [(line, named)] = office_builds(tmp_path)["pkg/second.py"]
    assert named is ok
