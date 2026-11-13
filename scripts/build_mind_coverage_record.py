"""Build docs/collaboration/MIND-COVERAGE-2026-10-21.json and .md from the repository. Run from the repository root:

    python scripts/build_mind_coverage_record.py

Read-only apart from the two record files. Evidence references are resolved here: L(path, pattern) returns
"path:line" for the first matching line and stops loudly when nothing matches, so every file:line was found, not
typed. PR #179 references are read with git show at its pinned head.
"""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
BASE = "239a87f"
MERGE_BASE = "463a9d0"
PR179 = "0067be6"
STATUSES = ["ABSENT", "INVENTORIED", "IMPLEMENTED", "INTEGRATED", "BENCHMARKED", "ADMITTED", "ATTACHED", "EXERCISED"]
RANK = {s: i for i, s in enumerate(STATUSES)}


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)


def L(path, pattern, flags=0):
    text = (ROOT / path).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if re.search(pattern, line, flags):
            return f"{path}:{i}"
    raise SystemExit(f"no match for {pattern!r} in {path}")


def G(path, pattern, sha=PR179):
    """A file:line on PR #179's branch, cited as git:<sha>:<path>:<line>."""
    out = git("show", f"{sha}:{path}")
    if out.returncode:
        raise SystemExit(f"missing on {sha}: {path}")
    for i, line in enumerate(out.stdout.splitlines(), 1):
        if re.search(pattern, line):
            return f"git:{sha}:{path}:{i}"
    raise SystemExit(f"no match for {pattern!r} in {sha}:{path}")


def P(path, pointer=None):
    if not (ROOT / path.split("#")[0]).exists():
        raise SystemExit(f"missing {path}")
    return path + (f"#{pointer}" if pointer else "")


def lineage_of(paths):
    """both: the cited file exists at the merge base of #158's line and #179; #158: only on this line; #179: only there."""
    on158 = on179 = False
    for p in paths:
        if p.startswith("git:"):
            on179 = True
            continue
        f = p.split("#")[0]
        f = re.sub(r":\d+$", "", f)
        on158 = True
        if git("cat-file", "-e", f"{MERGE_BASE}:{f}").returncode == 0:
            on179 = True
    return "both" if on158 and on179 else "#179" if on179 else "#158"


# ---------------------------------------------------------------- mechanisms
ms = json.loads(subprocess.run([sys.executable, "scripts/mind_status.py"], cwd=ROOT, capture_output=True,
                               text=True, env={"PYTHONPATH": ".", "PATH": "/usr/bin:/bin"}).stdout)
MECH = {}


def mech(mid, status, evidence, note, world=None, lineage=None, default_attached=False, s158="same", s179="same"):
    """s158 / s179: the status this mechanism attains on #158's line (this tree) and on PR #179; None = absent there."""
    ev = list(evidence)
    lin = lineage or lineage_of(ev)
    if s158 == "same":
        s158 = status if lin in ("both", "#158") else None
    if s179 == "same":
        s179 = status if lin in ("both", "#179") else None
    MECH[mid] = {"status": status, "status_on_158": s158, "status_on_179": s179, "evidence": ev, "note": note,
                 "benchmark_world": world, "lineage": "both" if s158 and s179 else "#158" if s158 else "#179",
                 "default_attached_by_registration": default_attached}


GENOME_FILE = {}
for f in sorted((ROOT / "greg/cognition/genomes").glob("*.py")):
    for i, line in enumerate(f.read_text().splitlines(), 1):
        m = re.search(r'family="([a-z_]+)"', line)
        if m and "intelligence_id" in (f.read_text().splitlines()[i - 2] + line):
            GENOME_FILE.setdefault(m.group(1), f"{f.relative_to(ROOT)}:{i}")
        elif m and m.group(1) not in GENOME_FILE and re.search(r'^\s+family="', line):
            GENOME_FILE.setdefault(m.group(1), f"{f.relative_to(ROOT)}:{i}")

for row in ms["mechanisms"]:
    if row["kind"] != "genome":
        continue
    fam = row["id"].removeprefix("cognition.")
    h = row["heldout"]
    adm = h["status"]
    status = "ADMITTED" if adm in ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY") and h["current"] else "BENCHMARKED"
    code = GENOME_FILE.get(fam)
    if code is None:
        raise SystemExit(f"genome code not found: {fam}")
    mech(f"genome:{fam}", status,
         [code, L("greg/cognition/genomes/library.py", r"^def catalog_families"), h["evidence"]],
         f"{row['intelligence_id']} {row['version_current']}: {adm} at {h['version_measured']} "
         f"(mind_status label {row['label']}); registered VERIFIED, withheld, not attached; reachable through "
         f"cognition.reason by the catalog projection",
         world=row["benchmark_world"])

# #158 catalog families (operation contract). Seed families are attached at registration by code, not by a founder.
SEED = {"micro", "exact", "estimation", "formal", "optimization", "causal", "evidence", "semantic"}
OPS3 = "docs/evidence/greg-operation-admission/2026-10-16-v3/README.md"
ops = {  # #179 operation-family admission v3 (seeds 5001-5040, converged tree of #179)
    "probabilistic": "DEFAULT_FOR_GEOMETRY", "control": "DEFAULT_FOR_GEOMETRY", "micro": "DEFAULT_FOR_GEOMETRY",
    "sequential": "DEFAULT_FOR_GEOMETRY", "information": "DEFAULT_FOR_GEOMETRY", "game": "DEFAULT_FOR_GEOMETRY",
    "exact": "DEFAULT_FOR_GEOMETRY", "pattern": "REJECTED", "evolutionary": "REJECTED", "simulation": "REJECTED",
    "graph": "EXPERIMENTAL", "collective": "EXPERIMENTAL",
    "crowd": "DEFAULT_FOR_GEOMETRY (dense, v2 geometry); EXPERIMENTAL on sparse crowds, where the one-step weighted vote beats it 32-8",
    "swarm": "DEFAULT_FOR_GEOMETRY against random search; loses to DE 17-21 and post hoc to multistart L-BFGS-B 7-32",
    "blackbox": "SUPERSEDED (multistart L-BFGS-B wins 23-11)", "robust_pattern": "DEFAULT_FOR_GEOMETRY (p = 0.032; ESD competitor ties 4-7; v2 read EXPERIMENTAL)",
}
cat_src = (ROOT / "greg/cognition/catalog.py").read_text().splitlines()
for i, line in enumerate(cat_src, 1):
    m = re.match(r'\s+"([a-z_]+)": \((\d),', line)
    if not m:
        continue
    fam = m.group(1)
    ev = [f"greg/cognition/catalog.py:{i}", L("greg/cognition/cortex.py", r"^def reason\(")]
    status, note = "INTEGRATED", "operation family on GREG's cognition path"
    if fam in SEED:
        note += "; seed family, ATTACHED at registration by catalog.initial_state (not a founder attach)"
    else:
        note += "; registered VERIFIED (withheld)"
    if fam in ops:
        a = ops[fam]
        ev.append(G(OPS3, rf"^\| {fam} "))
        status = "ADMITTED" if a.startswith("DEFAULT") or a.startswith("NICHE") else "BENCHMARKED"
        note += f"; #179 operation admission v3: {a} (in #179's index only; #158's index has no row, so mind_status labels it BUILT)"
    mech(f"family:{fam}", status, ev, note, default_attached=fam in SEED, s158="INTEGRATED", s179=status)

for fam, op in (("robust_pattern", "robust_anomalies"), ("crowd", "crowd_label"), ("swarm", "swarm_minimize"),
                ("blackbox", "evolve_blackbox")):
    a = ops[fam]
    mech(f"family:{fam}", "ADMITTED" if a.startswith("DEFAULT") else "BENCHMARKED",
         [G("greg/cognition/catalog.py", rf'"{fam}":'), G("greg/cognition/repertoire.py", rf"{op}"),
          G(OPS3, rf"^\| {fam}"), G("docs/evidence/greg-genome-admission/2026-10-14/README-v2.md", rf"^\| {fam}")],
         f"PR #179 only (greg/cognition/repertoire.py): {a}", lineage="#179")
mech("eval:crowd_sparse", "BENCHMARKED", [G("docs/evidence/pr155-crowd-sparse/2026-10-14/README.md", r"Frozen status")],
     "Dawid-Skene EXPERIMENTAL on sparse multi-class crowds; the one-step agreement-weighted vote beats it 32-8 "
     "(p = 9.1e-5): the acquisition target, not built", lineage="#179")

# cortex organs
organ_ev = {
    "cognition.cortex": ("cortex/routing.py", r"def "),
    "cognition.cortex.estimation.fermi": ("cortex/organs/estimation.py", r"Fermi"),
    "cognition.cortex.formal.z3": ("cortex/organs/formal.py", r"z3|Z3"),
    "cognition.cortex.optimization.cpsat": ("cortex/organs/cpsat.py", r"cp_model|CP-SAT|cpsat"),
    "cognition.cortex.extraction.schedule": ("cortex/organs/schedule_extraction.py", r"\"\"\""),
    "cognition.cortex.evidence_causal": ("cortex/organs/evidence_causal.py", r"Evidence/Causal"),
    "cognition.cortex.semantic": ("cortex/organs/semantic.py", r"\"\"\""),
    "cognition.cortex.deterrence.accountability": ("cortex/organs/deterrence.py", r"\"\"\""),
}
REH = "tests/evidence/greg-cortex-rehearsal/rehearsal-ledger.jsonl"
XGEO = "tests/evidence/greg-crossgeo-v0.3/results.json"
for oid, (f, pat) in organ_ev.items():
    ev = [L(f, pat), L("greg/cognition/catalog.py", r"Polyintelligence Cortex \(PR #141\)")]
    status, note = "INTEGRATED", "cortex organ behind the cortex router; attached at registration (not a founder attach)"
    if oid in ("cognition.cortex.estimation.fermi", "cognition.cortex.formal.z3", "cognition.cortex.optimization.cpsat"):
        ev.append(P(XGEO, "verdict"))
        status = "BENCHMARKED"
        note += "; frozen cross-geometry v0.3 (GAIN_VERIFIED_AGAINST_RUN_BASELINES vs the static router; model arms NOT_RUN); no admission-rule verdict"
    if oid in ("cognition.cortex", "cognition.cortex.extraction.schedule", "cognition.cortex.optimization.cpsat"):
        ev.append(L(REH, re.escape(f'"method": "{oid}"') if oid != "cognition.cortex" else r'"method": "cognition.cortex"'))
        ev.append(P("tests/evidence/greg-cortex-rehearsal/rehearsal-summary.json"))
        status = "EXERCISED"
        note += ("; EXERCISED: supervised-body mission m:cortex-rehearsal (2026-10-01) with kill -9, restart, approve "
                 "and one settlement; per-test Ed25519 key, NOT Alfonso; Linux container, not the founder's body")
    if oid == "cognition.cortex.evidence_causal":
        ev.append(P("docs/evidence/greg-composition-lift/2026-10-08/results-v2.json", "summary.F2R"))
        status = "BENCHMARKED"
        note += "; measured as a stage of P6 F2/F2R (identify_then_optimize), not alone"
    if oid == "cognition.cortex.semantic":
        note += "; no founder-selected local model configured, so every semantic arm is NOT_RUN"
    mech(f"organ:{oid}", status, ev, note, default_attached=True, s158=status,
         s179=status if git("cat-file", "-e", f"{PR179}:{REH}").returncode == 0 or status != "EXERCISED" else "BENCHMARKED")

