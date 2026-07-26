"""Core-versus-Venture boundary — the authoritative test.

    UNIIMENTE may create and govern ventures. No venture may define UNIIMENTE.

WHY THIS IS NOT A TOKEN BLACKLIST. Scanning core paths for venture names is too
crude: it either fails on legitimate references (a legal-principal registry MUST
name real entities; a historical record MUST preserve what past work was called)
or it accumulates exceptions until the allowlist means nothing. A growing
allowlist is a lint that has stopped working.

So the authoritative rules below are path-aware and dependency-aware. A token
scan is retained at the end as an ADVISORY diagnostic only — it reports, it does
not fail the build.
"""

import ast
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CORE_PACKAGES = [
    "constitution", "authority", "identity", "policy", "events", "provenance",
    "memory", "capabilities", "autonomy", "embassy", "affect", "capital",
    "compiler", "loom", "twins", "evolution", "closure", "linker", "organs",
    "morphogenesis", "sandbox", "observability",
]
VENTURES_DIR = "ventures"
DEVELOPMENTAL = "developmental"

# Core interfaces a Venture Cell is permitted to import. Anything outside this
# set means a venture reached for machinery it was not offered.
APPROVED_CORE_INTERFACES_FOR_VENTURES = {
    "morphogenesis",   # contracts + engine: declare a target, never execute
    "closure",         # generic fixture builders
    "contracts",
}

# Rule 7 — a Venture Cell may not define or override any of these.
AUTHORITY_ARTIFACTS = [
    "constitution.ucl", "authority-matrix.yaml", "legal-principals.yaml",
    "organ-registry.yaml", "agent-registry.yaml", "consequence_gate.py",
    "shutdown-policy.ucl", "sovereignty.ucl", "amendment-policy.ucl",
]


def _py_files(rel_dir):
    base = os.path.join(ROOT, rel_dir)
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in {"__pycache__", ".git"}]
        out.extend(
            os.path.join(dirpath, f) for f in filenames if f.endswith(".py")
        )
    return out


