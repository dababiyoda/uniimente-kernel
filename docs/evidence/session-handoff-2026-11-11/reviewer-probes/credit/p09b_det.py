import json
from tests.unit.test_greg_evidence_corrections import World, file_read, CONTAINS, NOW
from greg import corrections
def build():
    w = World()
    w.mission("m:a", ("a", "fs.read", {"path": "/docs/a.txt"}, CONTAINS)); w.mission("m:r", ("a", "fs.read", {"path": "/docs/a.txt"}, CONTAINS))
    w.ra = w.read("m:a", "a", file_read("/docs/a.txt", "alpha v1")); w.achieve("m:a", w.ra)
    w.read("m:r", "a", file_read("/docs/a.txt", "alpha v1"), passed=False); w.tick(); w.tick()
    return w
a, b = build(), build()
print("receipt hashes equal across two identical builds:", a.ra == b.ra)
ia, ib = corrections.Index(a.journal), corrections.Index(b.journal)
strip = lambda cs: json.dumps([{k: v for k, v in c.items() if k not in ("cause_id", "basis", "trigger", "root")} | {"root_mission": c["root"]["mission_id"]} for c in cs], sort_keys=True)
print("causes equal once receipt hashes are set aside:", strip(ia.causes(NOW)) == strip(ib.causes(NOW)))
# same journal, causes computed twice, and containment read twice
print("same journal, computed twice:", json.dumps(ia.causes(NOW), sort_keys=True) == json.dumps(corrections.Index(a.journal).causes(NOW), sort_keys=True),
      corrections.contained_receipts(a.journal) == corrections.contained_receipts(a.journal))