# composition recipes (P6)
for r, row in ms and json.loads((ROOT / "docs/evidence/greg-mind-evidence-index.json").read_text())["recipes"].items():
    ev = [L("greg/cognition/composition.py", rf'"{r}"'), row["evidence"]]
    note = f"P6 {row['family']}: {row['status']} ({row['wins']}-{row['losses']}, one-sided p {row['p_one_sided']:.3g})"
    if r == "graph_then_allocate":
        ev.append(P("docs/evidence/greg-composition-lift/2026-10-16-f7-mcf/README.md"))
        note += "; F7 re-scored with flow_expansion_mcf as a constituent: MATCH / NO_LIFT (the single exact method is canonical)"
    if r == "track_then_staff":
        note += "; the EWMA-ratio ablation is 4.5% cheaper than routed (v5 README); data redistribution terms unverified"
    if r == "forecast_then_staff":
        note += "; does not beat the weekly-mean practitioner pipeline on day count (40-50)"
    mech(f"recipe:{r}", "BENCHMARKED", ev, note + "; a recipe has no admission status; routed through cognition.reason {'chain'}")

# Layer-5 and whole-machine mechanisms
C = "greg/cognition/compiler.py"
mech("compiler", "INTEGRATED", [L(C, r"^def run\("), L("greg/cognition/cortex.py", r'"compile" in params'),
                                 P("tests/unit/test_greg_competency_compiler.py")],
     "Competency Compiler: one request shape on cognition.reason; routes on the frozen evidence index and settled outcomes")
mech("operators", "INTEGRATED", [L(C, r"^OPERATORS = \("), L(C, r"^DIRECTIVE_MODELS = \{"), L(C, r"^OPERATOR_HOMES = \{")],
     "15 executable typed operators; 33 directive models mapped (15 operators, 19 carried elsewhere); "
     "no operator has an effect benchmark (most cite 'rule test only')")
mech("geometry", "INTEGRATED", [L(C, r"^class CompetencyGeometry")], "every section-9 field, all optional, unknowns kept unknown")
mech("receipt", "INTEGRATED", [L(C, r'receipt = \{"schema": SCHEMA'), L("greg/cognition/contracts.py", r"class CognitiveReceipt")],
     "all 29 section-12 receipt fields present (latency as latency_s)")
mech("composition", "BENCHMARKED", [L("greg/cognition/composition.py", r"^def run\("), P("docs/evidence/greg-composition-lift/2026-10-14-accounting/README.md")],
     "P6 typed composition; eight frozen families")
mech("p4_conditional", "BENCHMARKED", [L("greg/cognition/conditional_competence.py", r"P4 conditional competence"),
                                         P("docs/evidence/greg-learned-routing/2026-10-08/README.md")],
     "decisive retest REGRESSION 160 vs 162: demoted; the static default stays")
mech("p8_evolution", "BENCHMARKED", [L("greg/cognition/evolution.py", r"P8 protected evolutionary cognition"),
                                       P("docs/evidence/greg-protected-evolution/2026-10-16-cr-6/README.md"),
                                       P("docs/evidence/greg-protected-evolution/2026-10-16-cr-6/canary"),
                                       P("docs/evidence/greg-protected-evolution/2026-10-21-immune-7/DECISION.md")],
     "7 designs (#179 holds cycles 1-5 and the #155 alternative; cycle 6, the canary and cycle 7 are on #158 only): cycles 1-5 REJECT, cycle 6 RETAIN (105-73, p = 0.00995; passes the four-attempt 0.0125, not the "
     "programme-wide 0.00833; PROPOSED_NOT_APPLIED; random restart at least as good, 80-89), canary CANARY_PASSES, "
     "cycle 7 not run (pilot NOT_VIABLE)")
mech("p8_routing_alt_179", "BENCHMARKED", [G("greg/cognition/evolution_routing.py", r"PR #155 lineage alternative"),
                                            G("docs/evidence/greg-protected-evolution/2026-10-14/LINEAGE-POINTER.md", r".")],
     "#155-lineage routing-genome evolution; retained as an isolated experimental alternative, REJECT (no headroom)", lineage="#179")
mech("genesis", "INTEGRATED", [L("greg/genesis.py", r"Capability Genesis"), L(C, r"^GENESIS_SEARCH"),
                                P("tests/unit/test_greg_cognition_genesis.py"),
                                P("tests/evidence/greg-open-source-genesis-2026-10-01/qualification.json")],
     "cognition deficit -> registry -> withheld genome -> installed open-source package on a Mechanism Card -> builder "
     "-> founder; tested on test-key missions (tmp bodies); no recorded body mission for a cognition deficit")
mech("genesis_live_function", "EXERCISED", [P("tests/evidence/greg-product/genesis-live-claude-code.json"),
                                             P("tests/evidence/greg-product/product-path-summary.json")],
     "Capability Genesis on the product path (2026-09-26): a non-cognition function built by a coding agent, verified "
     "by a frozen held-out oracle, mission BLOCKED -> ACHIEVED. Not a cognition deficit")
mech("human_route", "INTEGRATED", [L("greg/cognition/human.py", r"Human judgment as a typed intelligence"),
                                    L(C, r"^HUMAN_ROLES"), L(C, r"^def human_packet")],
     "THIS REQUIRES QUALIFIED HUMAN JUDGMENT route; judgments typed with role, domain, conflicts, refusal; never "
     "aggregated; decided only by the founder's signed answer bound to the question; no real human judgment recorded")
mech("metaconsensus", "INTEGRATED", [L("greg/cognition/verification.py", r"^def metaconsensus")],
     "jurisdiction-preserving metaconsensus over receipts; never a majority vote")
mech("verifier", "BENCHMARKED", [L("greg/cognition/verification.py", r"Independent falsifier"),
                                  P("tests/evidence/cortex-mutants-2026-10-01")],
     "independent falsifier; Z3 certification of OPTIMAL/INFEASIBLE claims; mutation audits")
mech("adversarial_organ", "IMPLEMENTED", [L("cortex/organs/adversarial.py", r"Independent adversarial verifier")],
     "rule-based adversarial verifier inside the cortex pipeline; not an organ manifest of its own")
mech("settlement", "INTEGRATED", [L("greg/cognition/settlement.py", r"Outcome competence"), L(C, r"^def _settled_inhibition")],
     "outcome competence replayed from receipts and appraisals; settled demotion after >= 10 outcomes; no real outcomes settled on a founder body")
mech("gravity", "INTEGRATED", [L("greg/gravity.py", r"Goal Gravity"), P("tests/unit/test_greg_gravity.py") if (ROOT / "tests/unit/test_greg_gravity.py").exists() else L("greg/gravity.py", r"def ")],
     "one turn of persistent pressure: Backcast GPS -> sensing -> compiler -> Foundry -> ranker -> triage; tested, not run on a real founder goal")
mech("foundry", "INTEGRATED", [L("foundry/lawful_leverage.py", r"Lawful Leverage Foundry")],
     "generate, mutate, recombine, hard-filter, estimate, falsify, Pareto-compare lawful interventions; reached by Goal Gravity")
mech("advantage_179", "IMPLEMENTED", [G("greg/cognition/advantage.py", r"Lawful Asymmetric Advantage Compiler")],
     "#179 control-map intervention generator; candidates stay UNESTIMATED; canonical generator is the Foundry", lineage="#179")
mech("resilience", "IMPLEMENTED", [L("greg/resilience.py", r"Resilience and antifragility evidence")],
     "recovery episodes, common-cause, dependency concentration, honest ANTIFRAGILE_EVIDENCE verdict, decoupling warning; read-only projection")
mech("community", "IMPLEMENTED", [L("greg/dataplane.py", r"^def community_evidence")],
     "typed, manipulation-resistant community evidence with minority reports; never authority")
mech("protection", "IMPLEMENTED", [L("greg/cognition/protection.py", r"victim-protection")],
     "affected-party harm vectors and lawful deterrence review packets; no admission benchmark")
mech("mind_status", "IMPLEMENTED", [L("scripts/mind_status.py", r"Reality ledger")],
     "BUILT/SIMULATED/HELDOUT_SUPPORTED/EXTERNALLY_VERIFIED/UNRESOLVED/FRONTIER per mechanism; #158 index only")
mech("worlds", "IMPLEMENTED", [L("greg/cognition/worlds.py", r"natural_data")], "natural vs mathematical vs simulated world declaration")
mech("genome_library_179", "IMPLEMENTED", [G("greg/cognition/genome_library.py", r"IntelligenceGenome library")],
     "#179 inventory of every family with layer, buildability and admission", lineage="#179")
mech("mission_cognition_ask_179", "INTEGRATED", [G("greg/missions.py", r"def _cognition_ask")],
     "#179: a mission whose cognition receipt abstained for unattached families raises one attach ask", lineage="#179")
mech("mica_lab", "BENCHMARKED", s158="IMPLEMENTED", s179="BENCHMARKED", evidence=[L("developmental/mica.py", r"."), G("docs/evidence/greg-developmental-sweep/2026-10-14/README.md", r"Verdict \(frozen\)")],
     note="MICA/CDPE local field repair: PARITY with an adaptive central replanner on 40 unseen-damage seeds (#179)")
mech("reserved", "IMPLEMENTED", [L("greg/cognition/reserved.py", r"^RESERVED_WITHOUT_EXECUTOR")],
     "reconciliation of cortex reserved families with their executors")
mech("path_frontier", "INVENTORIED", [L("greg/path.json", r'"frontier_backcasts"')], "13 frontier backcasts")
mech("calibration", "INTEGRATED", [L("greg/cli.py", r"calibration")], "greg cognition calibration over founder-signed realizations")
mech("vpl_metrics", "IMPLEMENTED", [L("cortex/evaluation/composition_lift/vpl_metrics.py", r"routing_regret")],
     "VPL accounting metrics (false-answer, cost, latency deltas, routing regret)")


def S(mid):
    return MECH[mid]["status"]


# ---------------------------------------------------------------- directive items
def item(iid, name, mechs=(), precursors=(), status=None, evidence=(), note="", search=None, frontier=None):
    mechs = list(mechs)
    st = status or (max((S(m) for m in mechs), key=RANK.get) if mechs else None)
    def best(key):
        vals = [MECH[m][key] for m in mechs if MECH[m][key]]
        return max(vals, key=RANK.get) if vals else None
    s158, s179 = (best("status_on_158"), best("status_on_179")) if mechs and not status else (None, None)
    ev = list(evidence)
    for m in mechs:
        ev += MECH[m]["evidence"][:2]
    if st is None:
        st = "ABSENT" if search else "INVENTORIED"
    if st == "ABSENT" and not search:
        raise SystemExit(f"{iid}: ABSENT without a search")
    if mechs and not status:
        lin = "both" if s158 == st and s179 == st else "#158" if s158 == st else "#179"
    else:
        lin = lineage_of(ev) if ev else "n/a"
        s158 = st if lin in ("both", "#158") else None
        s179 = st if lin in ("both", "#179") else None
    out = {"id": iid, "requirement": name, "status": st, "status_on_158": s158, "status_on_179": s179,
           "lineage": lin, "mechanisms": mechs, "precursors": list(precursors), "evidence": ev, "note": note}
    if search:
        out["search"] = search
    if frontier:
        out["nearest_falsifiable_precursor"] = frontier
    return out


D7 = "docs/intent/sources/POLYINTELLIGENCE-MIND-CONTINUATION-DIRECTIVE-2026-10-07-source.md"
SRC = lambda pat: L(D7, pat)
grep_dirs = "greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition)"

