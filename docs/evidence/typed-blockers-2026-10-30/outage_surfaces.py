"""Where does an outage blocker show up in the product, and does any surface carry its required authority?"""
import json, sys, tempfile
from pathlib import Path
root = Path(sys.argv[1]); sys.path.insert(0, str(root))
from tests.unit import test_greg_blockers as T
from greg.body import status, morning_projection
d = Path(tempfile.mkdtemp()); home, *_, mid = T.host_outage(d)
st = status(home)
ac = [m["active_constraint"] for m in st["missions"] if m["mission_id"] == mid][0]
mr = morning_projection(home)
surfaces = {"status.active_constraint": ac,
            "status.decisions_required": st["decisions_required"],
            "morning.q4_intentionally_not_done": [x for x in mr["q4_intentionally_not_done"] if x["mission_id"] == mid],
            "morning.q13_tonight": [x for x in mr["q13_tonight"] if x["mission_id"] == mid],
            "morning.blockers": mr.get("blockers", "ABSENT")}
for name, value in surfaces.items():
    text = json.dumps(value, default=str)
    print(f"{name}: outage_shown={'outage' in text} required_authority_field={'required_authority' in text}")
print(json.dumps(ac, indent=1))
