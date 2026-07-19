"""Semantic Constitution model over the five parsed .ucl documents.

Every accessor is sourced from the five real files — no invented content:

- version / status / ratified_by       <- constitution "uniimente"
- permanent_prohibitions               <- permanent_prohibitions.non_delegable
- humans_authorize                     <- doctrine.humans_authorize
- failure_posture                      <- failure_posture (fails_toward /
                                        never_fails_toward)
- participant_rights / hard_refusal    <- participant_rights > right blocks
- safety_states                        <- safety_states > state blocks
- shutdown_may_never_block             <- shutdown_rule "authority"
- sovereignty_ranks                    <- sovereignty_hierarchy > level blocks
- kill_conditions                      <- kill_condition blocks
- amendment_hard_rules                 <- amendment_rule > hard_rules

Constitutional clause: the kernel_invariant's ``on_violation =
"refuse_and_escalate"`` — a constitution that is missing a required block or
attribute, or holds an ambiguous value, raises UCLError at build time. An
unenforceable constitution fails closed and compiles to nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ast import Block
from .lexer import UCLError
from .parser import Document, parse_file


def _err(block: Block, message: str) -> UCLError:
    return UCLError(message, line=block.line or None, col=block.col or None)


def _require_str(block: Block, name: str) -> str:
    value = block.attrs.get(name)
    if not isinstance(value, str) or not value:
        raise _err(block, f"required string attribute {name!r} is missing or empty")
    return value


def _require_int(block: Block, name: str) -> int:
    value = block.attrs.get(name)
    # bool is a subclass of int; a boolean is NOT an acceptable integer here.
    if type(value) is not int:
        raise _err(block, f"required integer attribute {name!r} is missing")
    return value


def _require_str_list(block: Block, name: str) -> list[str]:
    value = block.attrs.get(name)
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise _err(block, f"required string-list attribute {name!r} is missing or malformed")
    return list(value)


def _require_child(block: Block, kind: str) -> Block:
    child = block.child(kind)
    if child is None:
        raise _err(block, f"required nested block {kind!r} is missing")
    return child


@dataclass(frozen=True)
class Constitution:
    """The enforceable semantic model of the five-file constitution."""

    version: str
    status: str
    ratified_by: str | None
    permanent_prohibitions: frozenset
    humans_authorize: bool
    failure_posture: dict
    participant_rights: list
    hard_refusal_rights: list
    safety_states: dict
    shutdown_may_never_block: list
    sovereignty_ranks: list
    kill_conditions: list
    amendment_hard_rules: dict
    current_state: str = field(default="normal")

    # ------------------------------------------------------------ construction

    @classmethod
    def from_documents(
        cls, documents: list[Document], *, current_state: str = "normal"
    ) -> "Constitution":
        """Build the semantic model from parsed documents. Fails closed."""
        if not documents:
            raise UCLError("no .ucl documents supplied")
        blocks = [block for document in documents for block in document.blocks]

        constitutions = [b for b in blocks if b.kind == "constitution"]
        if len(constitutions) != 1:
            raise UCLError(
                f"exactly one constitution block is required, found {len(constitutions)}"
            )
        constitution = constitutions[0]
        version = _require_str(constitution, "version")
        status = _require_str(constitution, "status")
        ratified_by = constitution.attrs.get("ratified_by")
        if ratified_by is not None and not isinstance(ratified_by, str):
            raise _err(constitution, "ratified_by must be a string or null")

        prohibitions = _require_child(constitution, "permanent_prohibitions")
        non_delegable = _require_str_list(prohibitions, "non_delegable")

        doctrine = constitution.child("doctrine")
        humans_authorize = True
        if doctrine is not None:
            value = doctrine.attrs.get("humans_authorize")
            if value is not None:
                if type(value) is not bool:
                    raise _err(doctrine, "doctrine.humans_authorize must be a bool")
                humans_authorize = value

        posture_block = _require_child(constitution, "failure_posture")
        fails_toward = _require_str_list(posture_block, "fails_toward")
        never_fails_toward = _require_str(posture_block, "never_fails_toward")
        failure_posture = {
            "fails_toward": fails_toward,
            "never_fails_toward": never_fails_toward,
        }

        rights_blocks = [b for b in blocks if b.kind == "participant_rights"]
        if len(rights_blocks) != 1:
            raise UCLError(
                f"exactly one participant_rights block is required, found {len(rights_blocks)}"
            )
        participant_rights: list[Block] = []
        for right in rights_blocks[0].children_of("right"):
            if not right.label:
                raise _err(right, "every right block must be labelled")
            _require_str(right, "rule")
            enforcement = _require_str(right, "enforcement")
            if enforcement not in ("hard_refusal", "soft_flag", "audit_only"):
                raise _err(
                    right,
                    f"right {right.label!r} has unknown enforcement {enforcement!r}",
                )
            participant_rights.append(right)
        if not participant_rights:
            raise _err(rights_blocks[0], "participant_rights must declare at least one right")

        hard_refusal_rights = [
            r for r in participant_rights if r.attrs["enforcement"] == "hard_refusal"
        ]

        ladders = [b for b in blocks if b.kind == "safety_states"]
        if len(ladders) != 1:
            raise UCLError(
                f"exactly one safety_states block is required, found {len(ladders)}"
            )
        safety_states: dict[str, str] = {}
        for state in ladders[0].children_of("state"):
            name = _require_str(state, "name")
            external_effects = _require_str(state, "external_effects")
            if name in safety_states:
                raise _err(state, f"duplicate safety state {name!r}")
            safety_states[name] = external_effects
        if "normal" not in safety_states:
            raise _err(ladders[0], "the safety_states ladder must include a 'normal' state")

        authority_rules = [b for b in blocks if b.kind == "shutdown_rule" and b.label == "authority"]
        if len(authority_rules) != 1:
            raise UCLError(
                'exactly one shutdown_rule "authority" block is required, '
                f"found {len(authority_rules)}"
            )
        shutdown_may_never_block = _require_str_list(
            authority_rules[0], "may_never_block_or_delay"
        )

        hierarchies = [b for b in blocks if b.kind == "sovereignty_hierarchy"]
        if len(hierarchies) != 1:
            raise UCLError(
                f"exactly one sovereignty_hierarchy block is required, found {len(hierarchies)}"
            )
        ranks: list[tuple[int, str, str]] = []
        for level in hierarchies[0].children_of("level"):
            rank = _require_int(level, "rank")
            name = _require_str(level, "name")
            owner = _require_str(level, "owner")
            ranks.append((rank, name, owner))
        if not ranks:
            raise _err(hierarchies[0], "sovereignty_hierarchy must declare at least one level")
        rank_numbers = [r[0] for r in ranks]
        if len(set(rank_numbers)) != len(rank_numbers):
            raise _err(hierarchies[0], "sovereignty_hierarchy contains duplicate ranks")
        ranks.sort(key=lambda entry: entry[0])

        kill_conditions = [b for b in blocks if b.kind == "kill_condition"]
        if not kill_conditions:
            raise UCLError("at least one kill_condition block is required")
        for condition in kill_conditions:
            if not condition.label:
                raise _err(condition, "every kill_condition block must be labelled")
            _require_str(condition, "when")
            _require_str(condition, "then")

        amendment_rules = [
            b
            for b in blocks
            if b.kind == "amendment_rule" and b.label == "constitutional_amendment"
        ]
        if len(amendment_rules) != 1:
            raise UCLError(
                'exactly one amendment_rule "constitutional_amendment" block is '
                f"required, found {len(amendment_rules)}"
            )
        hard_rules_block = _require_child(amendment_rules[0], "hard_rules")
        amendment_hard_rules: dict[str, bool] = {}
        for name, value in hard_rules_block.attrs.items():
            if type(value) is not bool:
                raise _err(
                    hard_rules_block, f"amendment hard rule {name!r} must be a bool"
                )
            amendment_hard_rules[name] = value
        if not amendment_hard_rules:
            raise _err(hard_rules_block, "hard_rules must not be empty")

        return cls(
            version=version,
            status=status,
            ratified_by=ratified_by,
            permanent_prohibitions=frozenset(non_delegable),
            humans_authorize=humans_authorize,
            failure_posture=failure_posture,
            participant_rights=participant_rights,
            hard_refusal_rights=hard_refusal_rights,
            safety_states=safety_states,
            shutdown_may_never_block=shutdown_may_never_block,
            sovereignty_ranks=ranks,
            kill_conditions=kill_conditions,
            amendment_hard_rules=amendment_hard_rules,
            current_state=current_state,
        )

    @classmethod
    def from_directory(
        cls, path: str | Path, *, current_state: str = "normal"
    ) -> "Constitution":
        """Parse every *.ucl file in ``path`` (sorted by name) and build the model."""
        root = Path(path)
        if not root.is_dir():
            raise UCLError(f"constitution directory not found: {root}")
        files = sorted(root.glob("*.ucl"), key=lambda p: p.name)
        if not files:
            raise UCLError(f"no .ucl files found in {root}")
        return cls.from_documents(
            [parse_file(f) for f in files], current_state=current_state
        )

    # ------------------------------------------------------------ canonical form

    def to_canonical(self) -> dict[str, Any]:
        """Deterministic JSON-able dump used for the content-addressed
        ``policy_version`` hash (SPEC-WP02 "Versioning").

        Excludes ``current_state``: the safety state is runtime posture, not
        constitutional content, so it must never change the policy version.
        """
        return {
            "version": self.version,
            "status": self.status,
            "ratified_by": self.ratified_by,
            "permanent_prohibitions": sorted(self.permanent_prohibitions),
            "humans_authorize": self.humans_authorize,
            "failure_posture": {
                "fails_toward": list(self.failure_posture["fails_toward"]),
                "never_fails_toward": self.failure_posture["never_fails_toward"],
            },
            "participant_rights": [
                {
                    "name": right.label,
                    "rule": right.attrs["rule"],
                    "enforcement": right.attrs["enforcement"],
                }
                for right in self.participant_rights
            ],
            # Ladder order is constitutional content: keep it as pairs.
            "safety_states": [[name, effects] for name, effects in self.safety_states.items()],
            "shutdown_may_never_block": list(self.shutdown_may_never_block),
            "sovereignty_ranks": [[rank, name, owner] for rank, name, owner in self.sovereignty_ranks],
            "kill_conditions": [
                {
                    "name": condition.label,
                    "when": condition.attrs["when"],
                    "then": condition.attrs["then"],
                }
                for condition in self.kill_conditions
            ],
            "amendment_hard_rules": dict(self.amendment_hard_rules),
        }
