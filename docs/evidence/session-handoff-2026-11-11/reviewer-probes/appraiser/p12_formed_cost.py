"""The head builds the Genesis registry projection for every appraisal (base: only for cognition sensors). On a
body that holds formed open-source capabilities, does a plain fs.read closure still appraise, and at what cost?"""
import time
from lib import *
from greg.templates import network_in_words

ROUTE = "Warehouse to Hub: 4 miles. Hub to Store: 3. Warehouse to Store: 9. Shortest route from Warehouse to Store."
FLOW = ("Plant to North: 10. Plant to South: 5. North to Market: 4. South to Market: 8. North to South: 6. "
        "Maximum flow from Plant to Market.")
tmp = tmpdir("p12")
home, key, body_id, _ = make_body(tmp)
note = workspace(home, MID) / "note.txt"; note.parent.mkdir(parents=True, exist_ok=True); note.write_text("original")
drop(home, signed(key, body_id, "MISSION", network_in_words(text=ROUTE, auto_attach=True)))
drop(home, signed(key, body_id, "MISSION", network_in_words(text=FLOW, auto_attach=True)))
drop(home, signed(key, body_id, "MISSION", mission(MID, checks=[note_check("c", note, "final")],
     strategies=[write_strategy("w", "note.txt", "final", ["c"])], capabilities=["fs.read", "fs.write"])))
clock = Clock()
with Body(home, clock=clock) as body:
    body.boot()
    for _ in range(6):
        body.tick(); clock.advance(31)
    show("formed capabilities", sorted((c, s) for c, s in body.registry.state.items() if c.startswith(("acquired.", "built.", "constructed."))))
    show("appraised", [(e.payload["mission_id"][:24], e.payload["verdict"]) for e in body.journal.replay("mission.appraised")])
    times = []
    for _ in range(3):
        t = time.monotonic(); v = body.appraise(MID); times.append(round(time.monotonic() - t, 2))
    show("on-demand appraisal of the fs.read closure: verdict, seconds x3", (v["verdict"], v.get("findings"), times))
