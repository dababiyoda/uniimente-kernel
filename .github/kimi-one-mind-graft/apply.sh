#!/usr/bin/env bash
# One-shot scripted graft: reconcile the cortex 0.4.0 line (T) onto the
# execution fabric (B) as one Mind surface (INTENT-0037).
#
# Every step is deterministic and asserted; the resulting tree is
# byte-identical to the locally built and tested reconciliation tree.
# Fail-closed: any assertion failure aborts before commit.
#
# This script and .github/workflows/kimi-one-mind-graft.yml persist in the
# final tree as the auditable record of how the graft commit was produced.
# The workflow triggers only on pushes that modify THIS file; the bot's own
# graft commit never touches it, so it cannot retrigger.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

B=1aab4132fa4cb4064a01d5c02613b930467fbee3   # execution-fabric base (#148 head)
T=3f61cfc48a45f9aa642ae527827b0c419d7bb67d   # cortex 0.4.0 line graft source

# Idempotency guard: selector.py exists only after a completed graft.
if [ -f greg/cognition/selector.py ]; then
  echo "graft already applied; nothing to do"
  exit 0
fi

git cat-file -e "$B^{commit}"
git cat-file -e "$T^{commit}"

# --- 1) 155 files taken byte-verbatim from the cortex line -------------------
cat > /tmp/checkout_T.txt <<'PATHS'
contracts/cortex-intelligence-genome.schema.json
contracts/cortex-problem-geometry.schema.json
contracts/cortex-proof-artifact.schema.json
contracts/cortex-receipt.schema.json
cortex/contracts.py
cortex/evaluation/crossgeo.py
cortex/evaluation/crossgeo_arms.py
cortex/evaluation/crossgeo_loss.py
cortex/evaluation/crossgeo_suite.py
cortex/evaluation/freeze-crossgeo-v0.2.json
cortex/evaluation/freeze-crossgeo-v0.3.json
cortex/evaluation/freeze-v0.2.0.json
cortex/evaluation/freeze-v0.2.1.json
cortex/evaluation/freeze-v0.3.0.json
cortex/evaluation/freeze-v0.4.0.json
cortex/evaluation/run.py
cortex/evaluation/suites/crossgeo-adversarial-v0.2.json
cortex/evaluation/suites/crossgeo-adversarial-v0.3.json
cortex/evaluation/suites/crossgeo-dev-v0.2.json
cortex/evaluation/suites/crossgeo-heldout-v0.2.json
cortex/evaluation/suites/crossgeo-heldout-v0.3.json
cortex/evaluation/suites/crossgeo-selection-v0.2.json
cortex/examples.py
cortex/genome.py
cortex/organs/adversarial.py
cortex/organs/continuous.py
cortex/organs/cpsat.py
cortex/organs/formal.py
cortex/organs/formal_eval.py
cortex/organs/formed.py
cortex/organs/graphsearch.py
cortex/organs/schedule_extraction.py
cortex/outcomes.py
cortex/routing.py
docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json
docs/collaboration/deliberation-cortex-formed-routing-20261002.json
docs/collaboration/deliberation-greg-seed-genome-20261001.json
docs/collaboration/deliberation-npart-composition-20261003.json
docs/collaboration/intent-records-kimi-0035.json
docs/collaboration/intent-records-kimi-0036.json
docs/collaboration/intents-greg-seed-genome-20261001.json
docs/collaboration/requirements-greg-seed-genome-20261001.json
docs/cortex/BACKCAST_GPS_CORTEX.md
docs/cortex/BACKCAST_GPS_FULL_MIND_2026-10-01.md
docs/cortex/BUILD_PROMPT_TRACEABILITY.json
docs/cortex/GREG_SEED_GENOME_REPORT.md
docs/cortex/INVENTION_DOSSIER.md
docs/cortex/SPIDER_WEB_CORTEX.md
docs/cortex/dependency-partition-2026-10-03.json
docs/cortex/examples/INDEX.json
docs/cortex/examples/proof-causal_estimate.json
docs/cortex/examples/proof-extraction.json
docs/cortex/examples/proof-optimization.json
docs/cortex/examples/receipt-causal-identified.json
docs/cortex/examples/receipt-causal-unmeasured-confounding.json
docs/cortex/examples/receipt-deterrence-external-handoff.json
docs/cortex/examples/receipt-deterrence-internal-control.json
docs/cortex/examples/receipt-estimate-dependent-inputs.json
docs/cortex/examples/receipt-formal-optimize-certified.json
docs/cortex/examples/receipt-formal-recommend.json
docs/cortex/examples/receipt-gates-incomparable.json
docs/cortex/examples/receipt-legal-handoff.json
docs/cortex/examples/receipt-schedule-composition.json
docs/cortex/examples/receipt-semantic-model-unavailable.json
docs/cortex/examples/receipt-victim-protection-handoff.json
docs/cortex/examples/routing-memory-verified-success.json
docs/cortex/verbatim-register.json
docs/decisions/ADR-20261001-greg-seed-genome.md
docs/intent/INTENT-20261001-greg-seed-genome.json
docs/intent/sources/GREG-SEED-GENOME-DIRECTIVE-2026-10-01-source.md
examples/cognition/frozen-suite.json
examples/cognition/request.json
greg/cognition/README.md
greg/cognition/benchmark.py
greg/cognition/bridge.py
greg/cognition/catalog.py
greg/cognition/cells.py
greg/cognition/contracts.py
greg/cognition/cortex.py
greg/cognition/linear.py
greg/cognition/network.py
greg/cognition/protection.py
greg/cognition/settlement.py
greg/cognition/solvers.py
greg/cognition/verification.py
greg/cognition/worker.py
greg/genesis.py
greg/mechanisms.py
requirements-cognition.txt
requirements-cortex.txt
scripts/ci/check_cortex_mutants.py
scripts/qualify_open_source_engines.py
tests/evidence/cognition-2026-09-30/authority.log
tests/evidence/cognition-2026-09-30/benchmark.log
tests/evidence/cognition-2026-09-30/full-suite.log
tests/evidence/cognition-2026-09-30/schema-refs.log
tests/evidence/cognition-2026-09-30/sealed.log
tests/evidence/cognition-2026-09-30/verification.json
tests/evidence/cortex-mutants-2026-10-01/run1-two-survivors.log
tests/evidence/cortex-mutants-2026-10-01/run2-after-fixes.log
tests/evidence/cortex-mutants-2026-10-01/run3-v0.2.1.log
tests/evidence/cortex-seed-v0.2.0/heldout-results.json
tests/evidence/cortex-seed-v0.2.0/smoke-results.json
tests/evidence/cortex-seed-v0.2.1/heldout-results.json
tests/evidence/cortex-seed-v0.2.1/smoke-results.json
tests/evidence/greg-body1-engines-2026-10-01/README.md
tests/evidence/greg-cortex-rehearsal/rehearsal-ledger.jsonl
tests/evidence/greg-cortex-rehearsal/rehearsal-summary.json
tests/evidence/greg-crossgeo-v0.2/results.json
tests/evidence/greg-crossgeo-v0.2/selection-results.json
tests/evidence/greg-crossgeo-v0.3/results.json
tests/evidence/greg-crossgeo-v0.3/selection-results.json
tests/evidence/greg-open-source-genesis-2026-10-01/README.md
tests/evidence/greg-open-source-genesis-2026-10-01/mutants.log
tests/evidence/greg-open-source-genesis-2026-10-01/qualification.json
tests/integration/test_greg_cognition_mission.py
tests/integration/test_greg_cortex_mission.py
tests/integration/test_greg_cortex_rehearsal.py
tests/unit/test_cortex_crossgeo.py
tests/unit/test_cortex_formal_engines.py
tests/unit/test_cortex_formed_organs.py
tests/unit/test_cortex_gates_genome.py
tests/unit/test_cortex_npart_composition.py
tests/unit/test_cortex_schedule_composition.py
tests/unit/test_greg_cognition.py
tests/unit/test_greg_cortex_bridge.py
tests/unit/test_greg_linear_genesis.py
tests/unit/test_greg_open_source_genesis.py
tests/unit/test_greg_schedule_words.py
tests/unit/test_greg_seed_genome_records.py
verifier/README.md
verifier/runs/collab-2026-10-02T12-09-01.379595+00-00.json
verifier/runs/collab-2026-10-02T16-44-14.416873+00-00.json
verifier/runs/manual-2026-10-02T11-21-00.000000+00-00.json
verifier/runs/manual-2026-10-02T11-33-00.000000+00-00.json
verifier/runs/manual-2026-10-02T11-37-27.828184+00-00.json
verifier/runs/manual-2026-10-02T11-43-00.000000+00-00.json
verifier/runs/manual-2026-10-02T11-54-13.885857+00-00.json
verifier/runs/remote-replication-2026-10-02T22-28-45.826879+00-00.json
verifier/runs/replication-2026-10-02T15-15-11.751854+00-00.json
verifier/runs/replication-2026-10-02T15-38-28.701715+00-00.json
verifier/runs/replication-2026-10-02T15-48-19.481605+00-00.json
verifier/runs/replication-2026-10-02T18-46-56.430310+00-00.json
verifier/runs/replication-2026-10-02T19-03-17.030444+00-00.json
verifier/runs/v2-2026-10-01T15-22-47.848453+00-00.json
verifier/runs/v2-2026-10-01T19-23-19.066968+00-00.json
verifier/runs/v3-2026-10-02T12-07-23.096152+00-00.json
verifier/runs/v4-2026-10-02T17-35-32.175540+00-00.json
verifier/runs/v4-2026-10-02T19-12-38.635782+00-00.json
verifier/runs/v4-2026-10-02T22-11-55.982277+00-00.json
verifier/runs/v4-2026-10-02T22-24-16.849187+00-00.json
verifier/v3/criteria.json
verifier/v3/verify.py
verifier/v4/criteria.json
verifier/v4/verify.py
PATHS
xargs -a /tmp/checkout_T.txt -d '\n' -n 25 git checkout "$T" --

