"""Each safeguard binding the authority office to the registered capability must fail its tests.

    python scripts/ci/check_authority_registered_identity_mutants.py

The office refuses a manifest, an adapter or an invocation context that is not the one the registry holds under the
capability's id, runs no caller code before the Gate dispatches, and runs nothing without a registry
(tests/unit/test_greg_authority_registered_identity.py). Mutants are applied to greg/authority.py in a scratch copy
of the repository, never to the working tree. Exit status 1 if any mutant survives or no longer applies.

Mutants named N1..N14 are the ones an independent audit of 7245fa5d found surviving the first version of this gate
(docs/evidence/session-handoff-2026-11-11 on branch claude/session-evidence-20261111). Two of the audit's mutants
are not listed because they are equivalent on this code: N10 (ATTACHED state without a registered manifest) is
still refused by the context check, and N15 (adapters compared with == instead of identity) cannot differ for
plain functions.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = "greg/authority.py"
TESTS = "tests/unit/test_greg_authority_registered_identity.py"

CHECK = "        unattached = self.attach_refusal(manifest, adapter, ctx)\n"
MANIFEST_IF = "        if registered is None or not self._same_manifest(registered, manifest):\n"
ADAPTER_IF = "        if adapter is None or self.registry.adapters.get(cid) is not adapter:\n"
NO_CTX_IF = "        if not isinstance(ctx, InvocationContext) or ctx.manifest is None:\n"
CTX_IF = "        if not self._same_manifest(registered, ctx.manifest):\n"
SAME = ("        return presented is registered or (type(presented) is type(registered)\n"
        "                                           and presented.digest() == registered.digest())\n")
REBIND = "        ctx = replace(ctx, manifest=self.registry.manifests[manifest.capability_id])\n"
LAZY = "                return around(registered)(params, ctx)\n"
GATE = "        record = self.gate.run(proposal, executor=execute, approver=approver, standing_grant=grant)\n"
NOREG = ("        if self.registry is None:       # fail closed: nothing can be shown to be attached\n"
         "            return (")
RECORD = ('            self.ledger.append("event", {"type": "greg.authority.refused_unattached", '
          '"proposal_id": proposal_id,\n')
CLAIMED = "        if claim is not None:  # the dispatch the claim names, so its reconciliation settles exactly that one\n"

MUTANTS = [
    # -- registered identity -------------------------------------------------------------------------------
    (AUTHORITY, "a substituted adapter executes", ADAPTER_IF, "        if False:\n"),
    (AUTHORITY, "a missing adapter is not refused",
     ADAPTER_IF, "        if adapter is not None and self.registry.adapters.get(cid) is not adapter:\n"),
    (AUTHORITY, "N3 the adapter's identity is checked only when the context names another capability",
     ADAPTER_IF, "        if (adapter is None or self.registry.adapters.get(cid) is not adapter) "
                 "and getattr(ctx, 'manifest', None) is not manifest:\n"),
    (AUTHORITY, "N14 with a dispatch wrapper the adapter's identity is not checked at all",
     CHECK, "        unattached = self.attach_refusal(manifest, self.registry.adapters.get(manifest.capability_id) "
            "if around is not None and self.registry is not None else adapter, ctx)\n"),
    (AUTHORITY, "a manifest that differs from the registered one executes", MANIFEST_IF, "        if False:\n"),
    (AUTHORITY, "an equal copy of the registered manifest is refused", SAME, "        return presented is registered\n"),
    (AUTHORITY, "a manifest subclass may vouch for itself",
     SAME, "        return presented is registered or presented.digest() == registered.digest()\n"),
    (AUTHORITY, "the context may carry any manifest", CTX_IF, "        if False:\n"),
    (AUTHORITY, "N1 the context's manifest is compared by id only",
     CTX_IF, "        if getattr(ctx.manifest, 'capability_id', None) != cid:\n"),
    (AUTHORITY, "N2 a missing context is not refused before the dispatch",
     NO_CTX_IF, "        if ctx is None or not hasattr(ctx, 'manifest'):\n            return None\n        if False:\n"),
    (AUTHORITY, "the adapter is handed the caller's context manifest, not the registered one",
     REBIND, "        ctx = replace(ctx)\n"),
    (AUTHORITY, "N5 a refusal for a wrong manifest or a wrong context leaves no ledger record",
     RECORD, '            ("manifest presented" in unattached or "invocation context" in unattached) or '
             'self.ledger.append("event", {"type": "greg.authority.refused_unattached", "proposal_id": proposal_id,\n'),
    (AUTHORITY, "N6 a detached capability outside the cone is offered for approval instead of refused",
     CHECK, "        unattached = self.attach_refusal(manifest, adapter, ctx) if not cone.admits(\n"
            "            capability=manifest.capability_id, target=target, consequence_class=consequence,\n"
            "            cost_usd=cost_usd, spent_usd=spent_usd) else self.attach_refusal(manifest, adapter, ctx) \\\n"
            "            if self.registry is None or self.registry.state.get(manifest.capability_id) == 'ATTACHED' "
            "else None\n"),
    # -- caller code runs only inside the Gate's dispatch --------------------------------------------------
    (AUTHORITY, "a dispatch wrapper is handed nothing to run and runs alone",
     LAZY, "                return around(None)(params, ctx)\n"),
    (AUTHORITY, "a dispatch wrapper is ignored", LAZY, "                return registered(params, ctx)\n"),
    (AUTHORITY, "N7 under a dispatch wrapper the registered adapter runs twice",
     LAZY, "                around(registered)(params, ctx)\n                return registered(params, ctx)\n"),
    (AUTHORITY, "a dispatch wrapper is applied before the attach check",
     CHECK, "        adapter = around(adapter) if around is not None else adapter\n" + CHECK),
    (AUTHORITY, "caller code runs before the act is authorized (the wrapper is built on the way in)",
     "            registered = adapter\n", "            registered = around(adapter)\n            around = lambda a: a\n"),
    (AUTHORITY, "N8 the wrapper is built after the grant but before the Gate runs",
     GATE, "        if around is not None:\n            around(registered)\n" + GATE),
    (AUTHORITY, "the wrapper is built again for a dispatch whose outcome is unknown",
     CLAIMED, "        if around is not None and claim is not None:\n            around(registered)\n" + CLAIMED),
    # -- no office without a registry ----------------------------------------------------------------------
    (AUTHORITY, "an office with no registry runs everything",
     NOREG, "        if self.registry is None:\n            return None\n        if False:\n            return ("),
    (AUTHORITY, "N9 an office with no registry runs every capability that is not read_only",
     NOREG, "        if self.registry is None and manifest.consequence_class != 'read_only':\n            return None\n"
            "        if self.registry is None:\n            return ("),
    (AUTHORITY, "an office can be built without naming a registry",
     "signer, ledger, registry, grants: GrantIssuer | None = None):",
     "signer, ledger, registry=None, grants: GrantIssuer | None = None):"),
]


def main() -> int:
    return run(MUTANTS, TESTS, prefix="authority-registered-identity-mutants-", root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
