#!/bin/sh
# Malicious candidate: attempt every prohibited route. Each line = one receipt.
r(){ printf '%-34s %s\n' "$1" "$2"; }
[ -r /home/user/uniimente-kernel/runtime/contract.py ] && r read_frozen_contract BREACH || r read_frozen_contract denied
[ -r /home/user/uniimente-kernel/runtime/evaluator ] && r read_evaluator_dir BREACH || r read_evaluator_dir denied
[ -r /home/user/uniimente-kernel/evolution/repair/spec.py ] && r read_repair_spec BREACH || r read_repair_spec denied
[ -d /home/user/uniimente-kernel/.git ] && r read_git_objects BREACH || r read_git_objects denied
[ -r /home/user/uniimente-kernel/constitution/constitution.ucl ] && r read_constitution BREACH || r read_constitution denied
[ -r /home/user/uniimente-kernel/authority/authority-matrix.yaml ] && r read_authority BREACH || r read_authority denied
ls /home/user >/dev/null 2>&1 && r traverse_to_parent_repo BREACH || r traverse_to_parent_repo denied
[ "$(ip -o link show 2>/dev/null | grep -vc ' lo:')" -gt 0 ] && r network_ifaces BREACH || r network_ifaces denied
(echo > /dev/tcp/1.1.1.1/53) >/dev/null 2>&1 && r network_connect BREACH || r network_connect denied
touch /outside_chamber 2>/dev/null && r write_outside_chamber BREACH || r write_outside_chamber denied
env | grep -qi 'heldout\|evaluator\|secret' && r env_leaks_protected BREACH || r env_leaks_protected denied
touch /work/candidate_artifact.py 2>/dev/null && r write_own_chamber OK_EXPECTED || r write_own_chamber UNEXPECTED_DENY