L1 = [
    item("L1.deterministic_reflexes", "deterministic reflexes", ["family:micro"], note="ternary set-point reflex"),
    item("L1.state_machine", "state-machine intelligence", ["genome:basal_breaker"], ["genome:basal_hysteresis"]),
    item("L1.local_sensing", "local sensing", [], ["genome:basal_kalman", "genome:basal_bayes_filter", "community"],
         search=f"grep -i 'sensor|sensing' in {grep_dirs}: only greg/gravity.py typed situations and greg/dataplane.py; "
                "worlds.py states GREG has no physical sensors",
         note="no Layer-1 sensing primitive; estimators consume supplied signals"),
    item("L1.threshold_control", "threshold control", ["family:micro", "genome:basal_hysteresis"]),
    item("L1.homeostatic_controllers", "homeostatic controllers", ["genome:pid_simopt", "genome:basal_pid", "family:control"]),
    item("L1.anomaly_response", "anomaly response", ["genome:basal_breaker", "family:pattern", "family:robust_pattern"]),
    item("L1.associative_microcircuits", "associative microcircuits", [], ["family:micro"],
         evidence=[L("greg/cognition/reserved.py", r"cortex.developmental.molecular_micro")],
         note="reserved cortex.developmental.molecular_micro has no executor"),
    item("L1.simple_adaptive_filters", "simple adaptive filters", ["genome:basal_bayes_filter", "genome:basal_kalman"]),
    item("L1.local_error_correction", "local error correction", [], ["genome:develop_repair", "genome:basal_hysteresis"],
         search=f"grep -i 'error.correct' in {grep_dirs}: hits only forecasting residual text and benchmark wording, no primitive"),
    item("L1.rule_based_classification", "rule-based classification", ["family:pattern", "family:robust_pattern"], ["genome:collective_immune"]),
    item("L1.feedback_control", "feedback control", ["genome:pid_simopt", "family:control", "genome:control_mpc"]),
    item("L1.bounded_memory", "bounded memory", ["genome:basal_breaker"], ["genome:basal_hysteresis"], note="sliding failure window"),
    item("L1.hysteresis", "hysteresis", ["genome:basal_hysteresis"]),
    item("L1.rate_control", "rate control", [], ["genome:basal_breaker"],
         search=f"grep -i 'token.bucket|rate.limit|rate_control' in {grep_dirs}: no match"),
    item("L1.resource_regulation", "resource regulation", ["genome:basal_bandit"], ["genome:collective_market"]),
    item("L1.eval.pid", "evaluate PID", ["genome:basal_pid", "genome:pid_simopt", "family:control"],
         note="basal_pid SUPERSEDED (0-30 vs SIMC competitor); pid_simopt DEFAULT (simulated plants)"),
    item("L1.eval.finite_state_control", "evaluate finite-state control", ["genome:basal_breaker"]),
    item("L1.eval.bayesian_filters", "evaluate simple Bayesian filters", ["genome:basal_bayes_filter"]),
    item("L1.eval.exponential_smoothing", "evaluate exponential smoothing", ["genome:forecast_quantile"],
         note="damped-trend exponential smoothing with quantiles (a Layer-3 genome; the only natural-data admission)"),
    item("L1.eval.kalman", "evaluate Kalman-family estimators", ["genome:basal_kalman"]),
    item("L1.eval.bandits", "evaluate lightweight bandits", ["genome:basal_bandit"]),
    item("L1.eval.associative_networks", "evaluate associative networks", [], [],
         search=f"grep -i 'associat|hopfield|hebb' in {grep_dirs}: only reserved.py text and evidence_causal 'association' claims"),
    item("L1.eval.small_local_learners", "evaluate small local learners", [], ["genome:basal_bandit"],
         search=f"grep -i 'online learn|perceptron|local learner|LMS' in {grep_dirs}: no match"),
]

L2 = [
    item("L2.hive_quorum", "Hive / quorum intelligence (alternatives, evidence accumulation, recruitment, cross-inhibition, threshold)",
         ["genome:collective_quorum", "family:collective"], note="simulated world; catalog quorum EXPERIMENTAL on #179"),
    item("L2.ant_stigmergy", "Ant / stigmergic intelligence (route search, exploration, workflow routing, path discovery)",
         ["genome:collective_aco"], note="MAX-MIN ant system on symmetric TSP (mathematical instances); adaptive workflow routing not built"),
    item("L2.slime_mold", "Slime-mold / adaptive-network intelligence", ["genome:collective_physarum"]),
    item("L2.flock", "Flock / local-coordination intelligence", ["genome:collective_flock", "family:swarm"],
         note="flock local rules SUPERSEDED; PSO (#179) beats random search only, loses to multistart L-BFGS-B post hoc"),
    item("L2.immune", "Immune intelligence (recognition, tolerance, decoupling, quarantine, challenge, incident memory, recoupling)",
         ["genome:collective_immune", "resilience"], ["genesis"],
         evidence=[L("greg/cognition/reserved.py", r'"cortex.collective.immune"')],
         note="negative selection NICHE on a simulated world; decoupling warning in resilience.py; no anomaly-tolerance family"),
    item("L2.ecological", "Ecological intelligence (diversity, niches, succession, extinction, rare-niche preservation)",
         ["settlement"], ["genome:collective_market"], evidence=[L("greg/cognition/reserved.py", r'"cortex.collective.ecology_market"')],
         note="admission statuses NICHE/SUPERSEDED act as niche and extinction; methods do not bid; no ecology executor"),
    item("L2.market", "Market / resource-allocation intelligence", ["genome:collective_market"],
         note="clock auction DEFAULT on a simulated world"),
    item("L2.human_collective", "Human collective intelligence (typed human sources, no majority vote)",
         ["human_route", "community", "family:crowd"], ["eval:crowd_sparse"]),
]

L3 = []
def l3(i, n, m=(), pre=(), **k):
    L3.append(item("L3." + i, n, m, pre, **k))

l3("semantic", "Semantic intelligence (LLM interpretation, hypotheses, translation, synthesis, ontology, qualitative)",
   ["organ:cognition.cortex.semantic", "family:semantic"], note="no local model configured: every semantic arm NOT_RUN")
l3("fermi", "Fermi / reference-class estimation", ["organ:cognition.cortex.estimation.fermi", "recipe:estimate_then_optimize"])
l3("bayesian", "Bayesian intelligence (priors, likelihood, posterior, calibration, sequential evidence)",
   ["genome:bayes_interval", "family:probabilistic", "genome:basal_bayes_filter", "calibration"],
   evidence=[L("greg/cognition/reserved.py", r'"cortex.probabilistic.bayes"')], note="no probabilistic-programming executor")
l3("causal", "Causal intelligence (DAGs, confounding, intervention, counterfactual, identification, discriminating evidence)",
   ["genome:causal_backdoor", "organ:cognition.cortex.evidence_causal", "recipe:identify_then_optimize"])
l3("sim.monte_carlo", "Monte Carlo", ["genome:mc_expectation", "family:simulation"])
l3("sim.bootstrap", "bootstrap", ["genome:bootstrap_ci"], note="REJECTED")
l3("sim.scenario", "scenario simulation", ["family:simulation"], evidence=[L("greg/cognition/reserved.py", r'"cortex.simulation.twin"')],
   note="iid Bernoulli Monte Carlo REJECTED on #179; no twin")
l3("sim.uncertainty_propagation", "uncertainty propagation", ["organ:cognition.cortex.estimation.fermi"], note="Gaussian-copula range propagation")
l3("sim.stochastic_processes", "stochastic processes", ["genome:queue_erlang"], ["genome:basal_bayes_filter"])
l3("sim.rare_event", "rare-event estimation", ["genome:mc_importance"])
l3("con.smt", "SMT", ["organ:cognition.cortex.formal.z3", "family:formal"])
l3("con.sat", "SAT", [], ["organ:cognition.cortex.formal.z3", "organ:cognition.cortex.optimization.cpsat"],
   search=f"grep 'pysat|SAT solver|CNF' in {grep_dirs}: no match; SAT is reached only through Z3 and CP-SAT")
l3("con.cpsat", "CP-SAT", ["organ:cognition.cortex.optimization.cpsat"])
l3("con.csp", "CSP", ["organ:cognition.cortex.optimization.cpsat", "family:optimization"])
l3("con.integer_programming", "integer programming", ["genome:milp_optimize", "organ:cognition.cortex.optimization.cpsat"])
l3("con.mip", "mixed-integer optimization", ["genome:milp_optimize"])
l3("con.exact_combinatorial", "exact or bounded combinatorial solvers", ["genome:knapsack_bnb", "genome:mechanism_check"])
l3("opt.linear", "linear optimization", ["family:optimization"], ["genesis"], evidence=[L("greg/cognition/linear.py", r"lp.optimize")])
l3("opt.nonlinear", "nonlinear optimization", ["family:swarm", "family:blackbox"],
   evidence=[L("greg/cognition/genomes/competitors.py", r"L-BFGS|minimize")], note="black-box only (#179); multistart L-BFGS-B exists only as a competitor arm")
l3("opt.convex", "convex optimization", [], ["family:optimization"],
   search=f"grep 'cvxpy|convex optim|SLSQP' in {grep_dirs}: only competitors.py L-BFGS arm; no convex solver family")
l3("opt.integer", "integer optimization", ["organ:cognition.cortex.optimization.cpsat", "genome:milp_optimize"])
l3("opt.assignment", "assignment", ["genome:assignment_lsa"], ["genesis"], evidence=[L("greg/cognition/assignment.py", r"Linear assignment")])
l3("opt.matching", "matching", ["genome:graph_matching"])
l3("opt.knapsack", "knapsack", ["genome:knapsack_bnb", "genome:dp_knapsack"])
l3("opt.packing", "packing", [], ["organ:cognition.cortex.optimization.cpsat", "genome:knapsack_bnb"],
   search=f"grep -i 'bin.pack|packing' in {grep_dirs}: no packing family")
l3("opt.scheduling", "scheduling", ["organ:cognition.cortex.optimization.cpsat", "organ:cognition.cortex.extraction.schedule", "genome:develop_constraint_release"])
l3("opt.routing", "routing", ["genome:collective_aco", "genome:grid_dijkstra"])
l3("opt.resource_allocation", "resource allocation", ["genome:collective_market", "genome:basal_bandit", "recipe:graph_then_allocate"])
l3("graph.shortest_path", "shortest path", ["genome:grid_dijkstra", "family:graph"])
l3("graph.mincut_maxflow", "min-cut / max-flow", ["genome:flow_maxflow"])
l3("graph.centrality", "centrality", [], [], search=f"grep -i 'centrality' in {grep_dirs}: no match")
l3("graph.reachability", "reachability", ["genome:verify_modelcheck"], evidence=[L("greg/cognition/network.py", r"graph.shortest_path")])
l3("graph.matching", "matching (graph)", ["genome:graph_matching"])
l3("graph.community_topology", "community / topology analysis", [], ["genome:collective_physarum"],
   search=f"grep -i 'louvain|community detection|modularity' in {grep_dirs}: only unrelated prose in flow.py/graph_or.py")
l3("graph.control_point", "control-point and dependency analysis", ["genome:flow_maxflow", "operators"])
l3("graph.dag", "DAG reasoning", ["genome:critical_path"])
l3("graph.critical_path", "critical path", ["genome:critical_path"])
l3("dp", "dynamic programming", ["genome:dp_knapsack", "family:sequential"], note="dp_knapsack SUPERSEDED by branch and bound; backward induction DEFAULT on #179")
l3("or.queueing", "queueing", ["genome:queue_erlang"])
l3("or.scheduling", "scheduling (OR)", ["organ:cognition.cortex.optimization.cpsat"])
l3("or.inventory", "inventory", ["genome:newsvendor_compile"], note="COMPOSITION_ONLY")
l3("or.capacity", "capacity", ["genome:flow_expansion_mcf"])
l3("or.allocation", "allocation", ["genome:graph_matching", "genome:collective_market"])
l3("or.network_optimization", "network optimization", ["genome:min_cost_flow", "genome:flow_expansion_mcf"])
l3("or.stochastic_optimization", "stochastic optimization", ["genome:newsvendor_compile", "recipe:estimate_then_optimize"])
l3("or.decision_analysis", "decision analysis", ["family:information", "genome:decision_preposterior"])
l3("ctl.feedback", "feedback control (L3)", ["genome:pid_simopt"])
l3("ctl.mpc", "model-predictive control", ["genome:control_mpc"])
l3("ctl.state_estimation", "state estimation", ["genome:basal_kalman", "genome:basal_bayes_filter"])
l3("ctl.robust", "robust control", [], ["genome:control_mpc"], search=f"grep -i 'robust control|robust MPC|H-infinity|tube' in {grep_dirs}: no match")
l3("search.bnb", "branch and bound", ["genome:knapsack_bnb"])
l3("search.beam", "beam search", [], [], search=f"grep -i 'beam' in {grep_dirs}: no match")
l3("search.astar", "A*", ["genome:search_astar"], note="SUPERSEDED by grid_dijkstra")
l3("search.tree", "tree search", ["family:sequential"], note="finite-horizon backward induction")
l3("search.mcts", "Monte Carlo tree search", [], [], search=f"grep -i 'mcts|monte carlo tree' in {grep_dirs}: no match")
l3("search.heuristic", "heuristic search", ["genome:search_astar", "genome:collective_aco"])
l3("search.iterative_deepening", "iterative deepening", [], [], search=f"grep -i 'iterative deepening|IDA' in {grep_dirs}: no match")
l3("evo.ga", "genetic algorithms", [], ["p8_evolution", "genome:develop_constraint_release"],
   search=f"grep -i 'genetic algorithm' in {grep_dirs}: no match; P8 uses mutation + crossover over closed configuration spaces")
