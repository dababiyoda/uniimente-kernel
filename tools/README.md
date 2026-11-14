# tools/

Standalone operator tools, not imported by the Kernel. `offline_test.py` is a
fail-closed Linux launcher that blocks network sockets (seccomp) for a child
process: network containment, not a filesystem sandbox.

`collaboration_protocol/` holds the founder's deliberation validator, vendored unchanged; CI runs it over every
deliberation record (`tests/unit/test_deliberation_records.py`).