# T-parent files that receive scripted edits below.
git checkout "$T" -- \
  docs/cortex/README.md \
  docs/cortex/SEED_EXPERIMENT_REPORT.md \
  docs/FOUNDER_INTENT_LEDGER.md \
  docs/PROJECT_COGNITION_CONTINUITY.md

# --- 2) selector rename: the fabric's deterministic selector, verbatim -------
mkdir -p greg/cognition
git show "$B:greg/cognition.py" > greg/cognition/selector.py
git rm -q greg/cognition.py
git show "$B:tests/unit/test_greg_cognition.py" > tests/unit/test_greg_cognition_selector.py

# --- 3) authored records from the payload (before any tree walk) -------------
test -d .github/kimi-one-mind-graft/payload
cp -r .github/kimi-one-mind-graft/payload/. .
for f in \
  docs/collaboration/deliberation-one-mind-surface-20261003.json \
  docs/collaboration/intent-records-kimi-0037.json \
  docs/cortex/ONE_MIND_SURFACE_RECONCILIATION_2026-10-03.md \
  greg/cognition/__init__.py \
  "verifier/runs/v4-2026-10-03T12-56-35.629229+00-00.json"; do
  test -f "$f" || { echo "payload copy missing: $f"; exit 1; }
done
rm -rf .github/kimi-one-mind-graft/payload

