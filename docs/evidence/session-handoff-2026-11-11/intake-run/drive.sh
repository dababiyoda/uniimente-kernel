#!/bin/bash
# Drives one intake-recommendation mission on a throwaway body. Test key: this is a rehearsal body, not the founder's.
set -u
S=<scratchpad>; R=$S/intake-run
PY=$S/venv-mind/bin/python; G="$PY -m greg --home $R/body"
cd $S/intake-mission
echo "start $(date -u +%H:%M:%S)"
$G init --read-root $R/code --deliver-root $R/out --worker-confinement supervised > $R/init.out 2>&1; echo "init $?"
PUB=$($PY -m greg founder keygen --key $R/founder.pem --no-passphrase 2>$R/keygen.err | tail -1)
$G founder enroll --pubkey "$PUB" > $R/enroll.out 2>&1; echo "enroll $?"
$G mission new intake-recommendation --intake $R/request.json --key $R/founder.pem --no-passphrase > $R/new.out 2>&1; echo "new $?"
$G run --max-ticks 2 --tick-seconds 1 > $R/run1.out 2>&1; echo "run1 $?"
$G decisions > $R/decisions.out 2>&1
RID=$($PY - "$R/decisions.out" <<'PYEOF'
import json, re, sys
text = open(sys.argv[1]).read()
m = re.search(r'"request_id":\s*"([^"]+)"', text)
print(m.group(1) if m else "")
PYEOF
)
echo "request $RID"
[ -n "$RID" ] || { echo "no approval ask"; exit 2; }
$G decide "$RID" approve --key $R/founder.pem --no-passphrase > $R/decide.out 2>&1; echo "decide $?"
echo "exec start $(date -u +%H:%M:%S)"
$G run --max-ticks 4 --tick-seconds 1 > $R/run2.out 2>&1; echo "run2 $?"
echo "exec end $(date -u +%H:%M:%S)"
$G status > $R/status.out 2>&1
ls -la $R/out/briefs 2>&1
echo "end $(date -u +%H:%M:%S)"
