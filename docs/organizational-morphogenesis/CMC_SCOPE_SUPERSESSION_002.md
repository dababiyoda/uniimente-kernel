# Explicit scope supersession — CMC-002

The exact latest founder text is FOUNDER-DIRECTION-CMC-SCOPE-002.json.
It explicitly permits design/development records only and prohibits manual
relay from authorizing runtime execution. DEC-CMC-002 is a new linked decision
with exactly two passes; it does not edit or add a third pass to DEC-CMC-001.

This supersedes the real start/continue surface in the original CMC freeze.
There will be no real runtime CLI, authenticated-command substitute, grants,
passports, credentials, policy edits, authority changes or actual mission run.
All unauthenticated runtime commands are refused. Simulation fixtures are
clearly named and cannot produce actual founder acceptance or runtime authority.

Permitted deliverables: pure proposal router, independent read-only appraisal,
record-only founder direction semantics, simulation tests using existing Kernel
mechanisms, preserved evidence, and one draft PR on the existing branch.

The original source corpus and numeric test bounds remain frozen. New protocol
test assertion: no real runtime command is accepted, even if its input is a
content-bound founder-direction record. An unknown or claimed signature is
also refused; this module never authenticates a human or issues authority.

Actual Cathedral Metabolism Closure remains 0. A simulated continuation is a
test result, not founder acceptance, VDM or whole-machine closure. The original
master directive and genuine Phase-4 success condition remain unfinished.

Source metadata limitation: exact visible text is retained, but the interface
does not expose its authoring timestamp or opaque conversation/message ID.
Those fields remain null, with the observed relay timestamp separately labeled.
No timestamp, identity, source reference or authentication proof is fabricated.
If exact unavailable metadata becomes required, return NEEDS_FOUNDER_DECISION.

Earlier pytest failures remain recorded. Later actual passing test commands
may close only the environment gap they demonstrate, not erase the failures.