# --- 4) anchored in-place edits (each anchor asserted unique) ----------------
python3 - <<'PYEOF'
import json, sys

with open('.github/kimi-one-mind-graft/data/edits.json') as f:
    EDITS = json.load(f)

def apply(path, spec):
    with open(path) as f:
        txt = f.read()
    if 'replace_all' in spec:
        old, new, cnt = spec['replace_all']
        c = txt.count(old)
        if c != cnt:
            sys.exit(f'{path}: replace_all anchor count {c} != {cnt}')
        txt = txt.replace(old, new)
    else:
        for old, new in spec['ops']:
            c = txt.count(old)
            if c != 1:
                sys.exit(f'{path}: anchor count {c} != 1 for {old[:70]!r}')
            txt = txt.replace(old, new, 1)
    with open(path, 'w') as f:
        f.write(txt)

for path, spec in EDITS.items():
    apply(path, spec)
print('anchored edits applied:', len(EDITS))
PYEOF

# --- 5) greg/path.json: union the cortex line's workstreams key --------------
git show "$T:greg/path.json" > /tmp/t_path.json
python3 - <<'PYEOF'
import json
with open('greg/path.json') as f:
    b = json.load(f)
with open('/tmp/t_path.json') as f:
    t = json.load(f)
assert 'workstreams' not in b, 'workstreams already present'
assert 'workstreams' in t, 'cortex-line workstreams missing'
b['workstreams'] = t['workstreams']
with open('greg/path.json', 'w') as f:
    f.write(json.dumps(b, indent=2) + '\n')
