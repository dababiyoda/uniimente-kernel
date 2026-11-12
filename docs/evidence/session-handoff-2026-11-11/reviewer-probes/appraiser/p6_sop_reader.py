"""Does a downstream reader count the appraiser's UNAVAILABLE as a failed appraisal? sop.trend (feeds greg path N4)
and compounding.retained_reuse wording. Crafted ledger with the test file's own helpers; the reader code is real."""
from datetime import datetime, timedelta, timezone
from lib import show, tmpdir
from greg import sop, path as devpath
from greg.body import Body
from tests.greg_fixtures import make_body
from tests.unit.test_greg_sop_compounding import closure, taught_and_ratified

for last in ("VERIFIED", "UNAVAILABLE", "REFUTED"):
    home, *_ = make_body(tmpdir("p6"))
    with Body(home) as body:
        j = body.journal
        proposal, record = taught_and_ratified(j, home)
        for n in range(4):
            spec = sop.instantiate(record, {"text": f"sop run {n}"}, now=datetime.now(timezone.utc) + timedelta(seconds=n))
            closure(j, spec, approvals=(), verdict=last if n == 3 else "VERIFIED")
        [entry] = sop.trend(j)["procedures"]
        show(f"4th SOP run appraised {last} | compounding", entry["compounding"])
        show(f"4th SOP run appraised {last} | why_not", entry.get("why_not"))
        show(f"4th SOP run appraised {last} | quality_failures", entry["sop_runs"]["quality_failures"])
        show(f"4th SOP run appraised {last} | verified_outcomes", entry["sop_runs"]["verified_outcomes"])
        inc = devpath.sop_compounding(j)["incomplete"]
        show(f"4th SOP run appraised {last} | greg path N4 missing", [m for m in inc[0]["missing"] if "quality" in m] if inc else None)
