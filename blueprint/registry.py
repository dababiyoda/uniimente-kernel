"""The 55 bindings: what this institution can actually prove about itself.

Each entry binds one Foundry technology (`foundry/arsenal.py`) to the evidence
that exists in this repository today, the reality of what exists, the gaps that
stand between it and a hardened form, and which collaborator owns closing them.

Three disciplines govern every entry:

1. **Claimed is checked.** `claimed_rung` is refused if the evidence it requires
   does not resolve. The awarded rung is the one the evidence supports — never
   the one the entry asked for.
2. **Reality is separate.** A technology may be BUILT and still BLUEPRINT_ONLY
   elsewhere, or EXERCISED and only SIMULATED. Neither axis implies the other.
3. **Gaps are named, not implied.** "Partial" is not a gap. "The bridge mirrors
   share one HMAC secret, so a recognized identity is a claimed identity and not
   a cryptographically isolated one" is a gap.

Cross-repository evidence, previously the standing limitation of this registry:
evidence locators used to be kernel-repository-relative, so capabilities
implemented in the peer organs stood at BLUEPRINT from here regardless of what
existed there. `blueprint/peer_evidence.py` closes that mechanism — an
`IMPLEMENTATION_PATH` locator may now read `peer:<organ>/<path>` and resolves
against a commit-pinned attestation carrying content digests.

No binding in this table has been re-rated on the strength of it. Deciding that a
peer's file satisfies a kernel technology is a judgment about what the peer
implements, and making nineteen such judgments at once is how a ladder inflates.
The one correction the closed mechanism did produce is recorded in #32's gap: the
boundary was not what held it at BLUEPRINT.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from blueprint.evidence import (
    KERNEL_ROOT,
    EvidenceRef,
    Resolution,
    resolve_all,
    satisfied_kinds,
)
from blueprint.ladder import (
    EvidenceKind as K,
    LadderError,
    Reality,
    Rung,
    highest_supported_rung,
    missing_for,
    rung_index,
)
from foundry.arsenal import ARSENAL, technology

FBO = "docs/UNIIMENTE_FINAL_BUILD_ORDER.md"
ARCH = "docs/ARCHITECTURE.md"


class Owner(str, Enum):
    """Who owns closing this technology's named gaps."""

    CLAUDE = "CLAUDE"
    CHATGPT = "CHATGPT"
    FOUNDER = "FOUNDER"      # requires a constitutional or capital decision
    EXTERNAL = "EXTERNAL"    # requires a real customer, payment or platform


@dataclass(frozen=True)
class TechnologyBinding:
    """One technology's evidence.

    `claimed_rung` may be None. That is not an omission — it is the honest state
    of a technology for which not even a written specification exists, and the
    ladder's floor (BLUEPRINT) requires one. Claiming nothing is permitted;
    claiming more than the evidence supports is not.
    """

    technology_id: int
    claimed_rung: Rung | None
    reality: Reality
    evidence: tuple[EvidenceRef, ...]
    gaps: tuple[str, ...]
    owner: Owner

    @property
    def name(self) -> str:
        return technology(self.technology_id).name


# Shorthands so the table below reads as a table.
def _spec(loc: str) -> EvidenceRef:
    return EvidenceRef(K.SPEC_DOCUMENT, loc)


def _impl(loc: str) -> EvidenceRef:
    return EvidenceRef(K.IMPLEMENTATION_PATH, loc)


def _test(loc: str) -> EvidenceRef:
    return EvidenceRef(K.TEST_NODE, loc)


def _closure(loc: str) -> EvidenceRef:
    return EvidenceRef(K.CLOSURE_MODULE, loc)


def _contract(loc: str) -> EvidenceRef:
    return EvidenceRef(K.CONTRACT_SCHEMA, loc)


def _cap(loc: str) -> EvidenceRef:
    return EvidenceRef(K.MANIFEST_CAPABILITY, loc)


def _b(technology_id, claimed_rung, reality, evidence, gaps, owner) -> TechnologyBinding:
    return TechnologyBinding(
        technology_id=technology_id,
        claimed_rung=claimed_rung,
        reality=reality,
        evidence=tuple(evidence),
        gaps=tuple(gaps),
        owner=owner,
    )