def _top_level_imports(path):
    with open(path) as handle:
        tree = ast.parse(handle.read(), filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and not node.level:
                names.add(node.module.split(".")[0])
    return names


# --------------------------------------------------------------------------
# Rule 1 — core modules may not import from ventures/
# --------------------------------------------------------------------------

def test_rule1_core_does_not_import_from_ventures():
    offenders = []
    for package in CORE_PACKAGES + [DEVELOPMENTAL]:
        if not os.path.isdir(os.path.join(ROOT, package)):
            continue
        for path in _py_files(package):
            if VENTURES_DIR in _top_level_imports(path):
                offenders.append(os.path.relpath(path, ROOT))
    assert not offenders, f"core modules import from ventures/: {offenders}"


# --------------------------------------------------------------------------
# Rule 2 — ventures may import only approved core interfaces
# --------------------------------------------------------------------------

def test_rule2_ventures_import_only_approved_core_interfaces():
    if not os.path.isdir(os.path.join(ROOT, VENTURES_DIR)):
        return
    all_core = set(CORE_PACKAGES) | {DEVELOPMENTAL}
    offenders = []
    for path in _py_files(VENTURES_DIR):
        reached = _top_level_imports(path) & all_core
        unapproved = reached - APPROVED_CORE_INTERFACES_FOR_VENTURES
        if unapproved:
            offenders.append((os.path.relpath(path, ROOT), sorted(unapproved)))
    assert not offenders, f"ventures reached unapproved core machinery: {offenders}"


# --------------------------------------------------------------------------
# Rule 3 — core fixtures may not carry venture-domain defaults
# --------------------------------------------------------------------------

def test_rule3_core_fixture_builders_require_explicit_legal_party():
    """A core fixture must never silently choose who is accountable.

    Checked structurally: the generic builders expose the legal party as a
    keyword-only argument with NO default.
    """
    from closure import advantage_registry

    source = os.path.join(ROOT, "closure", "advantage_registry.py")
    with open(source) as handle:
        tree = ast.parse(handle.read())

    expected = {
        "build_opportunity": "legal_operator",
        "build_composition_request": "legal_principal",
    }
    for func_name, arg_name in expected.items():
        node = next(
            (n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == func_name),
            None,
        )
        assert node is not None, f"{func_name} missing from core fixture builders"
        kwonly = [a.arg for a in node.args.kwonlyargs]
        assert arg_name in kwonly, f"{func_name}: {arg_name} must be keyword-only"
        index = kwonly.index(arg_name)
        assert node.args.kw_defaults[index] is None, (
            f"{func_name}: {arg_name} must have NO default — a fixture may not "
            f"silently select an accountable party"
        )
    assert hasattr(advantage_registry, "build_opportunity")


def test_rule3_core_fixture_defaults_are_domain_neutral():
    """The generic builder's own defaults must not name a specific industry."""
    from closure.advantage_registry import build_opportunity

    spec = build_opportunity(legal_operator="alfonso_lopez")
    domain_terms = ("patient", "facility", "hospital", "discharge", "clinical",
                    "payer-grade", "case management")
    for field in ("buyer", "beneficiary", "pain_owner", "budget_owner",
                  "mandate_actor", "recurring_transaction", "broken_state"):
        value = str(getattr(spec, field, "")).lower()
        hits = [t for t in domain_terms if t in value]
        assert not hits, f"core fixture default {field}={value!r} carries {hits}"


# --------------------------------------------------------------------------
# Rule 4 — core manifests reference ventures only through explicit registries
# --------------------------------------------------------------------------

def test_rule4_manifest_venture_reference_resolves_in_a_registry():
    import yaml

    manifest = yaml.safe_load(
        open(os.path.join(ROOT, "integration", "egregore-v1.yaml"))
    )
    registry = yaml.safe_load(
        open(os.path.join(ROOT, "identity", "organ-registry.yaml"))
    )
    known = set((registry.get("organs") or registry or {}).keys())

    for name, entry in (manifest.get("canonical_functions") or {}).items():
        if not isinstance(entry, dict):
            continue
        delegate = entry.get("delegated_to")
        if delegate is not None:
            assert delegate in known, (
                f"canonical_functions.{name}.delegated_to={delegate!r} does not "
                f"resolve in identity/organ-registry.yaml"
            )
            assert "delegation_active" in entry, (
                f"canonical_functions.{name} delegates without stating "
                f"delegation_active"
            )


# --------------------------------------------------------------------------
# Rule 7 — no Venture Cell may define or override authority
# --------------------------------------------------------------------------

def test_rule7_ventures_define_no_authority_artifacts():
    base = os.path.join(ROOT, VENTURES_DIR)
    if not os.path.isdir(base):
        return
    offenders = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in filenames:
            if filename in AUTHORITY_ARTIFACTS:
                offenders.append(os.path.relpath(os.path.join(dirpath, filename), ROOT))
    assert not offenders, f"Venture Cell defines authority artifacts: {offenders}"


def test_rule7_ventures_are_inactive_and_unattached_by_default():
    from ventures.ivio_nemt import ACTIVE, ATTACHED

    assert ACTIVE is False, "Venture Cell must be inactive by default"
    assert ATTACHED is False, "Venture Cell must be unattached by default"


# --------------------------------------------------------------------------
# Rules 5 and 6 — legitimate venture names that must NOT be flagged
# --------------------------------------------------------------------------

def test_rule5_legal_principal_registry_may_name_real_entities():
    import yaml

    principals = yaml.safe_load(
        open(os.path.join(ROOT, "authority", "legal-principals.yaml"))
    )["principals"]
    assert "IVIO_NEMT_LLC" in principals, (
        "the legal-principal registry must be able to name real entities; "
        "removing them would break the gate"
    )
    assert principals["UNIIMENTE"]["status"] == "prohibited"


def test_rule6_historical_records_preserve_venture_names():
    """The protected historical block must still contain its original venture
    references, and must match the hash recorded before Package 2."""
    import hashlib

    path = os.path.join(ROOT, "integration", "egregore-v1.yaml")
    lines = open(path).read().splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if l.startswith("source_prs:"))
    end = next(i for i, l in enumerate(lines) if l.startswith("implementation_classes:"))
    block = "".join(lines[start:end])

    assert "ivio_first_cell" in block, (
        "historical record was scrubbed of venture names — that falsifies provenance"
    )

    recorded = open(
        os.path.join(ROOT, "docs", "release", "package-2", "PROTECTED_RECORD_HASH.txt")
    ).read().split()[0]
    actual = hashlib.sha256(block.encode()).hexdigest()
    assert actual == recorded, (
        f"protected historical record changed.\n  recorded {recorded}\n  actual   {actual}"
    )


# --------------------------------------------------------------------------
# ADVISORY ONLY — reports, never fails
# --------------------------------------------------------------------------

