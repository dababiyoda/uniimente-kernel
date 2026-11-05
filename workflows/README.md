# workflows/

Declarative institutional workflow specifications (YAML). These describe the
states and gates; executable workflows run on the event spine (`events/`) and
the Automation Loom (`loom/`).

| File | Describes |
|---|---|
| `approval-lifecycle.yaml` | proposal → approval → commit-time revalidation → external effect |
| `venture-validation.yaml` | evidence gates through which a Venture Cell earns authority |
| `incident-response.yaml` | incident triggers, containment and regression (nothing deleted) |
| `shutdown-recovery.yaml` | ordered black-start stages back from shutdown or quarantine |

The verifier (`verifier/verify.py`) checks these files are present and valid YAML.
