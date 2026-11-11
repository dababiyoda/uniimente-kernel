#!/bin/bash
# usage: run_probe.sh <worktree dir name under the scratchpad> <probe file in adv-negrc-probes> [pytest args...]
# Copies the probe into the worktree's tests/unit, runs it with -s, and removes it again (the worktree stays clean).
S=/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad
wt="$S/$1"; probe="$2"; shift 2
source "$S/venv/bin/activate"
cp "$S/adv-negrc-probes/$probe" "$wt/tests/unit/$probe"
(cd "$wt" && python -B -m pytest -q -p no:cacheprovider -s "tests/unit/$probe" "$@")
code=$?
rm -f "$wt/tests/unit/$probe"
exit $code
