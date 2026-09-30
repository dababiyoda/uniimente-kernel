#!/bin/bash
# GREG Body 1 — native macOS verification package.
#
# Run by Alfonso on the Mac (never by an agent claiming to have run it):
#     bash greg/mac/verify_mac_body.sh
#
# It uses a THROWAWAY founder key and a throwaway body under a temporary home,
# registers a temporary LaunchAgent (label ai.uniimente.greg.verify), proves
# launchd restarts the body after kill -9 and does NOT restart it after a signed
# founder stop, exercises the macOS adapters (which may trigger Accessibility /
# Automation / Screen Recording prompts), then unloads everything. It spends
# nothing, contacts no account and touches no real founder key.
# Evidence is written to ~/greg-mac-verification-<timestamp>/ for the PR.
set -euo pipefail

KERNEL="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$HOME/greg-mac-verification-$STAMP"
HOME_DIR="$OUT/body"
LABEL="ai.uniimente.greg.verify"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$OUT"
exec > >(tee "$OUT/transcript.log") 2>&1

echo "== system"; sw_vers; uname -m; sysctl -n hw.memsize; sysctl -n hw.ncpu
[[ "$(uname)" == "Darwin" ]] || { echo "not macOS; refusing"; exit 2; }

echo "== python environment (isolated venv)"
python3 -m venv "$OUT/venv"
"$OUT/venv/bin/pip" install -q -r "$KERNEL/requirements-dev.txt"
PY="$OUT/venv/bin/python"
export PYTHONPATH="$KERNEL"
cd "$KERNEL"

echo "== unit + closure evidence on this Mac"
"$PY" -m pytest -q -k "greg" tests/unit | tee "$OUT/pytest-greg.log"

echo "== body init + throwaway founder key"
"$PY" -m greg --home "$HOME_DIR" init --read-root "$OUT"
PUB="$("$PY" -m greg founder keygen --key "$OUT/throwaway-founder.pem" --no-passphrase)"
"$PY" -m greg --home "$HOME_DIR" founder enroll --pubkey "$PUB"

echo "== launchd agent (KeepAlive SuccessfulExit=false)"
"$PY" - "$HOME_DIR" "$PLIST" "$LABEL" "$PY" <<'EOF'
import plistlib, sys
from pathlib import Path
from greg import service
home, plist, label, py = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
(home / "logs").mkdir(parents=True, exist_ok=True)
data = plistlib.loads(service.launchd_plist(home, python=py))
data["Label"] = label
data["ProgramArguments"][-1] = "0.5"   # fast ticks for verification
plist.parent.mkdir(parents=True, exist_ok=True)
plist.write_bytes(plistlib.dumps(data))
print(plist)
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

wait_json() { for _ in $(seq 1 120); do "$PY" -c "$1" 2>/dev/null && return 0; sleep 0.5; done; echo "TIMEOUT: $2"; return 1; }
wait_json "import json;assert json.load(open('$HOME_DIR/heartbeat.json'))['state']=='RUNNING'" "body running"
PID1="$("$PY" -c "import json;print(json.load(open('$HOME_DIR/heartbeat.json'))['pid'])")"
echo "body pid $PID1"

echo "== mission from a separate interface process (UI closes immediately)"
HOR="$("$PY" -c "from datetime import datetime,timedelta,timezone as t;print((datetime.now(t.utc)+timedelta(days=1)).isoformat().replace('+00:00','Z'))")"
WS="$HOME_DIR/workspace/m_mac-verification"
cat > "$OUT/mission.json" <<EOF
{"mission_id":"m:mac-verification","founder_expression":"Verify the first body on this Mac.","intended_effect":"a note written and the frontmost app observed",
"priority":90,"closure":{"kind":"bounded"},
"success_checks":[{"check_id":"note","description":"note written","sensor":{"capability":"fs.read","params":{"path":"$WS/note.txt"},"target":"fs:note.txt"},"predicate":{"op":"contains","field":"text","value":"mac"}}],
"strategies":[{"action_id":"write","capability":"fs.write","params":{"relative_path":"note.txt","content":"mac body verified"},"target":"workspace:note.txt","advances":["note"],"rationale":"write the note"}],
"light_cone":{"capabilities":["fs.read","fs.write"],"targets":["fs:*","workspace:*"],"max_consequence_class":"internal_write","budget_usd":0,"horizon":"$HOR"}}
EOF
"$PY" -m greg --home "$HOME_DIR" mission submit "$OUT/mission.json" --key "$OUT/throwaway-founder.pem" --no-passphrase
wait_json "import json,sys;sys.path.insert(0,'$KERNEL');from greg.body import status;s=status('$HOME_DIR');assert all(g['achieved'] for g in s['goals']) and s['goals']" "mission achieved"

