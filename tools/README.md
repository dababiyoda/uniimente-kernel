# tools/

Standalone operator tools, not imported by the Kernel. `offline_test.py` is a
fail-closed Linux launcher that blocks network sockets (seccomp) for a child
process: network containment, not a filesystem sandbox.