def test_advisory_token_scan_reports_without_failing(capsys):
    """Diagnostic. Deliberately cannot fail the build.

    A token blacklist is not the boundary — the rules above are. This exists so
    a human can see where venture vocabulary appears, and decide.
    """
    terms = ("ivio", "nemt", "pumpstation", "tgh", "patient", "facility",
             "hospital", "discharge")
    findings = []
    for package in CORE_PACKAGES:
        directory = os.path.join(ROOT, package)
        if not os.path.isdir(directory):
            continue
        result = subprocess.run(
            ["grep", "-rilE", "--exclude-dir=__pycache__", "--include=*.py",
             "--include=*.yaml", "--include=*.ucl", "|".join(terms), directory],
            capture_output=True, text=True,
        )
        findings.extend(
            os.path.relpath(p, ROOT) for p in result.stdout.split() if p
        )
    if findings:
        print("\nADVISORY — venture vocabulary in core paths (not a failure):")
        for item in sorted(set(findings)):
            print(f"  {item}")
    assert True


# --------------------------------------------------------------------------
# Venture removal — the core must stand alone
# --------------------------------------------------------------------------

def _core_invariant_fingerprint():
    """Hash the artifacts that define UNIIMENTE's identity and authority."""
    import hashlib

    artifacts = [
        "constitution/constitution.ucl", "constitution/sovereignty.ucl",
        "constitution/shutdown-policy.ucl", "constitution/amendment-policy.ucl",
        "constitution/participant-rights.ucl",
        "authority/authority-matrix.yaml", "authority/legal-principals.yaml",
        "authority/reserved-matters.yaml",
        "identity/organ-registry.yaml", "identity/agent-registry.yaml",
        "identity/service-identities.yaml",
        "policy/consequence_gate.py",
    ]
    digest = hashlib.sha256()
    for rel in artifacts:
        with open(os.path.join(ROOT, rel), "rb") as handle:
            digest.update(handle.read())
    return digest.hexdigest()


def test_core_operates_with_zero_venture_cells_attached():
    """Core loads, the gate decides, and the verifier passes with ventures/
    entirely absent from sys.path — proved in a child process so the parent's
    already-imported modules cannot mask a dependency."""
    script = (
        "import sys, os, shutil, tempfile\n"
        f"src = {ROOT!r}\n"
        "tmp = tempfile.mkdtemp()\n"
        "dst = os.path.join(tmp, 'core')\n"
        "shutil.copytree(src, dst, ignore=shutil.ignore_patterns("
        "'ventures', '.git', '__pycache__', 'node_modules'))\n"
        "assert not os.path.exists(os.path.join(dst, 'ventures'))\n"
        "sys.path.insert(0, dst); os.chdir(dst)\n"
        "import policy.consequence_gate, identity.machine_passport\n"
        "import compiler.ucl_compiler, provenance, memory, events\n"
        "from developmental.cdpe import DevelopmentalProgramExecutor\n"
        "rep = DevelopmentalProgramExecutor().run()\n"
        "d = rep if isinstance(rep, dict) else rep.__dict__\n"
        "assert d['external_effects'] == 0\n"
        "print('CORE_OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=900
    )
    assert "CORE_OK" in proc.stdout, (
        f"core failed with zero Venture Cells attached (rc={proc.returncode}):\n"
        f"{proc.stderr[-1500:]}"
    )


def test_removing_ventures_alters_no_core_invariant():
    """Constitution, authority matrix, legal principals, identity registries and
    the Consequence Gate are byte-identical whether or not ventures/ exists."""
    import hashlib
    import shutil
    import tempfile

    before = _core_invariant_fingerprint()

    tmp = tempfile.mkdtemp()
    dst = os.path.join(tmp, "core")
    shutil.copytree(
        ROOT, dst,
        ignore=shutil.ignore_patterns("ventures", ".git", "__pycache__", "node_modules"),
    )
    assert not os.path.exists(os.path.join(dst, "ventures"))

    digest = hashlib.sha256()
    for rel in [
        "constitution/constitution.ucl", "constitution/sovereignty.ucl",
        "constitution/shutdown-policy.ucl", "constitution/amendment-policy.ucl",
        "constitution/participant-rights.ucl",
        "authority/authority-matrix.yaml", "authority/legal-principals.yaml",
        "authority/reserved-matters.yaml",
        "identity/organ-registry.yaml", "identity/agent-registry.yaml",
        "identity/service-identities.yaml",
        "policy/consequence_gate.py",
    ]:
        with open(os.path.join(dst, rel), "rb") as handle:
            digest.update(handle.read())

    assert digest.hexdigest() == before, (
        "removing ventures/ changed a core invariant artifact"
    )
    shutil.rmtree(tmp, ignore_errors=True)