_BINDINGS: tuple[TechnologyBinding, ...] = (
    # ---------------------------------------------------------------- 1-11
    _b(1, Rung.PROVEN, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.1 Compiler Architecture"),
        _impl("compiler/ucl_compiler.py"),
        _test("tests/unit/test_ucl_compiler.py::test_compilation_is_deterministic"),
        _closure("compiler"), _contract("decision"), _cap("kernel.ucl_compiler"),
    ], [
        "Compiles the Constitution only. Workflows, agent charters and business "
        "plans named in FBO §4.1 are not compiled by this compiler.",
    ], Owner.CLAUDE),

    _b(2, Rung.PROVEN, Reality.IMPLEMENTED, [
        _spec("docs/UCL.md"),
        _impl("compiler/ucl_parser.py"),
        _test("tests/unit/test_ucl_compiler.py::test_parser_handles_labels_nested_lists_and_comments"),
        _closure("compiler"), _contract("decision"), _cap("kernel.ucl_compiler"),
    ], [
        "UCL is the only restricted DSL. No workflow DSL and no experiment DSL exist.",
    ], Owner.CLAUDE),

    _b(3, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.5 Version-Control Architecture"),
        _impl("evolution/capsule.py"),
        _test("tests/unit/test_evolution.py::test_tree_preserves_rejected_branches_with_revival_evidence"),
        _closure("evolution"),
    ], [
        "Capsules preserve lineage for evolution cycles only. There is no typed "
        "versioned-artifact object covering the Constitution, policy, charters and "
        "genomes as FBO §4.5 requires.",
    ], Owner.CHATGPT),

    _b(4, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.6 Database Architecture"),
        _impl("provenance/ledger.py"),
        _test("tests/unit/test_provenance.py::test_persistence_roundtrip"),
        _closure("evidence_ledger"),
    ], [
        "The append-only ledger is the only durable institutional store. No "
        "Institutional State Fabric over a mature database, no materialized views, "
        "no reconciliation workers (FBO §4.6).",
    ], Owner.CHATGPT),

    _b(5, Rung.PROVEN, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.7 Event-Sourcing Architecture"),
        _impl("events/spine.py"),
        _test("tests/unit/test_events.py::test_emit_ledgers_and_dispatches"),
        _closure("events"), _contract("event"), _cap("kernel.event_spine"),
    ], [
        "In-process only. No organ emits into this spine across a repository boundary.",
    ], Owner.CLAUDE),

    _b(6, Rung.PROVEN, Reality.IMPLEMENTED, [
        _spec(f"{ARCH}#Integrity without a blockchain"),
        _impl("provenance/proof.py"),
        _test("tests/unit/test_proof.py::test_root_commits_to_all_leaves"),
        _closure("proof"), _contract("evidence"), _cap("kernel.evidence_ledger"),
    ], [
        "No external timestamping or independent notarization; the chain is "
        "self-anchored and trusts its own host.",
    ], Owner.FOUNDER),

    _b(7, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{ARCH}#Identity + Authority Fabric"),
        _impl("identity/machine_passport.py"),
        _impl("identity/pki/handshake.py"),
        _test("tests/unit/test_identity.py::test_identity_is_not_authority"),
        _test("tests/unit/test_pki_mutual_tls.py::"
              "test_a_foreign_ca_cannot_mint_a_kernel_identity"),
        _closure("identity"), _cap("kernel.machine_passports"),
    ], [
        # AMENDED 2026-08-22 under FOUNDER-RULING-2026-08-22, which ratified
        # asymmetric workload identity. The shared-key gap below is NOT closed:
        # `identity/pki/` exists and is adversarially tested, but no bridge has
        # migrated to it, so the live transport still authenticates exactly as
        # it did. Building a replacement is not adopting one, and recording it
        # as closed would be the kind of credit the founder ruled out for a
        # change that moves no integration boundary.
        "The live bridge transport is still HMAC over a shared secret. The "
        "DALEOBANKS, WealthMachine and kernel mirrors share one "
        "WEALTHMACHINE_SIGNING_KEY, so a recognized transport identity remains a "
        "CLAIMED identity: any holder of the shared secret can assert any known "
        "identity. `adapters/bridge_transport.py` now reports "
        "`identity_isolated: false` on every path so no reader can mistake a "
        "valid signature for isolation, and refuses to run unsigned unless a "
        "human sets UNIIMENTE_BRIDGE_DEV_UNSIGNED=1 — but the underlying "
        "symmetry is unchanged until the bridges move to `identity/pki/`.",
        "The asymmetric replacement has no transport. `mutual_tls` runs over "
        "ssl.MemoryBIO: a real TLS 1.3 handshake with real chain validation and "
        "no socket, because the founder's standing constraints forbid opening a "
        "network surface. No real peer has ever spoken it.",
        "Certificate distribution and key custody are unsolved. The CA is "
        "constructed in-process and `WorkloadIdentity.materialise()` writes the "
        "private key to a 0600 file inside a 0700 directory for the duration of "
        "a handshake, because Python's ssl module loads chains from paths and "
        "not from memory. Acceptable for consequence-inert internal use; not "
        "acceptable for production key custody.",
        "Revocation is an in-process serial set, not a signed CRL or OCSP. It is "
        "sufficient while revocation data never crosses a trust boundary, and "
        "insufficient the moment it does.",
    ], Owner.FOUNDER),

    _b(8, Rung.PROVEN, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.11 Operating-System Capability Security"),
        _impl("policy/consequence_gate.py"),
        _test("tests/unit/test_consequence_gate.py::test_capability_grant_matches_contract"),
        _closure("consequence_gate"), _contract("capability-grant"),
        _cap("kernel.consequence_gate"),
    ], [
        "Capability narrowing is enforced in-process by policy. It is not enforced "
        "by an operating-system or hardware boundary.",
    ], Owner.CHATGPT),

    _b(9, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#4.12 Containers, MicroVMs and WebAssembly"),
    ], [
        "No container runtime, image, or hardened profile exists in the kernel.",
        "Containment tier selection by consequence class is unbuilt.",
    ], Owner.CHATGPT),

    _b(10, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#4.12 Containers, MicroVMs and WebAssembly"),
    ], [
        "No microVM isolation for untrusted tools or generated code.",
    ], Owner.CHATGPT),

    _b(11, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#4.12 Containers, MicroVMs and WebAssembly"),
    ], [
        "No WebAssembly component boundary for portable narrow capabilities.",
    ], Owner.CHATGPT),

    # --------------------------------------------------------------- 12-22
    _b(12, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.3 Package Manager Architecture"),
        _impl("capabilities/genome.py"),
        _test("tests/unit/test_capabilities.py::test_unbounded_authority_refused"),
        _closure("capabilities"), _cap("kernel.genome_registry"),
    ], [
        "In-memory per process; nothing persists between runs.",
        "None of the thirteen FBO §4.3 lifecycle states (DISCOVERED … QUARANTINED) "
        "are represented; a genome is either registered or absent.",
        "No dependency resolution, version ranges, incompatibility declarations, "
        "attach/detach/migrate/rollback procedures, or benchmark history.",
        "No capability-genome contract schema types the genome at its boundary.",
    ], Owner.CHATGPT),

    _b(13, Rung.PROVEN, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.2 Linker Architecture"),
        _impl("linker/linker.py"),
        _test("tests/integration/test_phase_zero_connection.py::test_linker_resolves_bridge_a_edges"),
        _closure("linker"), _contract("organ-manifest"),
        _cap("kernel.institutional_linker"),
    ], [
        "The governed module loader of FBO §4.4 does not exist: no inspect, install, "
        "attach, activate, pause, shadow, compare, replace, rollback or detach "
        "operations, and therefore no way to attach a capability without a code change.",
    ], Owner.CHATGPT),

    # Was the ladder's only UNSUPPORTED row: the arsenal named this technology and
    # nothing specified it, so it could not claim even BLUEPRINT. Specified and
    # built together on purpose — a specification written alone would have lifted
    # the row to BLUEPRINT on paper while changing nothing, which is exactly the
    # gaming this ladder's own adversarial pass names.
    _b(14, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec("docs/INSTITUTIONAL_SHELL_SPEC.md#Pipeline model"),
        _impl("shell/pipeline.py"),
        _test("tests/unit/test_shell.py::test_a_stage_reporter_may_not_take_a_target"),
        _closure("shell"),
    ], [
        "READ-ONLY SUBSET. The arsenal declares this technology's consequence class "
        "as `internal_write`; the shell writes nothing. Pipelines that perform "
        "governed internal writes — recording a decision episode, advancing a "
        "workflow state machine — need the Consequence Gate on the path and a "
        "capability grant per pipeline, and are unbuilt. The technology is not "
        "complete; only its reporting half exists.",
        "Not PROVEN, and deliberately not reaching for it: a terminal-only surface "
        "has no wire boundary, so typing one with a contract schema would be "
        "ceremony rather than evidence. No organ manifest declares it either.",
        "UNLOCKED NOTHING DOWNSTREAM. Nothing in the arsenal depends on #14, so "
        "carrying it from UNSUPPORTED to EXERCISED raised no ceiling and moved no "
        "technology onto the frontier. `python -m blueprint.cycle` records that "
        "cycle as CEREMONY_SUSPECTED. The shell has standalone operator value and "
        "the verdict does not dispute that; it denies the work credit for advancing "
        "the critical path, which it did not.",
    ], Owner.CLAUDE),

    _b(15, Rung.PROVEN, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.7 Event-Sourcing Architecture"),
        _impl("events/engine.py"),
        _test("tests/unit/test_loom.py::test_unratified_pattern_never_weaves"),
        _closure("loom"), _contract("event"), _cap("kernel.loom"),
    ], [
        "Durable workflows survive kill and resume in-process; there is no external "
        "durable store, so durability does not survive host loss.",
    ], Owner.CHATGPT),

    _b(16, Rung.SKETCHED, Reality.IMPLEMENTED, [
        _spec("docs/release/canonical-v1/06-ci-two-run-record.md"),
        _impl(".github/workflows/canonical-ci.yml"),
    ], [
        "CI runs, but no test node asserts its behaviour: `scripts/ci/*.py` are "
        "invoked by the workflow and never by the suite, so a broken gate would "
        "not be caught by `python -m pytest`.",
        "No cross-repository CI covering the three organs together.",
    ], Owner.CLAUDE),

    _b(17, Rung.PROVEN, Reality.IMPLEMENTED, [
        _spec(f"{ARCH}#Causal Memory + Portfolio Governor"),
        _impl("memory/causal.py"),
        _test("tests/unit/test_memory.py::test_ancestry_walks_to_root"),
        _closure("memory"), _contract("outcome"), _cap("kernel.causal_memory"),
    ], [
        "Calibration has no real outcomes to calibrate against: verified external "
        "outcome count is 0.",
    ], Owner.EXTERNAL),

    _b(18, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.15 Search Engine and Knowledge Graph"),
        _impl("knowledge/graph.py"),
        _test("tests/unit/test_knowledge_graph.py::test_node_without_provenance_is_refused"),
        _closure("knowledge_graph"), _cap("kernel.knowledge_graph"),
    ], [
        "Read-only projection. The graph's output is not a typed institutional "
        "contract, so it cannot cross an organ boundary.",
        "Spans Repository → Commit → File → Contract → Capability → Organ. The "
        "Evidence → Claim → Contradiction → Prediction → Decision → Action → "
        "Receipt → Outcome → Revenue tail of FBO §4.15 has no populated sources yet.",
        "No query language and no index; traversal is linear over an in-memory graph.",
    ], Owner.CLAUDE),

    _b(19, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#4.15 Search Engine and Knowledge Graph"),
    ], [
        "No recommender. The Capability Router selects among declared "
        "implementations; it does not learn or rank from behaviour.",
    ], Owner.CHATGPT),

    _b(20, Rung.EXERCISED, Reality.SIMULATED, [
        _spec(f"{FBO}#4.13 Emulator and Digital-Twin Architecture"),
        _impl("twins/twin.py"),
        _test("tests/unit/test_twins.py::test_fork_is_hermetic"),
        _closure("twins"), _cap("kernel.institutional_twins"),
    ], [
        "Emulates institutional state, not a machine. No preserved legacy "
        "implementation is currently running as an emulator or regression oracle.",
    ], Owner.CHATGPT),

    _b(21, Rung.BUILT, Reality.SIMULATED, [
        _spec(f"{FBO}#4.13 Emulator and Digital-Twin Architecture"),
        _impl("twins/twin.py"),
        _test("tests/unit/test_twins.py::test_empty_corpus_refused"),
    ], [
        "No virtual machine and no machine snapshot. The hermetic twin fork "
        "snapshots institutional state only.",
    ], Owner.CHATGPT),

    _b(22, Rung.EXERCISED, Reality.SIMULATED, [
        _spec(f"{FBO}#4.13 Emulator and Digital-Twin Architecture"),
        _impl("twins/tribunal.py"),
        _test("tests/unit/test_twins.py::test_floor_raise_is_twin_superior_over_real_engine"),
        _closure("twins"), _cap("kernel.institutional_twins"),
    ], [
        "Simulation corpora are frozen fixtures. No simulation has been compared "
        "against a real external result.",
    ], Owner.EXTERNAL),

    # --------------------------------------------------------------- 23-34
    _b(23, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.8 Distributed-Systems Architecture"),
        _impl("events/spine.py"),
        _test("tests/unit/test_events.py::test_ingest_is_idempotent"),
        _closure("events"), _cap("kernel.event_spine"),
    ], [
        "Idempotent inbox and mediated outbox exist. Dead-letter handling, circuit "
        "breakers, backpressure, compensation across organs and reconciliation "
        "workers — all named in FBO §4.8 — do not.",
    ], Owner.CHATGPT),

    _b(24, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.9 Message Queue Architecture"),
        _impl("events/spine.py"),
        _test("tests/unit/test_events.py::test_type_must_be_namespaced"),
        _closure("events"), _cap("kernel.event_spine"),
    ], [
        "In-memory only. The organ-neutral transport interface has no SQLite/file "
        "implementation, no PostgreSQL outbox/inbox, and no broker adapter (FBO §4.9).",
    ], Owner.CHATGPT),

    # NOT CLOSED. Two routers exist and the canonical one is a founder decision.
    # The rung below describes `routing/decision_router.py` alone; it is not a
    # claim that technology #25 is settled. See the first gap.
    _b(25, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.14 Load Balancer and Cognitive Router"),
        _impl("routing/decision_router.py"),
        _test("tests/unit/test_decision_router.py::test_router_authorizes_nothing"),
        _test("tests/unit/test_routing_decision_contract.py::"
              "test_the_provider_is_called_in_exactly_one_place_in_the_institution"),
        _closure("decision_router"), _contract("routing-decision"),
        _cap("kernel.decision_router"),
    ], [
        # RESOLVED 2026-08-22 by FOUNDER-RULING-2026-08-22 ruling 4 (DEC-OM-001),
        # which selected routing/decision_router.py as the canonical selector.
        # The two gaps that named the unresolved selection and the untyped
        # boundary are closed and replaced by the record of what was done, so a
        # reader is not told a settled question is open. The third gap below is
        # UNCHANGED, because no outcome has been observed.
        "CANONICAL SELECTOR RESOLVED — `routing/decision_router.py` is canonical. "
        "PR #70 is preserved and its useful machinery rehomed rather than "
        "discarded (FBO §9, §12): `Implementation.origin`, the §4.3 LIFECYCLES, "
        "set_lifecycle and loss-recording now live in "
        "`capabilities/implementations.py`, which holds implementations and "
        "moves them through their lifecycle but neither ranks nor constructs. "
        "PR #70's `resolve()` — the three lines that selected and then called "
        "`chosen.provider()` — moved to `capabilities/instantiate.py`, where "
        "construction requires a capability and crosses the Consequence Gate. "
        "`provider()` now has exactly one call site in the institution, asserted "
        "structurally.",
        "PR #70's rule that `origin` is recorded but never scored is preserved: "
        "`Implementation.selectable_view()` is the only projection a selector "
        "sees and excludes both `origin` (so a mechanism cannot win for "
        "resembling a metaphor) and `provider` (so a selector that could reach "
        "the constructor could call it).",
        "No live traffic has routed through either router. Every decision is recorded, "
        "none has been compared against an outcome, so selection weights are declared "
        "rather than learned.",
        "The two routers are NOT yet benchmarked against each other. The ruling "
        "was explicit that architectural selection today must not be "
        "misrepresented as evidence that one router produces better outcomes; "
        "challenger evaluation waits for real outcomes, and CVO reads 0.",
    ], Owner.FOUNDER),

    _b(26, Rung.BUILT, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.11 Operating-System Capability Security"),
        _impl("adapters/bridge_transport.py"),
        _impl("identity/pki/ca.py"),
        _test("tests/integration/test_phase_zero_connection.py::test_forged_identity_replay_and_tamper_all_fail_closed"),
        _test("tests/unit/test_pki_mutual_tls.py::"
              "test_rotation_issues_an_independent_key_and_the_old_serial_can_be_retired"),
    ], [
        # AMENDED 2026-08-22 under FOUNDER-RULING-2026-08-22. Three of the four
        # things this gap named now exist and are tested; the rung deliberately
        # does NOT move. EXERCISED requires a CLOSURE_MODULE — it means the
        # technology runs inside the institution's own loop — and no loop uses
        # the PKI yet. The founder's instruction was to advance only what the
        # evidence earns and not to game the ladder, and passing tests are not
        # adoption.
        "Mutual TLS, per-service key isolation and certificate rotation now "
        "exist in `identity/pki/` and are adversarially tested (impersonation, "
        "wrong-cert identity, expiry, revocation, rotation, replay, downgrade "
        "and cross-organ handshakes all fail closed). NOT ADOPTED: no bridge, "
        "gate or organ calls `mutual_tls`, so the live trust boundary is "
        "unchanged.",
        "No network-level policy, and no network. The handshake is proven over "
        "in-memory BIOs; the transport half remains absent and founder-gated.",
        # CLOSED 2026-08-22 by `bridges/signal_to_venture.py`, which imports
        # `adapters` and runs it. Corrected as an authored change after
        # `python -m governance.gap_audit` reported it STALE — the register had
        # drifted, and a closed item on the founder's list is noise where his
        # attention is scarcest. The remaining zero-trust gap above is unaffected
        # and stays open.
    ], Owner.FOUNDER),

    _b(27, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.10 Service Discovery and RPC"),
        _impl("discovery/service.py"),
        _test("tests/unit/test_capability_discovery.py::test_discovery_grants_no_access"),
        _closure("discovery"), _cap("kernel.capability_discovery"),
    ], [
        "Discovery is in-process and read-only over local manifest files. There is "
        "no RPC transport, no signed remote manifest publication, and no generated "
        "typed service client (FBO §4.10).",
    ], Owner.CHATGPT),

    _b(28, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#4.10 Service Discovery and RPC"),
    ], [
        "No MCP server, client, or boundary envelope. Inbound MCP traffic has no "
        "path that turns it into a proposal rather than an instruction.",
    ], Owner.CHATGPT),

    _b(29, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.10 Service Discovery and RPC"),
        _impl("embassy/gate.py"),
        _test("tests/unit/test_embassy.py::test_guest_gets_minimum_privilege_passport"),
        _closure("embassy"), _cap("kernel.agent_embassy"),
    ], [
        "The Embassy admits foreign agents in-process. There is no agent-to-agent "
        "wire protocol, no boundary envelope, and no protocol-version negotiation.",
    ], Owner.CHATGPT),

    _b(30, Rung.PROVEN, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#4.11 Operating-System Capability Security"),
        _impl("policy/consequence_gate.py"),
        _test("tests/unit/test_consequence_gate.py::test_full_pipeline_reaches_recorded"),
        _closure("consequence_gate"), _contract("capability-grant"),
        _cap("kernel.consequence_gate"),
    ], [
        "The Gate has never executed a real external effect. Every recorded "
        "traversal terminates in a test executor.",
        # ADDED 2026-08-22 implementing ruling 3 of FOUNDER-RULING-2026-08-22.
        "The Gate does not emit witness contract v2. `provenance/witness_v2.py` "
        "records evidence_confidence, consequence_class and exposure_ceiling_usd "
        "under the signature, and the Gate already holds all three — Proposal "
        "carries the first two and grant['spending_limit_usd'] the third — but "
        "it calls the v1 constructor and drops them. Every witness in the ledger "
        "is therefore v1: calibration is impossible and Bridge G falls back to "
        "the actor's standing passport ceiling, which over-estimates. Adoption "
        "is roughly three lines and is blocked because "
        "policy/consequence_gate.py is a sealed continuity artifact — see "
        "docs/deliberations/CONTRADICTION-0002-continuity-baseline.md, which "
        "needs a founder decision.",
    ], Owner.FOUNDER),

    _b(31, Rung.BUILT, Reality.SIMULATED, [
        _spec("docs/PHASE_ZERO_REPORT.md#embassy pattern"),
        _impl("application/router.py"),
        _test("tests/unit/test_application_inertness.py::"
              "test_the_whole_request_path_produces_zero_external_effects"),
    ], [
        # BUILT under FOUNDER-RULING-2026-08-22 ruling 5 (DEC-OM-004), Option A:
        # the inert application half only. BUILT is what the ladder awards for a
        # tested implementation, and the rung deliberately stops there — there
        # is no closure module and no traffic, so EXERCISED would be inflation.
        # Reality is SIMULATED, not IMPLEMENTED: every byte this package has
        # ever parsed came from a fixture.
        "TRANSPORT HALF ABSENT AND FOUNDER-GATED. No listener, socket, bind, "
        "port, outbound connection or HTTP client exists in this institution. "
        "`application/` cannot serve a request and has never processed a byte "
        "originating outside its own process. Building the transport half "
        "requires a separate explicit founder authorization; it is not "
        "scheduled work.",
        "This is not a web server and must not be described as one. What exists "
        "is the pure half — bytes in, bytes out — with the seam at a function "
        "signature so that adding a network would be an addition someone has to "
        "make and review, never an emergent property of this package.",
        "Any network primitive appearing in application/ is a STOP-THE-LINE "
        "failure, not a code-review finding: its presence means the boundary "
        "was not being maintained. Enforced structurally over every module's "
        "AST and independently by running the full request path under "
        "sys.addaudithook with the parent process asserting.",
        "No kernel-side HTTP surface. The intake endpoint named as the next gate in "
        "the Phase Zero report is unbuilt, so organs must deliver through tests.",
    ], Owner.FOUNDER),

    _b(32, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#1. Governing Principle"),
    ], [
        "STILL BLUEPRINT, FOR A DIFFERENT REASON THAN RECORDED. This gap used to say "
        "the kernel could bind no implementation path across a repository boundary. "
        "That is no longer true: `blueprint/peer_evidence.py` binds a "
        "`peer:<organ>/<path>` locator to a commit-pinned attestation, which closes "
        "BLK-6's mechanism. Crossing the boundary showed the assumed understatement "
        "was not one. DALEOBANKS declares seven capabilities in its organ manifest — "
        "bridge security, adversarial committee, decision ledger, context packets, "
        "operator line, constitution service, wealthmachine client — and none of them "
        "implements an owned social network or community surface. The organ operates "
        "on a platform it does not own, which is distribution rather than ownership. "
        "So this stands at BLUEPRINT because no declared capability implements it, "
        "not because the kernel cannot see across the boundary.",
    ], Owner.CLAUDE),

    _b(33, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#1. Governing Principle"),
    ], ["No federated protocol work anywhere in the organism."], Owner.CHATGPT),

    _b(34, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#4.15 Search Engine and Knowledge Graph"),
    ], [
        "No recommendation-graph observability. Nothing measures how distribution "
        "surfaces actually route attention, so #49 and #50 optimise blind.",
    ], Owner.CHATGPT),

    _b(35, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec("docs/FOUNDRY_OMNIMORPH_V1.md"),
    ], ["No media engine of any kind in the kernel."], Owner.CLAUDE),

    # --------------------------------------------------------------- 36-46
    _b(36, Rung.PROVEN, Reality.IMPLEMENTED, [
        _spec(f"{ARCH}#Integrity without a blockchain"),
        _impl("provenance/ledger.py"),
        _test("tests/unit/test_provenance.py::test_tamper_detection"),
        _closure("evidence_ledger"), _contract("evidence"),
        _cap("kernel.evidence_ledger"),
    ], [
        "Content addressing covers ledger records only. Media, documents and "
        "artifacts are not content-addressed.",
    ], Owner.CHATGPT),

    _b(37, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#6. Connect the Existing Disconnected Systems"),
    ], ["No marketplace. Bridge F has no implementation."], Owner.FOUNDER),

    _b(38, Rung.EXERCISED, Reality.SIMULATED, [
        _spec(f"{FBO}#Bridge H: Revenue-to-Regeneration"),
        _impl("business/commercial_loop.py"),
        _test("tests/unit/test_business.py::test_no_delivery_before_recorded_payment"),
        _closure("business"),
    ], [
        "No payment rail is connected. Payment is a recorded fact in a fixture, "
        "never a settled transaction.",
    ], Owner.FOUNDER),

    _b(39, Rung.EXERCISED, Reality.SIMULATED, [
        _spec(f"{FBO}#11. Growth Doctrine"),
        _impl("capital/treasury.py"),
        _test("tests/unit/test_treasury.py::test_waterfall_funds_in_policy_order"),
        _closure("treasury"),
    ], [
        "The waterfall allocates simulated amounts. No account, ledger export, or "
        "reconciliation against a real balance exists.",
    ], Owner.FOUNDER),

    _b(40, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec(f"{FBO}#10. The Asymmetric Advantage Foundry"),
        _impl("evolution/spider_web.py"),
        _test("tests/unit/test_evolution.py::test_spider_web_eight_sides_and_super_nodes"),
        _closure("evolution"),
    ], [
        "The eight-sided audit analyses a design. It has never been applied to a "
        "market with real participants.",
    ], Owner.EXTERNAL),

    _b(41, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#4.15 Search Engine and Knowledge Graph"),
    ], ["No reputation system; no participants to have reputations."], Owner.EXTERNAL),

    _b(42, Rung.EXERCISED, Reality.SIMULATED, [
        _spec(f"{FBO}#4.13 Emulator and Digital-Twin Architecture"),
        _impl("twins/twin.py"),
        _test("tests/unit/test_twins.py::test_harm_increase_bars_promotion"),
        _closure("twins"), _cap("kernel.institutional_twins"),
    ], [
        "Twins fork institutional state. No twin mirrors a real external system.",
    ], Owner.CHATGPT),

    _b(43, Rung.EXERCISED, Reality.IMPLEMENTED, [
        _spec("docs/BUILD_ORDER.md"),
        _impl("verifier/v2/verify.py"),
        _test("tests/unit/test_evolution.py::test_verifier_levels_seven_ordered"),
        _closure("evolution"),
    ], [
        "The seven verifier levels rank evidence strength. They are not machine-"
        "checked proofs: no model checker, no theorem prover, no formal specification "
        "language beyond UCL's deterministic compilation.",
    ], Owner.CHATGPT),

    _b(44, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec("observability/README.md"),
    ], [
        "observability/ contains a specification and no implementation. There is no "
        "metric, trace, or log pipeline anywhere in the kernel.",
    ], Owner.CHATGPT),

    _b(45, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#4.12 Containers, MicroVMs and WebAssembly"),
    ], ["No security event pipeline; nothing to feed it."], Owner.CHATGPT),

    _b(46, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#4.6 Database Architecture"),
    ], [
        "No backup, no restore drill, no black-start recovery. The ledger persists "
        "to one location with no independent copy.",
    ], Owner.CHATGPT),

    # --------------------------------------------------------------- 47-55
    _b(47, Rung.EXERCISED, Reality.SIMULATED, [
        _spec(f"{FBO}#4.1 Compiler Architecture"),
        _impl("business/genome.py"),
        _test("tests/unit/test_business.py::test_complete_genome_compiles"),
        _closure("business"),
    ], [
        "Compiles business genomes from fixtures. No genome has been compiled from "
        "a real venture.",
    ], Owner.EXTERNAL),

    _b(48, Rung.BUILT, Reality.SIMULATED, [
        _spec("docs/ADE1_GOVERNED_RUNTIME.md"),
        _impl("egregore/runtime.py"),
        _test("tests/unit/test_egregore_runtime.py::test_deliberation_selects_deterministically_and_preserves_dissent"),
    ], [
        # SUPERSEDED 2026-08-22. The previous text read "egregore/ is imported by
        # no non-test module and is registered in no kernel closure registry ...
        # connected to nothing that runs." All three clauses closed in the same
        # session that wrote them: `closure/integration_registry.py` imports the
        # package, `egregore-standing-cognition` is registered with the closure
        # controller, and the signal -> tick -> candidate -> gate -> receipt
        # pathway runs. Reported STALE by `python -m governance.gap_audit`, which
        # caught its own author's drift. Replaced rather than deleted: what stays
        # open is narrower than what was claimed, and saying so is the point.
        "Every signal the standing-cognition runtime has ever ingested was "
        "constructed by a test. The pathway to the Gate runs, but nothing has "
        "entered it from outside the institution.",
        "Proposer and evaluator organs are callables supplied by tests, not real agents.",
    ], Owner.CLAUDE),

    _b(49, Rung.EXERCISED, Reality.SIMULATED, [
        _spec("docs/FOUNDRY_OMNIMORPH_V1.md"),
        _impl("foundry/company.py"),
        _test("tests/unit/test_foundry.py::test_unratified_company_cannot_publish"),
        _closure("foundry"),
    ], [
        "No company has published anything. Every publish path terminates at the "
        "Gate in a test.",
    ], Owner.FOUNDER),

    _b(50, Rung.EXERCISED, Reality.SIMULATED, [
        _spec("docs/FOUNDRY_OMNIMORPH_V1.md"),
        _impl("foundry/territory.py"),
        _test("tests/unit/test_foundry.py::test_valid_territory_is_rooted_dag_with_one_exit"),
        _closure("foundry"),
    ], [
        "Territory graphs are validated but never traversed by a real audience.",
    ], Owner.EXTERNAL),

    _b(51, Rung.BUILT, Reality.SIMULATED, [
        _spec("docs/release/package-3/EXPERIMENT_SPEC.md"),
        _impl("evolution/repair/candidate.py"),
        _test("tests/unit/test_repair_candidates.py::test_candidate_is_deterministic"),
    ], [
        "Candidate generation is confined to a frozen experiment. It is registered "
        "in no closure registry and cannot run outside its harness.",
    ], Owner.CLAUDE),

    _b(52, Rung.BUILT, Reality.SIMULATED, [
        _spec("docs/release/package-3/EXPERIMENT_SPEC.md"),
        _impl("evolution/repair/harness.py"),
        _test("tests/unit/test_repair_harness.py::test_the_capsule_records_the_whole_cycle"),
    ], [
        "One recorded repair cycle over one deliberately removed component. No "
        "repair has been driven by an unplanned failure.",
    ], Owner.CLAUDE),

    _b(53, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#4.1 Compiler Architecture"),
    ], [
        "No self-hosting toolchain. Every build depends on external toolchains the "
        "institution neither owns nor can reproduce offline.",
    ], Owner.CHATGPT),

    _b(54, Rung.BLUEPRINT, Reality.BLUEPRINT_ONLY, [
        _spec(f"{FBO}#Bridge H: Revenue-to-Regeneration"),
    ], [
        "No agent-native commerce. Depends on payments (#38), marketplaces (#37) "
        "and reputation (#41), none of which exist.",
    ], Owner.FOUNDER),

    _b(55, Rung.EXERCISED, Reality.SIMULATED, [
        _spec(f"{FBO}#11. Growth Doctrine"),
        _impl("capital/treasury.py"),
        _test("tests/unit/test_treasury.py::test_regenerative_debt_blocks_expansion_until_repaired"),
        _closure("treasury"),
    ], [
        "Regenerative debt is enforced over simulated capital. No restricted fund, "
        "no real obligation, no reconciliation.",
    ], Owner.FOUNDER),
)