print('path.json: workstreams unioned; both guard surfaces preserved')
PYEOF

# --- 6) foundry/owned-source.json: deliberate refresh via the owned walk -----
python3 - <<'PYEOF'
import json, os
from pathlib import Path
root = Path('.')
DATA_DIRS = ("contracts", "organs", "constitution", "authority")
packages = sorted(p.name for p in root.iterdir()
                  if p.is_dir() and (p / "__init__.py").exists() and p.name != "tests")
owned = packages + [d for d in DATA_DIRS if (root / d).exists() and d not in packages]
EXCLUDE_PARTS = {"__pycache__", ".pytest_cache"}
EXCLUDE_SUFFIX = {".pyc", ".pyo"}
out = []
for top in owned:
    for p in (root / top).rglob("*"):
        if p.is_file() and not (EXCLUDE_PARTS & set(p.parts)) \
                and p.suffix not in EXCLUDE_SUFFIX \
                and "evidence" not in p.parts[1:2]:
            out.append(p.as_posix())
doc = {"version": "owned-source/1", "files": sorted(out),
       "scope": "Explicit published owned-source paths, not arbitrary repository files. Refresh deliberately when adding or retiring an owned runtime source."}
with open('foundry/owned-source.json', 'w') as f:
    f.write(json.dumps(doc, indent=2) + '\n')
print('owned-source.json refreshed:', len(out), 'files')
PYEOF

# --- 7) lineage docs: cortex-line text + the fabric's appended record --------
python3 - <<'PYEOF'
SUFFIXES = {
  'docs/FOUNDER_INTENT_LEDGER.md': '.github/kimi-one-mind-graft/data/ledger_suffix.md',
  'docs/PROJECT_COGNITION_CONTINUITY.md': '.github/kimi-one-mind-graft/data/continuity_suffix.md',
}
for path, suffix_path in SUFFIXES.items():
    with open(suffix_path, 'rb') as f:
        suffix = f.read()
    assert suffix.startswith(b'\n## '), f'{suffix_path}: unexpected suffix start'
    with open(path, 'ab') as f:
        f.write(suffix)
print('lineage unions appended')
PYEOF

# payload was removed after the copy in section 3; the data dir is consumed by
# sections 4 and 7, so it is removed here, before the commit.
rm -rf .github/kimi-one-mind-graft/data

# --- 8) structural self-check -------------------------------------------------
test -f greg/cognition/selector.py
test -f greg/cognition/__init__.py
test -f greg/cognition/contracts.py
test ! -f greg/cognition.py
python3 -c "import json; json.load(open('greg/path.json')); json.load(open('foundry/owned-source.json')); json.load(open('docs/cortex/SEED_GENOME_REQUIREMENTS.json'))"

# --- 9) commit and push -------------------------------------------------------
git add -A
git -c user.name='github-actions[bot]' \
    -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
    commit -q -m "One Mind surface: reconcile cortex 0.4.0 with the execution fabric (INTENT-0037)

Scripted graft: 155 cortex-line files byte-verbatim from $T,
the fabric's deterministic selector preserved verbatim as
greg/cognition/selector.py, 12 deterministic scripted merges,
and 5 authored records (intent, deliberation, reconciliation,
package init, verifier run). Applied by CI for byte-fidelity;
the identical tree was built and tested locally (1198 passed,
zero kept-test regressions vs the base's own roster)."
if [ "${GRAFT_PUSH:-1}" = "1" ]; then
  git push origin "HEAD:${GITHUB_REF_NAME}"
else
  echo "GRAFT_PUSH=0: commit created locally, push skipped"
fi
