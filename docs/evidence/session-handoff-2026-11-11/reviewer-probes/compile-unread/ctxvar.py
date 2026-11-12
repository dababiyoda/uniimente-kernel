"""Context-variable and untyped-host-stop probes on the compiler alone (head only for host_stop). cwd = tree."""
import sys, threading, subprocess, concurrent.futures
from rcu_common import *
from greg.cognition.cortex import reason, registry_view
from greg.cognition import cortex as C
from greg.missions import unanswered
host = Host()
reg = registry_view(); reg.set_state(METHOD, "ATTACHED")
def show(label, r):
    inner = r.get("selected_receipt") or {}
    print(f"{label}: state={r['state']} result={'yes' if r['result'] is not None else None} host_stop={r.get('host_stop', '<no key>')} unanswered={unanswered(r)} inner=({inner.get('abstention_state')},{inner.get('reason_code')},{str(inner.get('missing_information'))[:90]})")
# 1 stale note: stalled compile, then an answered one, then a declined one
host.stall("timeout"); show("1a stalled", reason(compile_params(), registry=reg))
host.recover(); show("1b answered after stall", reason(compile_params(), registry=reg))
show("1c prohibited after stall", reason(compile_params(consequence={"lawful": False}), registry=reg))
# 2 an exception between note and collection, then a declined compile
host.stall("timeout")
orig = C.independent_verify
try:
    from greg.cognition import compiler
    real_compile = compiler._compile
    def boom(*a, **k):
        from greg.cognition.budget import note_host_stop
        note_host_stop("timeout", process="solver"); raise RuntimeError("between note and collection")
    compiler._compile = boom
    try: reason(compile_params(), registry=reg)
    except RuntimeError as e: print("2a raised:", e)
    compiler._compile = real_compile
    host.recover()
    show("2b prohibited after exception", reason(compile_params(consequence={"lawful": False}), registry=reg))
    show("2c answered after exception", reason(compile_params(), registry=reg))
finally:
    compiler._compile = real_compile
# 3 the whole compile in a worker thread (a background dispatch that calls reason in a thread)
host.stall("timeout"); box = {}
t = threading.Thread(target=lambda: box.update(r=reason(compile_params(), registry=reg))); t.start(); t.join()
show("3a compile run inside a thread, stalled", box["r"])
# 3b the launch in another thread than the compile (a pool inside the decision): the note is written where nobody collects
real_numeric = C._numeric
def pooled(family, data, geometry):
    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        return ex.submit(real_numeric, family, data, geometry).result()
C._numeric = pooled
show("3b solver launched from a pool thread, stalled", reason(compile_params(), registry=reg))
host.stall("crash")
show("3c solver launched from a pool thread, crashed", reason(compile_params(), registry=reg))
C._numeric = real_numeric
# 4 a host condition run_isolated types itself: isolation unavailable (CapabilityError, failure_class transient)
host.recover()
real = caps.run_isolated
def no_isolation(argv, *a, **k):
    if any("worker.py" in str(x) for x in argv):
        raise caps.CapabilityError("network isolation unavailable; command refused", failure_class="transient")
    return real(argv, *a, **k)
caps.run_isolated = no_isolation
show("4 isolation unavailable (typed transient where raised)", reason(compile_params(), registry=reg))
caps.run_isolated = real
# 5 the verifier refutes the engine's answer
def refuting(argv, *a, **k):
    proc = real(argv, *a, **k)
    if "verify" in argv:
        import json
        out = json.loads(proc.stdout); out["verdict"] = "REFUTED"; out.setdefault("dissent", []).append("probe: refuted")
        from greg.cognition.contracts import canonical
        return subprocess.CompletedProcess(argv, 0, canonical(out).encode(), b"")
    return proc
caps.run_isolated = refuting
r = reason(compile_params(), registry=reg); show("5 verifier refutes the engine's answer", r)
print("   outcome of the executed method:", (r.get("selected_receipt") or {}).get("outcome"))
caps.run_isolated = real
# 6 a solver that dies of its own bug on this input (exit 1, deterministic)
for label, data in (("shift too short", {**SPHERE, "shift": [0.5]}), ("bounds empty", {**SPHERE, "bounds": []}), ("budget huge", {**SPHERE, "budget": 10**12})):
    try:
        show(f"6 {label}", reason({"problem_id": "p", "compile": {"geometry": {"geometry": "optimization"}, "data": data}}, registry=reg))
    except Exception as e:
        print(f"6 {label}: raised {type(e).__name__}: {str(e)[:120]}")