BINDINGS: dict[int, TechnologyBinding] = {b.technology_id: b for b in _BINDINGS}

if set(BINDINGS) != set(ARSENAL):
    missing = sorted(set(ARSENAL) - set(BINDINGS))
    extra = sorted(set(BINDINGS) - set(ARSENAL))
    raise RuntimeError(
        "the blueprint must bind exactly the Foundry arsenal; "
        f"missing={missing} extra={extra}"
    )


def binding(technology_id: int) -> TechnologyBinding:
    try:
        return BINDINGS[technology_id]
    except KeyError as exc:
        raise KeyError(f"no blueprint binding for technology {technology_id}") from exc


# --------------------------------------------------------------------------
# Validation and award
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class BindingAudit:
    technology_id: int
    name: str
    claimed_rung: Rung | None
    awarded_rung: Rung | None
    reality: Reality
    owner: Owner
    resolutions: tuple[Resolution, ...]
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def over_claimed(self) -> bool:
        if self.claimed_rung is None:
            return False            # claiming nothing cannot over-claim
        if self.awarded_rung is None:
            return True
        return rung_index(self.claimed_rung) > rung_index(self.awarded_rung)

    @property
    def unresolved(self) -> tuple[Resolution, ...]:
        return tuple(r for r in self.resolutions if not r.ok)


