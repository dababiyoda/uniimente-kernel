"""Guard against silently dropping source clauses or replacing the primary path."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_source_lineage_is_exact_and_all_appendix_identifiers_are_retained():
    register=json.loads((ROOT/'docs/cortex/SEED_GENOME_REQUIREMENTS.json').read_text())
    original=ROOT/register['source']
    assert hashlib.sha256(original.read_bytes()).hexdigest()==register['sha256']
    lines=original.read_text().splitlines()
    assert [int(r['source_location'].rsplit(':',1)[1]) for r in register['line_register']]==[i for i,l in enumerate(lines,1) if l.strip()]
    for row in register['line_register']:
        line=lines[int(row['source_location'].rsplit(':',1)[1])-1]
        assert hashlib.sha256(line.encode()).hexdigest()==row['source_sha256']
    assert len({r['source_id'] for r in register['source_crosswalk']})==122
    assert set(r['status'] for r in register['line_register']) <= {'active','needs_evidence'}
    for row in register['sections']:
        for ref in row['implementation_refs']:
            assert (ROOT/ref).exists(),ref


def test_cortex_is_subordinate_and_preserves_all_source_backcast_nodes():
    data=json.loads((ROOT/'greg/path.json').read_text())
    cortex=data['subordinate_workstreams']['polyintelligence_cortex']
    assert [n['id'] for n in cortex['nodes']]==[f'P{i}' for i in range(14)]
    assert set(cortex['c_to_p'])=={f'C{i}' for i in range(1,9)}
    for node in cortex['nodes']:
        assert all(node.get(k) for k in ('owner','dependency','budget_ceiling','review_trigger','falsification','smallest_next_experiment'))
        assert node['budget_ceiling']['paid_usd']==0
    assert data['nodes'][1]['id']=='N1' and data['nodes'][1]['sbm']['name']=='VEPMC'