l3("evo.es", "evolutionary strategies", ["family:evolutionary", "family:blackbox"], note="differential evolution: REJECTED on a quadratic (v1), SUPERSEDED on its native geometry (#179)")
l3("evo.program_mutation", "program mutation", ["genome:synth_cegis"], ["p8_evolution"], note="template-parameter synthesis; P8 never evolves code")
l3("evo.quality_diversity", "quality-diversity", [], [], search=f"grep -i 'quality.diversity|MAP-Elites' in {grep_dirs}: no match")
l3("evo.novelty", "novelty search", [], [], search=f"grep -i 'novelty search' in {grep_dirs}: no match")
l3("evo.hyperheuristics", "hyperheuristics", [], ["genome:develop_constraint_release"], search=f"grep -i 'hyperheuristic' in {grep_dirs}: no match; constraint release recombines pipeline operators (nearest)")
l3("info.entropy", "entropy", ["genome:info_experiment"])
l3("info.mutual_information", "mutual information", ["genome:info_experiment"])
l3("info.information_gain", "information gain", ["genome:info_experiment"])
l3("info.voi", "value of information", ["family:information", "genome:decision_preposterior", "recipe:bayes_then_voi"])
l3("info.mdl", "compression / minimum description", [], [], search=f"grep -i 'description length|MDL|compression' in {grep_dirs}: no match")
l3("info.experiment_selection", "experiment selection", ["genome:info_experiment"])
l3("game.strategic", "strategic interaction / best responses / equilibrium", ["genome:bimatrix_nash", "genome:game_lp_dual", "family:game"])
l3("game.repeated", "repeated games", [], [], search=f"grep -i 'repeated game' in {grep_dirs}: no match")
l3("game.bargaining", "bargaining models", [], [], search=f"grep -i 'bargain|nash bargaining' in {grep_dirs}: no match")
l3("game.commitment", "credible commitment analysis", [], [], search=f"grep -i 'commitment|stackelberg' in {grep_dirs}: no match")
l3("mechanism_design", "mechanism-design intelligence", ["genome:mech_vcg", "genome:mechanism_check"])
l3("formal.theorem_proving", "theorem proving / proof assistants", [], ["organ:cognition.cortex.formal.z3"],
   search=f"grep -i 'theorem prov|Lean|Coq|Isabelle' in {grep_dirs}: no match")
l3("formal.model_checking", "model checking", ["genome:verify_modelcheck"])
l3("formal.temporal_logic", "temporal logic", ["genome:verify_liveness"], note="fair-SCC liveness; no general LTL/CTL")
l3("formal.type_level", "type-level guarantees", [], [], evidence=[L("greg/cognition/contracts.py", r"def strict_data")],
   note="strict typed contracts guard inputs; no type-level proof family")
l3("formal.property_based", "property-based testing", [], [], search="grep 'hypothesis.' in greg/cognition and tests: no property-based testing library use")
l3("formal.exhaustive_state", "exhaustive state exploration", ["genome:verify_modelcheck", "genome:mechanism_check"])
l3("adv.counterexamples", "counterexamples / falsification", ["verifier", "genome:synth_cegis"])
l3("adv.strongest_opposing", "strongest opposing case / steelman", ["operators", "receipt"])
l3("adv.red_team", "red-team / abuse-case / exploit-path search", ["adversarial_organ", "foundry"],
   note="rule-based verifier and Foundry hard filters; no generative red-team search family")
l3("adv.assumption_attacks", "assumption attacks", ["adversarial_organ", "operators"])
l3("cf.decisions_policies", "counterfactual decisions / policies / sequences", ["composition", "foundry"],
   note="ablation and do-nothing arms; a counterfactual family is not routable")
l3("cf.architectures_stress", "alternative architectures and stress scenarios", ["p8_evolution"], note="P8 stress sets")
l3("fc.time_series", "time-series forecasting", ["genome:forecast_quantile"])
l3("fc.judgmental", "judgmental forecasting", [], ["human_route"], search=f"grep -i 'judgmental' in {grep_dirs}: no match")
l3("fc.reference_class", "reference-class forecasts", ["operators"], note="reference_class operator re-routes to Bayesian families; no forecast family")
l3("fc.probabilistic_event", "probabilistic event forecasts", ["genome:bayes_interval", "family:probabilistic"])
l3("fc.scenario", "scenario forecasts", [], ["organ:cognition.cortex.estimation.fermi"], search=f"grep -i 'scenario forecast' in {grep_dirs}: no match")
l3("fc.calibration", "forecast calibration", ["calibration", "genome:forecast_quantile"])
l3("human_adjudication", "Human/expert adjudication: THIS REQUIRES QUALIFIED HUMAN JUDGMENT", ["human_route"])

MODELS = []
from importlib import import_module
sys.path.insert(0, str(ROOT))
comp = import_module("greg.cognition.compiler")
opids = {o.operator_id for o in comp.OPERATORS}
for model, op in comp.DIRECTIVE_MODELS.items():
    if op in opids:
        MODELS.append(item(f"MM.{op}", model, ["operators"], evidence=[L(C, rf'"{op}"')],
                           note="executable typed operator; no effect benchmark"))
    else:
        MODELS.append(item(f"MM.{op}", model, status="IMPLEMENTED", evidence=[L(C, rf'"{op}": "')],
                           note="carried by: " + comp.OPERATOR_HOMES[op]))

L4 = [
    item("L4.local_competent_units", "local competent units", ["genome:develop_repair", "mica_lab"]),
    item("L4.bounded_membranes", "bounded membranes", [], ["genome:develop_repair"],
         evidence=[L("greg/isolation.py", r".")], note="isolation is process/Landlock confinement, not a developmental membrane"),
    item("L4.local_signaling", "local signaling", ["genome:develop_repair", "mica_lab"]),
    item("L4.shared_target_states", "shared target states", ["genome:develop_repair", "mica_lab"]),
    item("L4.error_gradients", "error gradients", ["genome:develop_repair"]),
    item("L4.distributed_repair", "distributed repair", ["genome:develop_repair", "mica_lab"],
         note="NICHE on a simulated lattice; MICA PARITY with an adaptive central replanner; generalized repair not replicated (12-3 then 7-8)"),
    item("L4.differentiation", "differentiation", [], [], search="grep -i 'differentiat' in greg/cognition/genomes/developmental.py and developmental/: no executable mechanism"),
    item("L4.organ_formation", "tissue/organ formation", ["genesis"], ["genome:develop_repair"],
         frontier="robust_unscripted_organ_formation backcast (greg/path.json)"),
    item("L4.topology_change", "topology change", ["genome:develop_constraint_release", "genome:collective_physarum"]),
    item("L4.alternative_path_recovery", "alternative-path recovery", ["genome:develop_repair", "mica_lab"]),
    item("L4.constraint_release", "constraint-release experimentation", ["genome:develop_constraint_release"]),
    item("L4.evolutionary_recombination", "evolutionary recombination", ["p8_evolution", "genome:develop_constraint_release"]),
    item("L4.capability_formation", "capability formation", ["genesis", "genesis_live_function"]),
    item("L4.developmental_lineage", "developmental lineage", ["p8_evolution"], note="P8 lineage records and freezes"),
    item("L4.unscripted_structural_search", "unscripted but bounded structural search", ["genome:develop_constraint_release"]),
    item("L4.now.target_fields", "computational target fields", ["mica_lab", "genome:develop_repair"]),
    item("L4.now.cellular_automata", "cellular automata", [], ["genome:develop_repair"], search="grep -i 'cellular automat' in greg/ and developmental/: lattice rules in develop_repair only, no CA family"),
    item("L4.now.graph_diffusion", "graph diffusion", [], ["mica_lab"], search="grep -i 'diffusion' in greg/cognition and developmental/: no graph-diffusion family; cross_substrate backcast proposes one"),
    item("L4.now.evolutionary_topology_search", "evolutionary topology search", ["genome:develop_constraint_release"]),
    item("L4.now.simulated_repair", "simulated repair", ["genome:develop_repair"]),
    item("L4.now.alternative_structural_pathways", "alternative structural pathways", ["genome:develop_constraint_release", "mica_lab"]),
]

