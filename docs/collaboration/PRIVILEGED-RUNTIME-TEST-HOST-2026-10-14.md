# Dedicated test host for Foundry #9, #10 and #26 (privileged runtimes)

Status: **specification awaiting founder approval**. Nothing here has run. Execution of privileged OCI runtimes in
the development container was refused on 2026-09-30, and the founder has said: "Require explicit founder approval
before using privileged dedicated infrastructure or expanding authority."

## What is already enforced without privilege

- **#9 and #10:** `foundry/systems/containers.run` refuses before building any command unless
  `UNIIMENTE_PRIVILEGED_RUNTIME_HOST` equals this machine's host name. `sudo` is never reached elsewhere.
- **#9:** an image whose config asks for uid or gid 0 is refused. Layer extraction keeps every path, symlink and hard
  link inside the root, never creates device nodes, drops setuid/setgid bits and keeps dotfile names.
  Tests: `tests/unit/test_foundry_containers_hardening.py`.
- **#26:** per-identity egress through one relay under the Kernel's seccomp filter, with no privilege required.
  Tests: `tests/unit/test_foundry_segmentation.py`.

## The host the remaining evidence needs

The founder chooses one of these:

1. **CI runner:** a GitHub-hosted runner job that installs pinned runc and gVisor, sets the approval variable to its
   own host name, and runs `python -m foundry.completion --record 9` and `--record 10`.
2. **Ephemeral VM:** a VM the founder owns, destroyed after the run. It must have no founder keys, no credentials and
   no production data.

Either way:

- **Egress:** none for #10. #9 needs only the pinned base image registries.
- **Probes:** escape probes target only resources the harness creates, plus RFC 5737 TEST-NET addresses.
- **Kill criteria:** stop and record if any probe reaches a host resource, an undeclared network address or a secret;
  the system then stays PARTIAL.

## Evidence that would move the rows

- **#9:** two builds with the same image digest, and identical capability output under runc and under gVisor, from
  independently unpacked root filesystems.
- **#10:** every escape probe denied inside gVisor and journaled in the hash chain. The host control stays limited to
  self-created resources.
- **#26:** the relay launched for the capabilities that today run inside the body process. That last step needs no
  privilege; it is ordinary engineering, separate from this host.

Approving the host grants nothing else. The rows become COMPLETE only when `python -m foundry.completion --audit`
re-derives that evidence.
