#!/usr/bin/env bash
# One command from a fresh clone to a designated, supervised GREG Body 1 inside
# ChromeOS's Linux environment (Crostini).
#
#   git clone -b claude/uniimente-greg-reconciliation-39syff https://github.com/dababiyoda/uniimente-kernel
#   cd uniimente-kernel && bash greg/chromebook/install.sh
#
# It only composes existing greg commands (doctor, init, founder keygen/enroll,
# service install, body designate). Every step is idempotent: re-running it skips
# what is done. It never handles your passphrase (greg asks for it directly), never
# uses sudo, and grants GREG no capability or permission. Designation names this
# machine as your first body; it is accepted by the running body, not by this script.
#
# Ported mechanisms (INTENT-2026-09-30-DEVELOPMENTAL-INHERITANCE): Python 3.11+
# selection and a durable greg command come from the Mac runbook repairs in PR #122
# (commit ea95ebb); the command is a wrapper on PATH instead of a shell alias.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GREG_HOME_DIR="${GREG_HOME:-$HOME/.uniimente/greg}"
VENV="$HOME/.uniimente/venv"
KEY="$HOME/.greg-founder.pem"
BIN_DIR="$HOME/.local/bin"
READ_ROOT="$HOME/src"
DELIVER_ROOT="$HOME/GREG"
PYTHON_CHOICE=""
SERVICE="yes"
SKIP_DEPS=0
NO_PASSPHRASE=0
ALLOW_OTHER_LINUX=0

usage() {
  cat <<'EOF'
Usage: bash greg/chromebook/install.sh [options]
  --home DIR            body home (default ~/.uniimente/greg)
  --venv DIR            virtual environment (default ~/.uniimente/venv)
  --key FILE            founder key file (default ~/.greg-founder.pem)
  --bin-dir DIR         where the greg command is written (default ~/.local/bin)
  --read-root DIR       folder GREG may read (default ~/src)
  --deliver-root DIR    folder GREG delivers into (default ~/GREG)
  --python PATH         a specific Python 3.11+ interpreter
  --no-service          do not install/enable the systemd user service (development only)
  --skip-deps           use the chosen interpreter as is, no venv or pip (development only)
  --no-passphrase       UNPROTECTED founder key (tests only; never for Alfonso's key)
  --allow-other-linux   run outside ChromeOS Linux (the body will not be your Chromebook)
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --home) GREG_HOME_DIR="$2"; shift 2 ;;
    --venv) VENV="$2"; shift 2 ;;
    --key) KEY="$2"; shift 2 ;;
    --bin-dir) BIN_DIR="$2"; shift 2 ;;
    --read-root) READ_ROOT="$2"; shift 2 ;;
    --deliver-root) DELIVER_ROOT="$2"; shift 2 ;;
    --python) PYTHON_CHOICE="$2"; shift 2 ;;
    --no-service) SERVICE="no"; shift ;;
    --skip-deps) SKIP_DEPS=1; shift ;;
    --no-passphrase) NO_PASSPHRASE=1; shift ;;
    --allow-other-linux) ALLOW_OTHER_LINUX=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 64 ;;
  esac
done

step() { printf '\n== %s\n' "$*"; }
fail() { printf 'STOP: %s\n' "$*" >&2; exit "${2:-1}"; }

step "1/8 This is ChromeOS Linux"
[ "$(uname -s)" = "Linux" ] || fail "GREG Body 1 runs inside ChromeOS's Linux environment (Settings > About ChromeOS > Developers)." 10
if [ -e /dev/.cros_milestone ] || [ -d /opt/google/cros-containers ]; then
  echo "ChromeOS Linux environment detected."
elif [ "$ALLOW_OTHER_LINUX" = 1 ]; then
  echo "WARNING: not ChromeOS Linux. This body can run missions, but it is not your Chromebook."
else
  fail "No ChromeOS Linux markers found. On the Chromebook, turn on Linux in Settings > About ChromeOS > Developers. For another Linux machine pass --allow-other-linux." 10
fi

step "2/8 Python 3.11+ and git"
PY=""
for candidate in "$PYTHON_CHOICE" python3.13 python3.12 python3.11 python3; do
  [ -n "$candidate" ] || continue
  if command -v "$candidate" >/dev/null 2>&1 \
     && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    PY="$(command -v "$candidate")"; break
  fi
done
[ -n "$PY" ] || fail "No Python 3.11+ found. In the Linux terminal: sudo apt install -y python3 python3-venv git" 11
command -v git >/dev/null 2>&1 || fail "git is missing. In the Linux terminal: sudo apt install -y git" 11
echo "Using $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"

step "3/8 Environment"
if [ "$SKIP_DEPS" = 1 ]; then
  GREG_PY="$PY"
  echo "Skipping venv and dependency install (--skip-deps)."