def validate_binding(b: TechnologyBinding, root: str = KERNEL_ROOT) -> BindingAudit:
    """Resolve every reference and award the rung the evidence actually supports.

    A claim above what the evidence supports is reported as a problem. The
    awarded rung is never raised to meet the claim.
    """
    resolutions = resolve_all(b.evidence, root)
    kinds = satisfied_kinds(resolutions)
    awarded = highest_supported_rung(kinds)

    problems: list[str] = []
    for r in resolutions:
        if not r.ok:
            problems.append(f"unresolved {r.kind.value}: {r.detail}")

    if b.claimed_rung is None:
        pass                        # nothing claimed; nothing to refuse
    elif awarded is None:
        problems.append(
            f"claimed {b.claimed_rung.value} but no rung is supported: missing "
            + ", ".join(sorted(k.value for k in missing_for(Rung.BLUEPRINT, kinds)))
        )
    elif rung_index(b.claimed_rung) > rung_index(awarded):
        gap = missing_for(b.claimed_rung, kinds)
        problems.append(
            f"claimed {b.claimed_rung.value} but evidence supports only "
            f"{awarded.value}; missing " + ", ".join(sorted(k.value for k in gap))
        )

    return BindingAudit(
        technology_id=b.technology_id,
        name=b.name,
        claimed_rung=b.claimed_rung,
        awarded_rung=awarded,
        reality=b.reality,
        owner=b.owner,
        resolutions=resolutions,
        problems=tuple(problems),
    )


def effective_rung(technology_id: int, root: str = KERNEL_ROOT) -> Rung | None:
    """The rung the evidence supports right now. None means not even BLUEPRINT."""
    return validate_binding(binding(technology_id), root).awarded_rung


def audit(root: str = KERNEL_ROOT) -> tuple[BindingAudit, ...]:
    """Validate all 55 bindings, in technology order."""
    return tuple(validate_binding(BINDINGS[i], root) for i in sorted(BINDINGS))


def require_honest(root: str = KERNEL_ROOT) -> None:
    """Raise if any binding claims a rung its evidence does not support."""
    bad = [a for a in audit(root) if a.problems]
    if bad:
        lines = [f"  #{a.technology_id} {a.name}: {'; '.join(a.problems)}" for a in bad]
        raise LadderError("blueprint bindings are not honest:\n" + "\n".join(lines))
