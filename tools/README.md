# tools/

Standalone operator tools, not imported by the Kernel.

- `offline_test.py`: a fail-closed Linux launcher that blocks network sockets
  (seccomp) for a child process. It is network containment, not a filesystem
  sandbox; use it only with reviewed source and synthetic fixtures.