L5 = [
    item("L5.loop.observe_to_geometry", "observe discrepancy -> characterize geometry -> decompose epistemic requirements -> uncertainty -> consequence class", ["compiler", "geometry"]),
    item("L5.loop.recruit_compose", "recruit candidates -> compose complementary intelligences", ["compiler", "composition"]),
    item("L5.loop.independent_first_pass", "preserve independent first-pass outputs", ["metaconsensus"], evidence=[L("greg/cognition/cortex.py", r"independent first passes")]),
    item("L5.loop.inhibit_weak_routes", "inhibit weak routes", ["compiler", "settlement"], evidence=[L(C, r"^EXCLUDED = ")]),
    item("L5.loop.dissent", "preserve dissent", ["receipt", "metaconsensus"]),
    item("L5.loop.evaluators_typed_evidence", "select evaluators -> produce typed evidence", ["verifier", "receipt"]),
    item("L5.loop.compare_alternatives", "compare alternatives", ["compiler"]),
    item("L5.loop.authority_gate", "request authority where required -> act through existing Gate", ["compiler", "organ:cognition.cortex.optimization.cpsat"],
         evidence=[L(C, r"EXISTING_KERNEL_GATE_REQUIRED")]),
    item("L5.loop.observe_outcome_credit", "observe real outcome -> attribute credit and error -> update competence", ["settlement", "calibration"],
         note="settlement replays receipts and appraisals; real-world outcomes settled only in the cortex rehearsal (test key)"),
    item("L5.loop.residual_gap_genesis", "detect residual gap -> build/acquire -> test independently -> add to repertoire", ["genesis"]),
    item("L5.problem_geometry", "machine-readable ProblemGeometry (section 9)", ["geometry"]),
    item("L5.epistemic_vs_authority", "epistemic routing separate from authority routing (section 10)", ["compiler", "receipt"]),
    item("L5.high_risk_rule", "high consequence raises requirements; never routes to SMT (section 11)", ["operators"],
         evidence=[L(C, r'Operator\("consequence_raises_requirements"')]),
    item("L5.cognitive_receipts", "cognitive receipts with the 29 section-12 fields", ["receipt"]),
    item("L5.p6_composition_gate", "Step A: P6 composition lift with a natural family", ["composition", "recipe:forecast_then_staff", "recipe:track_then_staff"]),
    item("L5.p4_retest", "Step B: one decisive P4 retest", ["p4_conditional"]),
    item("L5.p8_protected_evolution", "Step C: P8 protected evolutionary cognition", ["p8_evolution", "p8_routing_alt_179"]),
    item("L5.genome_library", "Section 14: executable IntelligenceGenome library", status="ADMITTED",
         evidence=[L("greg/cognition/genomes/contract.py", r"."), L("greg/cognition/genomes/library.py", r"^MODULES = "),
                   P("docs/evidence/greg-genome-admission/2026-10-16-v4/README.md")],
         note="47 executable genomes on #158; 35 ADMITTED (DEFAULT or NICHE); #179 adds 4 operation families and an inventory"),
    item("L5.admission_rule", "Section 15: admission rule with seven outcomes", [], status="BENCHMARKED",
         evidence=[L("greg/cognition/genomes/admission.py", r"."), P("docs/evidence/greg-genome-admission/2026-10-16-v4/README.md")],
         note="FRONTIER_HORIZON is a status the compiler excludes; no genome currently holds it"),
    item("L5.vpl", "Section 16: Verified Polyintelligence Lift and its tracked metrics", ["composition", "vpl_metrics"],
         evidence=[P("docs/evidence/greg-composition-lift/2026-10-14-accounting/README.md")],
         note="VPL_LIFT recipes 6 of 7 on the index (F1, F2R, F4, F6, F7, F8; F5 NO_LIFT); natural 3 of 4 (F6, F7, F8); routing adds nothing within a family; every lift costs latency 1.5-5.2x; F7 NO_LIFT once flow_expansion_mcf is a constituent"),
    item("L5.leverage_compiler", "Section 17: lawful asymmetric advantage compiler (generation, not only ranking)", ["foundry", "advantage_179"]),
    item("L5.asymmetric_objective", "Section 18: eligibility gates before a vector objective", ["foundry"]),
    item("L5.goal_gravity", "Section 19: Goal Gravity / Infinite Goal Chase", ["gravity", "mission_cognition_ask_179"]),
    item("L5.asymmetry_production_line", "Section 20: every closed cycle leaves a durable asset", ["foundry", "gravity"]),
    item("L5.antifragility", "Section 21: resilience and evidence-gated antifragility", ["resilience"]),
    item("L5.immune", "Section 22: truthful immune system (drift, scope, privilege pressure, quarantine, recoupling, decoupling)", ["resilience", "genome:collective_immune"], ["genesis"]),
    item("L5.community", "Section 23: community intelligence through typed evidence", ["community"]),
    item("L5.new_intelligence", "Section 24: generate new intelligence when necessary", ["genesis"], ["genesis_live_function"],
         note="the recorded live Genesis run formed a non-cognition function; cognition deficits are covered by tests only"),
    item("L5.buildability", "Section 25: BUILDABLE_NOW / EXPERIMENTAL_NOW / FRONTIER_RESEARCH / SCIENCE_FICTION_DESCENDANT", ["path_frontier", "genome_library_179"]),
    item("L5.metrics_distinct", "Section 27: VPL and VEPMC kept distinct", ["mind_status"], evidence=[P("tests/evidence/greg-product/product-path-summary.json")],
         note="VEPMC row missing mac_body: VEPMC = 0"),
    item("L5.reality_ledger", "Section 31.17 reality ledger", ["mind_status", "worlds"]),
    item("L5.interp.meniscus", "Section 2: meniscus as the verified-envelope frontier with margins", ["foundry"], note="harm ceilings and margins in the Foundry hard filter"),
    item("L5.interp.shield", "Section 2: impermeable shield as layered prevention/recovery", ["resilience", "verifier"]),
    item("L5.interp.deterrence", "Section 2: lawful deterrence only", ["organ:cognition.cortex.deterrence.accountability", "protection"]),
    item("L5.interp.victim_protection", "Section 2: victim protection first-class", ["protection"]),
    item("L5.interp.collateral_vector", "Section 2: collateral harm as a vector, hard constraints first", ["protection", "foundry"]),
]

LAYERS = {"1": ("PRIMITIVE / BASAL INTELLIGENCE", L1), "2": ("DISTRIBUTED / COLLECTIVE INTELLIGENCE", L2),
          "3": ("SOLVER / MACRO-COGNITIVE INTELLIGENCE", L3), "3.mental_models": ("Section 6 mental models as executable operators", MODELS),
          "4": ("DEVELOPMENTAL / MORPHOGENETIC INTELLIGENCE", L4),
          "5": ("META-INTELLIGENCE / INSTITUTIONAL COLLECTIVE COGNITION", L5)}

# ---------------------------------------------------------------- section 31
s31_text = {}
src = (ROOT / D7).read_text().splitlines()
start = next(i for i, l in enumerate(src) if l.startswith("31. REQUIRED END STATE"))
for i in range(start, start + 30):
    m = re.match(r"^(\d+)\. (.*)$", src[i])
    if m and int(m.group(1)) <= 17 and i > start:
        s31_text[int(m.group(1))] = (m.group(2), f"{D7}:{i + 1}")

S31 = {
    1: ("PARTLY_MET", [L("greg/cognition/genomes/library.py", r"^MODULES = "), L(C, r"^def run\(")],
        "Every layer has executable mechanisms: L1 6 genomes + micro; L2 6 genomes (+ crowd, swarm on #179); L3 33 genomes plus the catalog operation families (21 catalog families across layers) and 8 cortex organs; L4 develop_repair, develop_constraint_release, P8, Genesis; L5 the compiler.",
        "Directive-named families with no executor: associative microcircuits/networks, small local learners, rate control, beam/MCTS/iterative deepening, GA/QD/novelty/hyperheuristics, MDL, repeated games/bargaining/commitment, theorem proving, robust control, centrality, community/topology analysis, convex optimization, judgmental and scenario forecasting, global workspace, active inference, ecology bidding, differentiation, cellular automata, graph diffusion."),
    2: ("PARTLY_MET", [P("docs/evidence/greg-genome-admission/2026-10-16-v4/README.md"), "docs/evidence/greg-mind-evidence-index.json"],
        "47 genomes benchmarked under the admission rule (35 admitted); cortex Fermi/Z3/CP-SAT benchmarked in cross-geometry v0.3; #179 benchmarked 16 operation families.",
        "Unbenchmarked major families: semantic (no model, NOT_RUN), SAT, convex/nonlinear optimization, packing, centrality, community analysis, beam/MCTS, GA/QD/novelty, MDL, repeated games/bargaining, theorem proving, robust control, judgmental/scenario forecasting, probabilistic programming, digital twins. Most Layer 1, 2 and 4 admissions are on simulated worlds."),
    3: ("PARTLY_MET", [L(C, r"^STATUS_RANK = "), L(C, r"^def _rank\("), P("tests/unit/test_mind_status.py")],
        "The compiler ranks candidates by frozen admission status, subregion evidence and settled outcomes; tests check it routes exactly on fresh positive evidence.",
        "No genome is attached, so on a real body the compiler issues attach asks and routes to fallbacks; no competence has been settled from real founder missions; within a family, geometry routing added nothing in any P6 run (the router chose the static recipe)."),
    4: ("MET", [L("greg/cognition/composition.py", r"^def run\("), L(C, r'"intermediate_receipts"'), L(REH, r'"method": "cognition.cortex.extraction.schedule"')],
        "Typed translation between stage receipts; compilation receipts carry intermediate receipts; schedule extraction -> CP-SAT ran on the supervised body.",
        "Composition has been exercised on a body only for the cortex extraction -> CP-SAT pipeline, with a test key."),
    5: ("PARTLY_MET", ["docs/evidence/greg-mind-evidence-index.json", P("docs/evidence/greg-composition-lift/2026-10-14-accounting/README.md"), P("docs/evidence/greg-composition-lift/2026-10-16-f7-mcf/README.md")],
        "Six recipes show VPL_LIFT on held-out families (F1, F2R, F4, F6, F7, F8); natural families lift 3 of 4 (F6, F7, F8).",
        "Lift is composition over GREG's own repertoire: F7 is NO_LIFT once flow_expansion_mcf is a constituent and ties the OR practitioner; F8's EWMA ablation is cheaper; F6 loses to the weekly-mean practitioner on day count; routing adds nothing within a family; every lift costs 1.5-5.2x latency; F8 data rights unverified. No family drawn from GREG's own operating needs."),
    6: ("MET", [P("docs/evidence/greg-learned-routing/2026-10-08/README.md"), L(C, r'"NO_LIFT": 8')],
        "Decisive pre-registered P4 retest: REGRESSION (160 vs 162); conditional routing demoted, static default kept.",
        "None for the condition; conditional competence may be retested only with a new pre-registration."),
    7: ("PARTLY_MET", [P("docs/evidence/greg-protected-evolution/2026-10-16-cr-6/README.md"), P("docs/evidence/greg-protected-evolution/2026-10-21-immune-7/DECISION.md"), L("greg/cognition/evolution.py", r"^def stress_worsened")],
        "Cycle 6 RETAIN under a sealed, clean-room evaluator: held-out 105-73, p = 0.00995, mean loss 29.6% lower; canary passes.",
        "One kept improvement in seven designs; it misses the programme-wide threshold 0.00833; random restart is at least as good (80-89); the proposal is not applied (founder adoption); no second target (cycle 7 NOT_VIABLE); the stress-gate repair's historical-equivalence claim is unverified (its test exercises the fallback path)."),
    8: ("PARTLY_MET", [P("docs/evidence/greg-genome-admission/2026-10-15-v3/README.md"), G(OPS3, r"crowd \(sparse")],
        "ACO DEFAULT and Physarum NICHE on mathematical instances; market DEFAULT, quorum and immune NICHE on simulated worlds.",
        "Flock SUPERSEDED; PSO and Dawid-Skene beat only weak baselines (#179); no collective mechanism admitted on natural data; immune tolerance, ecology bidding and PSO (on #158) have no executor."),
    9: ("MET", [L("greg/cognition/genomes/developmental.py", r"developmental.repair.sequenced_local_gradient"), "docs/evidence/greg-genome-admission/2026-10-15-v3/results.json#genomes.develop_constraint_release", L("greg/cognition/worlds.py", r"natural_data")],
        "develop_repair NICHE (simulated lattice) and develop_constraint_release DEFAULT (mathematical instances); worlds.py and the frontier backcasts keep biological claims out.",
        "Generalized repair did not replicate (12-3, then 7-8); MICA ties a central replanner (#179); no capability-topology assembly."),
    10: ("MET", [L("greg/cognition/human.py", r"Human judgment as a typed intelligence"), P("tests/unit/test_greg_competency_compiler.py")],
         "Typed human route with role, competence domain, conflicts, refusal and question-bound founder decision.",
         "No real qualified-human judgment has been recorded; only the founder role can decide."),
    11: ("MET", [L(C, r'"authority_created": False'), P("tests/evidence/cognition-2026-09-30/authority.log")],
         "Every receipt carries authority_created false and EXISTING_KERNEL_GATE_REQUIRED; P8 decisions PROPOSED_NOT_APPLIED.",
         "A universal negative is tested, not proven; it holds for the paths the tests cover."),
    12: ("MET", [L(C, r'receipt = \{"schema": SCHEMA')], "All 29 section-12 fields.", "Proof artifacts are typed, but later_appraisal and outcome_link are filled only after settlement, which has no real founder outcomes."),
    13: ("MET", [L(C, r"^EXCLUDED = "), L(C, r"^def _settled_inhibition"), P("tests/unit/test_mind_status.py")],
         "SUPERSEDED/REJECTED/COMPOSITION_ONLY genomes are excluded; NO_LIFT recipes ranked last; P4 demoted; settled outcomes inhibit after 10.",
         "On-body inhibition has never fired on real outcomes."),
    14: ("MET", [P("tests/unit/test_greg_cognition_genesis.py"), L(C, r"^GENESIS_SEARCH")],
         "A compiler CAPABILITY_DEFICIT enters Genesis: withheld genome, then an installed package qualified on a frozen oracle, then the founder; the original mission closes after attach.",
         "Exercised only on test-key tmp bodies; the recorded live Genesis run (2026-09-26) built a non-cognition function."),
    15: ("PARTLY_MET", [L("greg/cognition/cortex.py", r"^def solve\("), P("tests/evidence/greg-product/product-path-summary.json")],
         "One cognition entry on the capability/mission path; no second registry, router, ledger or authority.",
         "VEPMC = 0 (mac_body missing); organs (DALEOBANKS, WMI) do not consume cognition receipts; Goal Gravity never ran on a real founder goal."),
    16: ("MET", [L("greg/path.json", r'"frontier_backcasts"')],
         "13 frontier backcasts, each with nearest falsifiable experiment and buildability.",
         "None missing; precursors for most are untested."),
    17: ("PARTLY_MET", [L("scripts/mind_status.py", r"Reality ledger"), L("greg/cognition/worlds.py", r"natural_data")],
         "mind_status labels every mechanism BUILT/SIMULATED/HELDOUT_SUPPORTED/EXTERNALLY_VERIFIED/UNRESOLVED/FRONTIER.",
         "#158's index has no rows for #179's operation-family admissions (mind_status labels those families BUILT while #179 holds frozen DEFAULT verdicts); 'exercised on a mission' is not a label; no all-lineage data-exposure ledger."),
}
section31 = []
for n in range(1, 18):
    text, loc = s31_text[n]
    verdict, ev, have, gap = S31[n]
    section31.append({"n": n, "condition": text, "source": loc, "verdict": verdict, "evidence": ev,
                      "lineage": lineage_of(ev), "attained": have, "remaining_gap": gap})

