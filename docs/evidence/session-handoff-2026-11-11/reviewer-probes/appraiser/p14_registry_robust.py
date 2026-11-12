"""The head builds the registry projection in every appraisal. Does a closure whose mission workspace directory
does not exist (a read-only mission never wrote one), or is unwritable, still appraise? In-process and via the child."""
import os, shutil, stat
from lib import *
import greg.appraisal as appraisal

tmp = tmpdir("p14")
home, key, body_id, data = make_body(tmp)
f = data / "status.txt"; f.write_text("shipped")
# a read-only mission: one check that already passes, no strategy runs, nothing is written to its workspace
drop(home, signed(key, body_id, "MISSION", mission(MID, checks=[note_check("status", f, "shipped")],
     strategies=[write_strategy("w", "x.txt", "x", ["status"])], capabilities=["fs.read", "fs.write"])))
clock = Clock()
with Body(home, clock=clock) as body:
    for _ in range(4):
        body.tick(); clock.advance(31)
    ws = body.layout.workspace / MID.replace(":", "_")
    show("mission status, workspace exists, appraised", (body.engine.book.missions[MID].status, ws.exists(), [a["verdict"] for a in facts(body, "mission.appraised")]))
    before = sorted(p.name for p in body.layout.workspace.iterdir())
    v = body.appraise(MID)
    show("on-demand appraisal", (v["verdict"], v["findings"]))
    show("workspace entries created by the appraiser", sorted(set(p.name for p in body.layout.workspace.iterdir()) - set(before)), )
    if ws.exists():
        shutil.rmtree(ws)
    v = body.appraise(MID)
    show("workspace removed | verdict, findings, workspace recreated", (v["verdict"], v["findings"], ws.exists(), sorted(p.name for p in ws.iterdir()) if ws.exists() else None))
    if os.geteuid() != 0:
        os.chmod(body.layout.workspace, 0o555)
        v = body.appraise(MID)
        show("workspace root unwritable | verdict", (v["verdict"], v["findings"]))
        os.chmod(body.layout.workspace, 0o755)
    else:
        show("unwritable case", "not run: this process is root, chmod does not bind")
