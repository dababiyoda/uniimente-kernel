"""A closure refuted for a reason that is not an effect check (the delivered brief was edited after delivery), while
one of its sensors (brief.freshness) is detached. Does routing blame the capabilities for an effect failure?"""
from pathlib import Path
import json, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import Child, facts, close_then_stop, detach
from greg import routing, autonomy
from greg.body import Body
from greg.templates import engineering_brief
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_briefs import github, repo  # noqa: F401


def test_routing_blame(tmp_path, repo, github, capsys):  # noqa: F811
    child = Child(tmp_path)
    clock = Clock()
    home, key, body_id, _ = make_body(tmp_path)
    spec = engineering_brief(local={"kernel": str(repo)}, github=["acme/kernel", "acme/organ"])
    mid = spec["mission_id"]
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home, clock=clock) as body:
        body.boot(); clock.advance(30); body.tick(); body.engine.book.rebuild()
        [request] = body.engine.book.open_requests()
        drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve"}))
    close_then_stop(home, clock, mid=mid, step=30.0)
    [brief] = sorted((Path(home) / "deliveries" / "briefs").glob("*.md"))
    detach(home, key, body_id, "brief.freshness")
    brief.write_text(brief.read_text() + "\nappended after delivery\n")
    with Body(home, clock=clock) as body:
        body.tick()
        [a] = facts(body, "mission.appraised", mid)
        import greg
        tree = Path(greg.__file__).resolve().parents[1].name
        with capsys.disabled():
            print(f"\n[{tree}] verdict, not_run, adapters/deliveries run:", a["verdict"], sorted(a.get("not_run", {})), child.ran)
            print(f"[{tree}] checks false:", sorted(k for k, v in a["checks"].items() if v is False))
            print(f"[{tree}] routing:", json.dumps(routing.track_record(body.journal), sort_keys=True))
            print(f"[{tree}] autonomy.failures:", [(f["kind"], f["run"].payload["action_id"]) for f in autonomy.failures(body.journal)])