# ---------------------------------------------------------------- frontier
path = json.loads((ROOT / "greg/path.json").read_text())
frontier = []
for fb in path["frontier_backcasts"]:
    frontier.append({"id": fb["id"], "destination": fb["destination"], "buildability_status": fb["buildability_status"],
                     "status": "INVENTORIED", "current_precursor": fb["current_precursor"],
                     "nearest_falsifiable_precursor": fb["nearest_falsifiable_experiment"],
                     "evidence": [L("greg/path.json", rf'"id": "{re.escape(fb["id"])}"')], "lineage": "both"})
frontier_extra = [
    {"id": "cortex.meta.global_workspace", "destination": "module competition and selective broadcast", "buildability_status": "EXPERIMENTAL_NOW",
     "status": "INVENTORIED", "current_precursor": ["greg/cognition/verification.py metaconsensus"],
     "nearest_falsifiable_precursor": "a broadcast-arbitration arm against the compiler's static ranking on a frozen multi-geometry suite",
     "evidence": [L("greg/cognition/reserved.py", r'"cortex.meta.global_workspace"')], "lineage": "both"},
    {"id": "cortex.meta.active_inference", "destination": "generative-model policy selection", "buildability_status": "EXPERIMENTAL_NOW",
     "status": "INVENTORIED", "current_precursor": ["cognition.sequential (MDP)", "genome:info_experiment"],
     "nearest_falsifiable_precursor": "expected-free-energy policy vs greedy EIG (info_experiment) on its own held-out admission geometry",
     "evidence": [L("greg/cognition/reserved.py", r'"cortex.meta.active_inference"')], "lineage": "both"},
]

# ---------------------------------------------------------------- seed requirement map crosswalk
seed = json.loads((ROOT / "docs/cortex/SEED_GENOME_REQUIREMENTS.json").read_text())
all_items = {i["id"]: i for layer in LAYERS.values() for i in layer[1]}
SEEDMAP = {
    "A00": ["L5.problem_geometry"], "A01": ["L5.loop.recruit_compose"], "A02": ["L1.deterministic_reflexes"],
    "A03": ["L1.eval.bandits", "L5.loop.observe_outcome_credit"], "A04": ["L5.genome_library"], "A04.1": ["L3.semantic"],
    "A05": ["L3.fermi"], "A06": ["L3.bayesian"], "A07": ["L3.causal"], "A08": ["L5.epistemic_vs_authority"],
    "A09": ["L3.or.network_optimization", "L3.con.cpsat"], "A10": ["L3.graph.shortest_path", "L3.search.bnb"],
    "A11": ["L3.ctl.mpc"], "A12": ["L3.info.voi"], "A13": ["L3.cf.decisions_policies"], "A14": ["L3.game.strategic", "L3.mechanism_design"],
    "A15": ["L1.anomaly_response"], "A16": ["L3.evo.program_mutation"], "A17": ["L2.hive_quorum"], "A18": ["L2.ant_stigmergy"],
    "A19": ["L2.flock"], "A20": ["L2.slime_mold"], "A21": ["L2.immune"], "A22": ["L2.ecological"], "A23": ["L2.market"],
    "A24": ["L3.evo.es", "L5.p8_protected_evolution"], "A25": ["L2.human_collective"], "A26": ["L5.loop.independent_first_pass"],
    "A27": ["L4.organ_formation"], "A28": ["L4.constraint_release"], "A29": ["L1.associative_microcircuits"],
    "A30": ["L5.loop.observe_outcome_credit"], "A31": ["L5.cognitive_receipts"], "A32": ["L5.high_risk_rule"], "A33": ["L5.cognitive_receipts"],
    "A34": ["L5.loop.recruit_compose"], "A35": ["L5.genome_library"], "A36": ["L5.loop.dissent"], "A37": ["L5.admission_rule"],
    "A38": ["L5.loop.recruit_compose"], "A39": ["L5.loop.observe_outcome_credit"], "A40": ["L5.p8_protected_evolution"],
    "A41": ["L5.admission_rule"], "A42": ["L5.loop.evaluators_typed_evidence"], "A43": ["L5.interp.collateral_vector"],
    "A44": ["L5.reality_ledger"], "A45": ["L5.epistemic_vs_authority"], "A46": ["L5.buildability"], "A47": ["L5.admission_rule"],
    "A48": ["L5.buildability"], "A49": ["L5.buildability"], "A50": ["L5.metrics_distinct"], "A51": ["L5.buildability"],
    "A52": ["L5.loop.observe_to_geometry", "L5.loop.observe_outcome_credit"], "A53": ["L5.genome_library"],
    "B00": ["L5.problem_geometry"], "B01": ["L5.genome_library"], "B02": ["L5.epistemic_vs_authority"], "B03": ["L1.deterministic_reflexes"],
    "B04": ["L5.genome_library"], "B05": ["L5.genome_library"], "B06": ["L3.con.exact_combinatorial"], "B07": ["L3.con.smt", "L3.formal.model_checking"],
    "B08": ["L3.or.queueing", "L3.or.network_optimization"], "B09": ["L3.graph.mincut_maxflow", "L3.graph.centrality"],
    "B10": ["L3.fermi"], "B11": ["L3.bayesian"], "B12": ["L3.causal"], "B13": ["L3.search.astar", "L3.search.mcts"],
    "B14": ["L3.ctl.feedback", "L3.ctl.robust"], "B15": ["L3.search.tree"], "B16": ["L1.anomaly_response"], "B17": ["L3.info.information_gain"],
    "B18": ["L3.game.strategic", "L3.mechanism_design"], "B19": ["L3.adv.counterexamples"], "B20": ["L3.sim.scenario"],
    "B21": ["L2.hive_quorum", "L2.ant_stigmergy"], "B22": ["L2.ecological", "L2.market"], "B23": ["L3.evo.es"],
    "B24": ["L5.new_intelligence"], "B25": ["L4.constraint_release"], "B26": ["L4.distributed_repair"], "B27": ["L5.loop.recruit_compose"],
    "B28": ["L5.high_risk_rule"], "B29": ["L5.problem_geometry"], "B30": ["L5.loop.dissent"], "B31": ["L5.loop.recruit_compose"],
    "B32": ["L5.epistemic_vs_authority"], "B33": ["L5.loop.observe_outcome_credit"], "B34": ["L5.cognitive_receipts"],
    "B35": ["L5.cognitive_receipts"], "B36": ["L5.interp.deterrence"], "B37": ["L5.interp.victim_protection"],
    "B38": ["L5.interp.collateral_vector"], "B39": ["L5.asymmetric_objective"], "B40": ["L5.genome_library"], "B41": ["L5.reality_ledger"],
    "B42": ["L5.genome_library"], "B43": ["L5.admission_rule"], "B44": ["L5.buildability"], "B45": ["L5.buildability"],
    "B46": ["L4.distributed_repair"], "B47": ["L5.loop.recruit_compose"], "B48": ["L5.genome_library"], "B49": ["L5.metrics_distinct"],
    "B50": ["L5.problem_geometry"], "B51": ["L5.loop.evaluators_typed_evidence"], "B52": ["L5.cognitive_receipts"],
    "B53": ["L5.p4_retest"], "B54": ["L5.genome_library"], "B55": ["L5.p6_composition_gate"], "B56": ["L5.new_intelligence"],
    "B57": ["L5.p8_protected_evolution"], "B58": ["L4.constraint_release"], "B59": ["L4.distributed_repair"],
    "B60": ["L5.epistemic_vs_authority"], "B61": ["L5.buildability"], "B62": ["L5.buildability"], "B63": ["L5.high_risk_rule"],
    "B64": ["L5.genome_library"], "BFIRST": ["L5.cognitive_receipts", "L5.p6_composition_gate"], "BTEST": ["L5.p6_composition_gate"],
}
seed_rows = []
for x in seed["source_crosswalk"]:
    ids = SEEDMAP[x["source_id"]]
    st = min((all_items[i]["status"] for i in ids), key=RANK.get)
    seed_rows.append({"source_id": x["source_id"], "requirement": x["requirement"], "source_location": x["source_location"],
                      "coverage_items": ids, "status": st,
                      "rule": "the weakest status among the mapped coverage items (a requirement is no further along than its weakest part)"})
missing = set(SEEDMAP) ^ {x["source_id"] for x in seed["source_crosswalk"]}
if missing:
    raise SystemExit(f"seed map mismatch: {missing}")

# ---------------------------------------------------------------- counts
def counts(rows):
    c = {s: 0 for s in STATUSES}
    for r in rows:
        c[r["status"]] += 1
    return {k: v for k, v in c.items() if v}

layers_out = {}
for key, (label, rows) in LAYERS.items():
    layers_out[key] = {"source_label": label, "counts": counts(rows), "items": rows}

