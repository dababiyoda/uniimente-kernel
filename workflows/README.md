# workflows/

Declarative institutional workflow specifications (YAML): approval lifecycle,
venture validation gates, incident response and shutdown recovery. They describe
states and gates; executable workflows run on `events/` (the durable spine),
`loom/` and GREG missions (`greg/missions.py`). The verifier
(`verifier/verify.py`) checks they exist and parse.