else
  "$PY" -c 'import ensurepip' >/dev/null 2>&1 || fail "Python venv support is missing. In the Linux terminal: sudo apt install -y python3-venv" 12
  [ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -m pip install --quiet -r "$REPO/requirements-dev.txt" \
    -r "$REPO/requirements-cognition.txt" -r "$REPO/requirements-cortex-engines.txt" \
    -r "$REPO/requirements-browser.txt"
  if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1 \
     && ! command -v google-chrome >/dev/null 2>&1; then
    "$VENV/bin/python" -m playwright install chromium
  fi
  GREG_PY="$VENV/bin/python"
fi

step "4/8 The greg command"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/greg" <<EOF
#!/bin/sh
# Written by greg/chromebook/install.sh. Runs GREG from $REPO for the body at $GREG_HOME_DIR.
export PYTHONPATH="$REPO\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$GREG_PY" -m greg --home "$GREG_HOME_DIR" "\$@"
EOF
chmod 755 "$BIN_DIR/greg"
GREG="$BIN_DIR/greg"
case ":$PATH:" in
  *":$BIN_DIR:"*) echo "greg is on your PATH." ;;
  *) echo "Wrote $GREG. Open a new terminal (or run: export PATH=\"$BIN_DIR:\$PATH\") to use 'greg'." ;;
esac

step "5/8 Prerequisite check (greg doctor --chromebook)"
DOCTOR="$("$GREG" doctor --chromebook || true)"
MISSING="$(printf '%s' "$DOCTOR" | "$GREG_PY" -c 'import json,sys; print(" ".join(json.load(sys.stdin).get("missing", [])))')"
if [ "$SERVICE" = "no" ]; then
  MISSING="$(printf '%s\n' $MISSING | grep -v -e '^systemctl_available$' -e '^user_service_available$' | tr '\n' ' ' || true)"
fi
MISSING="$(echo "$MISSING" | xargs || true)"
if [ -n "$MISSING" ]; then
  printf '%s\n' "$DOCTOR"
  fail "Missing prerequisites: $MISSING" 13
fi
echo "Ready."

step "6/8 Body"
mkdir -p "$READ_ROOT" "$DELIVER_ROOT"
if [ -f "$GREG_HOME_DIR/body.json" ]; then
  echo "A body already exists at $GREG_HOME_DIR; keeping it."
else
  "$GREG" init --read-root "$READ_ROOT" --deliver-root "$DELIVER_ROOT" >/dev/null
  echo "Created a body at $GREG_HOME_DIR (reads $READ_ROOT, delivers into $DELIVER_ROOT)."
fi

status_field() {  # $1: python expression over the status dict
  "$GREG" status 2>/dev/null | "$GREG_PY" -c "import json,sys; s=json.load(sys.stdin); print($1)" 2>/dev/null || true
}

step "7/8 Your founder key"
KEYGEN_FLAGS=()
[ "$NO_PASSPHRASE" = 1 ] && KEYGEN_FLAGS+=(--no-passphrase) && echo "WARNING: --no-passphrase leaves the key unprotected (tests only)."
if [ -f "$KEY" ]; then
  echo "Keeping your existing key at $KEY."
else
  echo "Choose a passphrase you will remember; GREG cannot recover it. Never give this key to an agent."
  "$GREG" founder keygen --key "$KEY" "${KEYGEN_FLAGS[@]}" > "$KEY.pub"
  chmod 644 "$KEY.pub"
fi
ENROLLED="$(status_field 'len(s.get("security", {}).get("founder_keys_enrolled", []))')"
if [ "${ENROLLED:-0}" -gt 0 ] 2>/dev/null; then
  echo "A founder key is already enrolled."
else
  [ -s "$KEY.pub" ] || fail "Found $KEY but not $KEY.pub. Enroll it yourself: greg founder enroll --pubkey <hex printed when it was created>" 14
  "$GREG" founder enroll --pubkey "$(cat "$KEY.pub")" >/dev/null
  echo "Enrolled your public key."
fi

step "8/8 Supervised service and first-body designation"
if [ "$SERVICE" = "yes" ]; then
  "$GREG" service install --platform linux >/dev/null
  systemctl --user daemon-reload
  systemctl --user enable --now greg-body.service
  echo "greg-body.service is enabled and running (it restarts GREG after a crash while Linux runs)."
else
  echo "Skipping the service (--no-service). Start the body yourself with: greg run"
fi
DESIGNATED="$(status_field 'len(s.get("designation", []))')"
if [ "${DESIGNATED:-0}" -gt 0 ] 2>/dev/null; then
  echo "This body is already designated as your first body."
elif ls "$GREG_HOME_DIR"/inbox/*body_designate*.json >/dev/null 2>&1; then
  echo "A signed designation is already waiting in the inbox for the body to accept."
else
  echo "Sign the designation of THIS machine as your first body (your passphrase again):"
  "$GREG" body designate --key "$KEY" "${KEYGEN_FLAGS[@]}" >/dev/null
  echo "Designation queued; the running body accepts it on its next tick."
fi

cat <<EOF

GREG is installed. Next, the first mission (greg/CHROMEBOOK_FIRST_MISSION.md, step 2):
  greg console --key $KEY --no-model     then open the private owner link printed by the console in Chrome
  Ask: "Brief me on the state of my repositories." Review, sign, close the tab.
  greg status        note the PID, then: kill -9 <PID>   (the service restarts GREG)
  Approve the one waiting delivery in the console, read the brief in $DELIVER_ROOT/briefs/, accept or reject it.
  greg vepmc ; greg morning ; greg presence --hours 2 ; greg path
To stop: greg stop --local && systemctl --user stop greg-body.service
To run again after a stop: greg start --local && systemctl --user start greg-body.service
EOF