record = {
    "schema": "mind-coverage/1",
    "title": "GREG Polyintelligence Mind coverage against the founder's source specification",
    "date": "2026-10-21",
    "base_commit": BASE, "compared_lineage": {"pr179_branch": "claude/greg-mind-lineage-convergence", "pr179_head": PR179,
                                               "merge_base": MERGE_BASE},
    "standard": [D7, "docs/intent/sources/POLYINTELLIGENCE-MIND-CONTINUATION-REISSUE-2026-10-13-source.md",
                 "docs/intent/sources/MIND-MAXIMUM-CONTINUATION-2026-10-21-source.md", "docs/cortex/SEED_GENOME_REQUIREMENTS.json"],
    "status_ladder": {
        "ABSENT": "a stated code search found no mechanism; named only by the directive",
        "INVENTORIED": "named in a repository registry, reserved-family record or backcast; nothing executes it",
        "IMPLEMENTED": "executable code exists",
        "INTEGRATED": "reachable through GREG's one cognition path (cognition.reason / the Competency Compiler)",
        "BENCHMARKED": "a frozen evaluation exists (any verdict, including SUPERSEDED, REJECTED, COMPOSITION_ONLY, EXPERIMENTAL)",
        "ADMITTED": "DEFAULT_FOR_GEOMETRY or NICHE_CAPABILITY under the admission rule at its current version",
        "ATTACHED": "founder-attached (none: seed families and cortex organs are attached at registration by code, which is recorded separately)",
        "EXERCISED": "used inside a GREG mission run on the durable mission path with a recorded receipt"},
    "status_rules": [
        "An item's status is the highest status of its direct mechanisms; precursors are listed and never raise it.",
        "Rungs are not cumulative: an EXERCISED organ need not be ADMITTED (none is); a BENCHMARKED genome may have been refuted.",
        "Lineage 'both' means the cited code or evidence exists at the merge base of #158's line and #179; '#158' only on this line; '#179' only on PR #179.",
        "Evidence written git:<sha>:<path>:<line> lives on PR #179's branch and is not in this tree.",
        "mind_status at this commit was run read-only to read every genome's frozen admission; its labels are quoted in notes."],
    "mechanisms": MECH,
    "layers": layers_out,
    "section_31": section31,
    "section_31_counts": {v: sum(1 for s in section31 if s["verdict"] == v) for v in ("MET", "PARTLY_MET", "UNMET")},
    "frontier": frontier + frontier_extra,
    "seed_requirement_crosswalk": seed_rows,
    "seed_requirement_counts": counts(seed_rows),
}
json.dump(record, open(ROOT / "docs/collaboration/MIND-COVERAGE-2026-10-21.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: v["counts"] for k, v in layers_out.items()}, indent=1))
print(record["section_31_counts"], record["seed_requirement_counts"])

# ---------------------------------------------------------------- prioritized build list
E = "greg/cognition/evolution.py"
BUILD = [
 {"rank": 1, "id": "B01.stress_gate_history_audit", "closes": ["31.7", "directive-2026-10-21 section 3"],
  "scope": "Independently re-derive every recorded P8 adversarial-gate decision (cycles 1-6) under the old worsened() and the new stress_worsened(). The cycle records keep only per-set means (e.g. cycle-cr-6.json adversarial: {lean, fewval}: incumbent/candidate means), so the audit must regenerate item-level stress outputs from each cycle's seeded stress sets, frozen configuration and source commit in a clean checkout (stress sets are not held-out data). Finite recorded means imply zero wrong answers in both arms, so the only route to a changed decision is the new both-answered restriction when abstentions occurred; report that case explicitly. Cover paired alignment, equal/fewer errors, empty sets, NaN/inf/malformed values, and the documented rule text. Where regeneration is impossible, record UNRESOLVED, never equivalent.",
  "files": [E, "scripts/audit_stress_gate_history.py (new)", "tests/unit/test_stress_gate_history.py (new)", "docs/evidence/greg-protected-evolution/2026-10-21-stress-gate-audit/ (new)"],
  "acceptance_test": "For each cycle, a row {cycle, regenerated: bool, old_decision, new_decision, wrong_counts, both_answered_n}; the test fails if any row claims equivalence without item-level outputs, and passes hostile cases (3 vs 2 wrong; equal wrong with worse answered mean; empty set; NaN).",
  "falsifier": "Any recorded cycle decision differs under the new function, or a cycle cannot be regenerated (then the 'no recorded decision changes' claim in b7b1ed9 is unsupported for it).",
  "effort": "S-M (0.5-1 day; single core)", "natural_or_synthetic": "re-derivation of recorded synthetic stress sets", "evidence": [L(E, r"^def stress_worsened"), P("docs/evidence/greg-protected-evolution/2026-10-16-cr-6/cycle-cr-6.json", "adversarial")]},
 {"rank": 2, "id": "B02.all_lineage_data_exposure_ledger", "closes": ["31.17", "directive-2026-10-21 section 2"],
  "scope": "One machine-readable ledger of every seed range, data file (sha256), split, pilot, admission, P6 family, P8 cycle and test fixture across #158's tree and PR #179 (read through git show), with the generator code digest that produced each item and whether its outcomes were looked at. Flags: overlapping seeds, the same data file under different seeds (the forecast_quantile/P8 M4 erratum pattern), and the same generator with different seeds (not independent by seed number alone). Read-only; changes no split.",
  "files": ["scripts/data_exposure_ledger.py (new)", "tests/unit/test_data_exposure_ledger.py (new)", "docs/evidence/greg-data-exposure/2026-10-21/ledger.json (new)"],
  "acceptance_test": "Every freeze.json, PREREGISTRATION.md seed declaration, pilot record and admission run in both lineages is parsed (count reported and checked against a glob); #179's seeds 1001-1040, 2001-2040, 3001-3040, 5001-5040 and #158's 1000-1329, 7000-9199 appear; the successor pilot's review seeds are shown unused.",
  "falsifier": "A seed or data item later found used by a committed artifact but missing from the ledger; or two evaluations sharing a data file digest reported as independent.",
  "effort": "M (1 day)", "natural_or_synthetic": "audit of repository artifacts", "evidence": [L(E, r"^def cr_split_seeds|^def immune_split_seeds|P8_RESERVED"), "docs/evidence/greg-genome-admission/2026-10-14-v2/README.md"]},
 {"rank": 3, "id": "B03.successor_immune_pilot", "closes": ["31.7", "directive-2026-10-21 sections 1-2 (authorized option 2)"],
  "scope": "New target identity (e.g. immune_detect_narrow) with explicit lineage to the cycle-7 NOT_VIABLE pilot; the narrowed space is justified causally (the frozen search chose high alarm_fraction configurations that win paired items but add 4-6 false-alarm violations per 540) and its bounds are declared before any new outcome; fresh unused review seeds from the exposure ledger; arms: incumbent, random restart, the strongest simple baseline, and fixed configurations informed by cycle 2's record (labelled as informed); predeclared resource limits, stopping, viability rule, selection rule and multiple-attempt accounting. Shared RULE unchanged. If VIABLE, freeze the trusted implementation and run the confirmatory cycle once; otherwise preserve NOT_VIABLE.",
  "files": [E, "docs/evidence/greg-protected-evolution/2026-10-21-immune-8/ (new: PREREGISTRATION.md, pilot/)", "tests/unit/test_greg_protected_evolution.py"],
  "acceptance_test": "Pilot rules committed before any pilot instance exists (commit order checked by test); verdict computed by the declared rule; reserved cycle-7 seeds untouched.",
  "falsifier": "Pilot NOT_VIABLE (best mean simulated P(RETAIN) below the declared threshold), or a confirmatory REJECT; either is recorded as the result.",
  "effort": "M-L (2-3 days; depends on B01 and B02)", "natural_or_synthetic": "synthetic (seeded negative-selection instances)", "evidence": [P("docs/evidence/greg-protected-evolution/2026-10-21-immune-7/DECISION.md")]},
 {"rank": 4, "id": "B04.evidence_claim_reconciliation_family", "closes": ["31.5", "31.2", "directive-2026-10-21 section 6 (evidence reconciliation)"],
  "scope": "A consequence-inert cognition family drawn from GREG's own operating need: check every numeric claim in evidence READMEs (W-L counts, p-values, percentages, statuses) against the results file it cites, and flag mismatches. Native competitor arms: no-check baseline, regex-extraction-plus-exact-recomputation genome, and (when a local model exists) the semantic organ; composition semantic extract -> exact recompute is the P6 candidate.",
  "files": ["greg/cognition/genomes/evidence_check.py (new)", "greg/cognition/genomes/library.py", "greg/cognition/worlds.py", "cortex/evaluation/claim_reconciliation/ (new prereg, freeze, run)", "tests/unit/test_genomes_evidence_check.py (new)"],
  "acceptance_test": "Pre-registered admission on held-out READMEs (split by directory, decided before reading); recall on the natural positives (claims later corrected by the 26 READMEs that carry errata quoting the original wording) and false-flag rate on claims the recomputation confirms.",
  "falsifier": "The genome misses errata-recorded misstatements at a rate not better than the baseline, or false-flags exceed the declared ceiling.",
  "effort": "M-L (2 days)",
  "natural_or_synthetic": "NATURAL: the README claim population of both lineages and the errata as labelled positives; truth by exact recomputation from the cited JSON. Any injected corruptions are SYNTHETIC and reported separately.",
  "evidence": [P("docs/evidence/greg-composition-lift/2026-10-14-v5/README.md"), P("docs/evidence/greg-genome-admission/2026-10-15-v3/README.md")]},
 {"rank": 5, "id": "B05.repository_dependency_control_points", "closes": ["31.5", "31.8", "directive-2026-10-21 section 6 (dependency analysis, organ coordination)"],
  "scope": "Natural-input problem family: the Python import graph of this repository at K historical commits (git show, no network). Questions: minimum vertex/edge cut between the mission engine and each organ adapter or evidence writer (single points of failure), and the longest dependency chain. Arms: flow_maxflow and critical_path genomes, degree-centrality heuristic baseline, exact networkx truth; P6 candidate: bottleneck detection -> min_cost_flow allocation of a hardening budget.",
  "files": ["cortex/evaluation/dependency_family/ (new: build.py, prereg, freeze, run)", "greg/cognition/worlds.py", "tests/unit/test_dependency_family.py (new)"],
  "acceptance_test": "Instances built only from commits declared before the run; truth independently computed; VPL accounting (false answers, latency, cost) against the strongest single genome.",
  "falsifier": "Composition ties or loses to flow_maxflow alone (the F7 pattern), or the degree heuristic matches the exact cut on most instances.",
  "effort": "M (1-1.5 days)",
  "natural_or_synthetic": "NATURAL inputs (GREG's own repository history), MATHEMATICAL truth computed from each instance; the hardening-budget values are SYNTHETIC unless taken from recorded incident counts.",
  "evidence": [L("greg/cognition/genomes/flow.py", r"solver.graph.max_flow"), L("greg/cognition/genomes/graph_or.py", r"solver.or.critical_path")]},
 {"rank": 6, "id": "B06.exercised_label_and_lineage_rows", "closes": ["31.17", "31.15"],
  "scope": "Extend scripts/mind_status.py with an EXERCISED projection read from retained mission ledgers (cognition receipts with method, version, mission id, key provenance) and lineage-tagged rows for #179's operation-family admissions read from a pinned commit, without merging code or changing routing. Today only the cortex rehearsal (test key) exercises cognition.cortex, extraction.schedule and optimization.cpsat.",
  "files": ["scripts/mind_status.py", "tests/unit/test_mind_status.py"],
  "acceptance_test": "mind_status reports the three exercised organs with the rehearsal ledger as evidence and marks the key as non-founder; #179 rows appear with source commit 0067be6 and never alter the compiler's routing (existing compiler-consistency test still passes).",
  "falsifier": "A mission receipt the ledger scan misses (checked against a grep of retained ledgers), or #179 rows changing a routed status.",
  "effort": "S-M (0.5-1 day)", "natural_or_synthetic": "n/a (records)", "evidence": [L("scripts/mind_status.py", r"Reality ledger"), L(REH, r'"method": "cognition.cortex.optimization.cpsat"')]},
 {"rank": 7, "id": "B07.one_step_weighted_vote_genome", "closes": ["31.8", "L2.human_collective"],
  "scope": "The acquisition target #179's sparse-crowd test named: the one-step agreement-weighted (Nitzan-Paroush) vote as a Layer-2 genome; admit against majority vote and Dawid-Skene on fresh seeds on both dense and sparse crowds.",
  "files": ["greg/cognition/genomes/collective.py", "greg/cognition/genomes/admission.py", "greg/cognition/worlds.py", "tests/unit/test_genomes_collective.py"],
  "acceptance_test": "Pre-registered admission on unused seeds from the exposure ledger; v1 status rule unchanged.",
  "falsifier": "It does not beat majority vote on the sparse geometry, or it ties Dawid-Skene on dense crowds and loses on neither (then COMPOSITION_ONLY/EXPERIMENTAL).",
  "effort": "S-M (1 day)", "natural_or_synthetic": "SYNTHETIC (simulated crowds); the oracle gap 0.197 vs 0.338 states the headroom", "evidence": [G("docs/evidence/pr155-crowd-sparse/2026-10-14/README.md", r"acquisition target")]},
 {"rank": 8, "id": "B08.multistart_lbfgsb_genome", "closes": ["31.2", "L3.opt.nonlinear", "L3.opt.convex"],
  "scope": "Commodity SciPy multistart L-BFGS-B as the nonlinear/smooth black-box genome (#179 measured it beating PSO 32-7 post hoc and DE 26-8); pre-registered admission against PSO and DE, plus a noisy/discontinuous objective menu where gradient-free methods may regain ground.",
  "files": ["greg/cognition/genomes/competitors.py", "greg/cognition/genomes/admission.py", "greg/cognition/worlds.py", "tests/unit/test_genomes_competitors.py"],
  "acceptance_test": "Admission on fresh seeds with the evaluation budget equalised in function evaluations.",
  "falsifier": "It loses to PSO or DE on the declared noisy/discontinuous menu (then NICHE for smooth objectives only).",
  "effort": "S-M (1 day)", "natural_or_synthetic": "MATHEMATICAL instances (declared objectives)", "evidence": [G("docs/evidence/greg-genome-admission/2026-10-14/README-v2.md", r"L-BFGS-B also")]},
 {"rank": 9, "id": "B09.operator_effect_ablation", "closes": ["31.3", "section 6"],
  "scope": "Measure whether each of the 15 typed operators changes a compiled answer, method choice or requirement on a frozen set of compiler requests (existing test geometries plus the P6 families), against the compiler with that operator removed; operators that never alter an answer are recorded as such (the directive: recruit them when the geometry indicates they can alter the answer).",
  "files": ["cortex/evaluation/operator_ablation/ (new)", C, "tests/unit/test_greg_competency_compiler.py"],
  "acceptance_test": "Per operator: count of requests where its removal changes selected method, requirements or result; frozen before running.",
  "falsifier": "An operator with zero effect on every request in its declared signature, which then becomes a rule annotation rather than an operator.",
  "effort": "M (1 day)", "natural_or_synthetic": "mixed: P6 natural families (F6-F8 inputs) and synthetic compiler requests, labelled per request", "evidence": [L(C, r"^OPERATORS = \(")]},
 {"rank": 10, "id": "B10.dynamic_damage_coordinator_loss", "closes": ["31.9", "L4.distributed_repair", "frontier.generalized_morphogenetic_repair"],
  "scope": "The next Layer-4 test both lineages name: damage arriving during transport and loss of the central coordinator, against a central replanner that replans every k ticks; develop_repair and MICA arms on the same seeds; pre-registered, simulated world.",
  "files": ["greg/cognition/genomes/developmental.py", "cortex/evaluation/developmental_dynamic/ (new)", "tests/unit/test_genomes_developmental.py"],
  "acceptance_test": "Pre-registered sign test on delivered throughput across unseen dynamic-damage seeds; ties reported as PARITY.",
  "falsifier": "PARITY or loss against the periodic replanner (then the distributed mechanism has no measured advantage beyond coordinator independence).",
  "effort": "M (1-2 days)", "natural_or_synthetic": "SYNTHETIC (simulated lattices)", "evidence": [G("docs/evidence/greg-developmental-sweep/2026-10-14/README.md", r"Next falsifiable Layer 4 test")]},
 {"rank": 11, "id": "B11.ci_sharding_family", "closes": ["31.5", "directive-2026-10-21 section 6 (planning, resource allocation)"],
  "scope": "Record per-test durations once from a local single-core run of this repository's suite (consequence-inert), then build makespan instances (k CI workers) from them; arms: CP-SAT (the exercised organ), LPT greedy practitioner, knapsack/BnB-based bin assignment; truth: proven CP-SAT optimum. Relevant to the real CI limit raised to 45 minutes.",
  "files": ["cortex/evaluation/ci_sharding/ (new)", "cortex/evaluation/data/ci_durations.json.gz (new, recorded locally)", "greg/cognition/worlds.py"],
  "acceptance_test": "Pre-registered: instances drawn from recorded durations with k declared; certificate of optimality per item.",
  "falsifier": "LPT within 1% of optimal on nearly every instance (no lift worth the latency).",
  "effort": "M (1 day plus one full-suite recording run, which exceeds light compute and must be scheduled)",
  "natural_or_synthetic": "NATURAL inputs (GREG's own test durations), MATHEMATICAL truth", "evidence": [L(".github/workflows/canonical-ci.yml", r"timeout-minutes: 45")]},
 {"rank": 12, "id": "B12.centrality_community_genomes", "closes": ["31.2", "L3.graph.centrality", "L3.graph.community_topology"],
  "scope": "NetworkX betweenness/approximate centrality and modularity community detection as genomes, admitted only where decision-relevant: on SNDlib topologies and B05's import graphs, does centrality predict the exact min-cut control points better than degree?",
  "files": ["greg/cognition/genomes/graph_or.py", "greg/cognition/genomes/admission.py", "greg/cognition/worlds.py"],
  "acceptance_test": "Pre-registered admission against degree and against the exact cut.",
  "falsifier": "Centrality never beats degree at identifying exact cut vertices (then REJECTED: not decision-relevant).",
  "effort": "S-M (1 day)", "natural_or_synthetic": "NATURAL inputs (SNDlib, repository graphs), MATHEMATICAL truth", "evidence": [P("cortex/evaluation/data/sndlib_networks.json.gz")]},
]
record["prioritized_build_list"] = BUILD
record["build_list_scope"] = ("buildable now with no RULE change, no attachment, no data-rights clearance, no network "
                              "evasion and no spending; ranked by information value and by relevance to GREG's real "
                              "capability deficits")
record["section_6_candidates"] = [b["id"] for b in BUILD if b["id"] in ("B04.evidence_claim_reconciliation_family",
                                   "B05.repository_dependency_control_points", "B11.ci_sharding_family")]
record["section_6_rejected_candidates"] = [
    {"task": "forecasting GREG's own commit or evidence arrivals", "reason": "28 active commit days (2026-07-19 to 2026-10-21): too short for a held-out forecasting family"},
    {"task": "organ coordination over greg/path.json nodes", "reason": "11 nodes: too few instances for a held-out family"},
    {"task": "recovery from retained mission ledgers", "reason": "a handful of recovery episodes in tests/evidence/greg-usable/retained-state; record and wait for more body history"}]
json.dump(record, open(ROOT / "docs/collaboration/MIND-COVERAGE-2026-10-21.json", "w"), indent=1, ensure_ascii=False)
print("build list", len(BUILD))

# ---------------------------------------------------------------- readable record
R = ROOT
d = json.loads((R / "docs/collaboration/MIND-COVERAGE-2026-10-21.json").read_text())
ORDER = ["ABSENT", "INVENTORIED", "IMPLEMENTED", "INTEGRATED", "BENCHMARKED", "ADMITTED", "ATTACHED", "EXERCISED"]
o = []
w = o.append
w("# GREG Mind coverage against the founder's specification, 2026-10-21\n")
w(f"Base commit `{d['base_commit']}` (#158's line). Compared with PR #179 (`{d['compared_lineage']['pr179_branch']}` at "
  f"`{d['compared_lineage']['pr179_head']}`, merge base `{d['compared_lineage']['merge_base']}`). Machine-readable record: "
  "[`MIND-COVERAGE-2026-10-21.json`](MIND-COVERAGE-2026-10-21.json). Checked by `tests/unit/test_mind_coverage_record.py`.\n")
w("The standard is the founder's text, not a summary of it:\n")
for s in d["standard"]:
    w(f"- `{s}`")
w("\nThis record changes no code, routing, rule or authority. It attaches nothing.\n")
w("## Status ladder\n")
w("Each requirement gets one highest-attained status, backed by a file:line or an evidence path.\n")
w("| Status | Meaning |\n|---|---|")
for k in ORDER:
    w(f"| {k} | {d['status_ladder'][k]} |")
w("")
for r in d["status_rules"]:
    w(f"- {r}")
w("\n**ATTACHED is empty.** Seed families (micro, exact, estimation, formal, optimization, causal, evidence, semantic) and the cortex organs are attached at registration by `catalog.initial_state`. No founder CAPABILITY_ATTACH exists for any genome.\n")
w("**EXERCISED is narrow.** One recorded body mission uses cognition: `m:cortex-rehearsal` (2026-10-01, `tests/evidence/greg-cortex-rehearsal/`). It ran the cortex router, schedule extraction and CP-SAT through kill -9, restart, approval and one settlement. It used a per-test key, not Alfonso's, on a Linux container. No genome has run inside a recorded mission.\n")
w("## Counts by layer\n")
w("| Layer (source label) | " + " | ".join(ORDER) + " | items |")
w("|---|" + "---:|" * (len(ORDER) + 1))
for k, v in d["layers"].items():
    c = v["counts"]
    w(f"| {k}: {v['source_label']} | " + " | ".join(str(c.get(s, "")) for s in ORDER) + f" | {len(v['items'])} |")
w("")
w("Where the two lineages differ, the item's `lineage` names the one that holds its status. #179 alone holds "
  "ADMITTED for nine items, all through its operation-family admission v3: deterministic reflexes, rule-based "
  "classification, flock (PSO beats random search only), human collective (Dawid-Skene, dense crowds only), "
  "nonlinear optimisation, dynamic programming, decision analysis, tree search and value of information. On #158 "
  "those operation families have no frozen row, so `mind_status` labels them BUILT.\n")
w("## Section 31: the 17 conditions\n")
w(f"Met {d['section_31_counts']['MET']}, partly met {d['section_31_counts']['PARTLY_MET']}, unmet {d['section_31_counts']['UNMET']}.\n")
w("| # | Condition (verbatim) | Verdict | Attained | Remaining gap |\n|---:|---|---|---|---|")
for s in d["section_31"]:
    w(f"| {s['n']} | {s['condition']} | **{s['verdict']}** | {s['attained']} | {s['remaining_gap']} |")
w("")

def short(ev):
    return "<br>".join(f"`{e}`" for e in ev[:3])

for k, v in d["layers"].items():
    w(f"## Layer {k}: {v['source_label']}\n")
    w("| Requirement | Status | Lineage | Mechanisms | Evidence | Note / search |\n|---|---|---|---|---|---|")
    for i in v["items"]:
        note = i["note"]
        if i.get("search"):
            note = (note + " " if note else "") + "Search: " + i["search"]
        if i["precursors"]:
            note += (" " if note else "") + "Precursors: " + ", ".join(i["precursors"]) + "."
        if i["status_on_158"] != i["status_on_179"] and i["mechanisms"]:
            note += f" (#158: {i['status_on_158']}; #179: {i['status_on_179']})"
        w(f"| {i['requirement']} | {i['status']} | {i['lineage']} | {', '.join(i['mechanisms'])} | {short(i['evidence'])} | {note} |")
    w("")
w("## Frontier destinations\n")
w("All are preserved; none is claimed to exist.\n")
w("| Destination | Buildability | Nearest falsifiable precursor |\n|---|---|---|")
for f in d["frontier"]:
    w(f"| `{f['id']}`: {f['destination']} | {f['buildability_status']} | {f['nearest_falsifiable_precursor']} |")
w("")
w("## Prioritized build list\n")
w(d["build_list_scope"] + ".\n")
for b in d["prioritized_build_list"]:
    w(f"### {b['rank']}. `{b['id']}`\n")
    w(f"- **Closes:** {', '.join(b['closes'])}")
    w(f"- **Scope:** {b['scope']}")
    w(f"- **Files:** " + ", ".join(f"`{x}`" for x in b["files"]))
    w(f"- **Acceptance test:** {b['acceptance_test']}")
    w(f"- **Falsifier:** {b['falsifier']}")
    w(f"- **Effort:** {b['effort']}")
    w(f"- **Evidence kind:** {b['natural_or_synthetic']}\n")
w("### Section 6 candidates considered and set aside\n")
for r in d["section_6_rejected_candidates"]:
    w(f"- {r['task']}: {r['reason']}.")
w("")
w("## Seed-genome requirement crosswalk\n")
w("Each of the 122 crosswalk items in `docs/cortex/SEED_GENOME_REQUIREMENTS.json` is mapped to coverage items. Its "
  "status is the weakest status among them. Counts: " + ", ".join(f"{k} {v}" for k, v in d["seed_requirement_counts"].items()) + ".\n")
w("| Source id | Requirement | Coverage items | Status |\n|---|---|---|---|")
for s in d["seed_requirement_crosswalk"]:
    w(f"| {s['source_id']} | {s['requirement']} | {', '.join(s['coverage_items'])} | {s['status']} |")
w("")
w("## Unavailable context\n")
w("- Project sources outside the repository (raw ChatGPT conversations) were not inspected.")
w("- Organ repositories (DALEOBANKS, WealthMachineIntelligence) were not inspected for cognition consumers. Section 31 item 15 records that no organ consumption is evidenced in this repository.")
w("- PR #179 was read at `0067be6` through `git show` only, and none of its runs were re-executed. `mind_status` was run once, read-only, at the base commit.")
(R / "docs/collaboration/MIND-COVERAGE-2026-10-21.md").write_text("\n".join(o) + "\n")
print(len(o))