echo "== kill -9: launchd must restart the body"
kill -9 "$PID1"
wait_json "import json;h=json.load(open('$HOME_DIR/heartbeat.json'));assert h['pid']!=$PID1 and h['state']=='RUNNING'" "launchd restart"
PID2="$("$PY" -c "import json;print(json.load(open('$HOME_DIR/heartbeat.json'))['pid'])")"
echo "restarted as pid $PID2"

echo "== macOS adapters (permission prompts are expected; record what is granted)"
"$PY" - "$OUT" <<'EOF' | tee "$OUT/mac-adapters.json"
import json, sys
from pathlib import Path
from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
out = Path(sys.argv[1]); results = {}
for cid, params in (("mac.frontmost_app", {}), ("mac.notify", {"text": "GREG body verification"}),
                    ("mac.screenshot", {"name": "verify.png"})):
    manifest, adapter = BUILTINS[cid]
    ctx = InvocationContext(workspace=out / "adapters", read_roots=(out,), secrets=SecretBroker(out / "s.json"), manifest=manifest)
    try:
        results[cid] = {"ok": True, "output": adapter(params, ctx)}
    except Exception as exc:
        results[cid] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
print(json.dumps(results, indent=1, default=str))
EOF

echo "== browser.render with this Mac's Chrome (JavaScript-rendered page on loopback; egress limited)"
mkdir -p "$OUT/site"
printf '<html><head><title>mac probe</title></head><body><p id="x">static</p><script>document.getElementById("x").textContent="rendered on the mac"</script></body></html>' > "$OUT/site/index.html"
"$PY" -m http.server 8813 --bind 127.0.0.1 -d "$OUT/site" >/dev/null 2>&1 & SITE=$!
sleep 1
"$PY" - "$OUT" <<'EOF' | tee "$OUT/mac-browser.json"
import json, sys
from pathlib import Path
from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
out = Path(sys.argv[1]); manifest, adapter = BUILTINS["browser.render"]
ctx = InvocationContext(workspace=out / "adapters", read_roots=(out,), secrets=SecretBroker(out / "s.json"), manifest=manifest)
try:
    r = adapter({"url": "http://127.0.0.1:8813/index.html"}, ctx)
    print(json.dumps({"ok": "rendered on the mac" in r["text"], **{k: r[k] for k in ("title", "browser", "os_sandboxed", "egress")}}, indent=1))
except Exception as exc:
    print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
EOF
kill "$SITE" 2>/dev/null || true

echo "== remote channel for the phone (loopback; signed reads only)"
"$PY" -m greg --home "$HOME_DIR" serve --port 8814 >/dev/null 2>&1 & SERVE=$!
sleep 1
"$PY" - "$HOME_DIR" "$OUT/throwaway-founder.pem" <<'EOF' | tee "$OUT/mac-remote.json"
import json, sys, urllib.request, urllib.error
from greg.founder import load_founder_key, sign_read
home, key = sys.argv[1], load_founder_key(sys.argv[2], None)
body_id = json.load(urllib.request.urlopen("http://127.0.0.1:8814/api/hello"))["body_id"]
try:
    urllib.request.urlopen("http://127.0.0.1:8814/api/status"); unsigned = "ALLOWED (defect)"
except urllib.error.HTTPError as e:
    unsigned = e.code
req = urllib.request.Request("http://127.0.0.1:8814/api/status",
                             headers=sign_read(key, body_id=body_id, method="GET", path="/api/status"))
print(json.dumps({"unsigned_read": unsigned, "signed_read_principal": json.load(urllib.request.urlopen(req))["principal"]}))
EOF
kill "$SERVE" 2>/dev/null || true

echo "== signed founder stop: launchd must NOT restart"
"$PY" -m greg --home "$HOME_DIR" stop --key "$OUT/throwaway-founder.pem" --no-passphrase
wait_json "import json;assert json.load(open('$HOME_DIR/heartbeat.json'))['state']=='STOPPED'" "founder stop"
sleep 15
"$PY" -c "import json;h=json.load(open('$HOME_DIR/heartbeat.json'));assert h['state']=='STOPPED', h" && echo "still stopped after 15s: OK"
launchctl print "gui/$(id -u)/$LABEL" > "$OUT/launchctl-print.txt" 2>&1 || true

echo "== morning report + evidence bundle"
"$PY" -m greg --home "$HOME_DIR" morning > "$OUT/morning-report.json"
cp "$HOME_DIR/ledger.jsonl" "$OUT/ledger.jsonl"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$PLIST"
echo "MAC VERIFICATION COMPLETE. Attach $OUT (minus throwaway-founder.pem) to the PR."
