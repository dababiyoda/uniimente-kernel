"""UCL semantic model — Constitution over the five real documents.

Builds the executable view of the five constitution/*.ucl files
(constitution.ucl, amendment-policy.ucl, participant-rights.ucl,
shutdown-policy.ucl, sovereignty.ucl). Every accessor is sourced from those
files; nothing is invented. Missing required blocks/attributes, wrong types,
duplicate ranks or an unknown current safety state raise UCLError — the
kernel_invariant's ``on_violation = "refuse_and_escalate"`` applied at model
build time: ambiguity fails closed.

Clauses exposed (file of origin in parentheses):
- version / status / ratified_by            (constitution block)
- permanent_prohibitions.non_delegable      (permanent_prohibitions block)
- doctrine.humans_authorize                 (doctrine block)
- failure_posture                           (failure_posture block)
- participant_rights / hard_refusal_rights  (participant_rights.right blocks)
- safety_states ladder                      (safety_states.state blocks)
- shutdown_may_never_block                  (shutdown_rule "authority")
- sovereignty_ranks                         (sovereignty_hierarchy.level blocks)
- kill_conditions                           (kill_condition blocks)
- amendment_hard_rules                      (amendment_rule "constitutional_amendment")
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .ast import Block
from .lexer import UCLError
from .parser import Document, parse_file


def _err(block: Block | None, message: str) -> UCLError:
    if block is not None and block.line:
        return UCLError(message, line=block.line, col=block.col)
    return UCLError(message)


def _require_str(block: Block, name: str, *, allow_null: bool = False) -> str | None:
    if name not in block.attrs:
        raise _err(block, f"{block.kind} block is missing required attribute {name!r}")
    value = block.attrs[name]
    if allow_null and value is None:
        return None
    if not isinstance(value, str):
        raise _err(block, f"attribute {name!r} of {block.kind} block must be a string")
    return value


def _require_bool(block: Block, name: str) -> bool:
    if name not in block.attrs:
        raise _err(block, f"{block.kind} block is missing required attribute {name!r}")
    value = block.attrs[name]
    if type(value) is not bool:
        raise _err(block, f"attribute {name!r} of {block.kind} block must be a bool")
    return value


def _require_int(block: Block, name: str) -> int:
    if name not in block.attrs:
        raise _err(block, f"{block.kind} block is missing required attribute {name!r}")
    value = block.attrs[name]
    if type(value) is not int:  # bool is a subclass of int; exclude it explicitly
        raise _err(block, f"attribute {name!r} of {block.kind} block must be an integer")
    return value


def _require_str_list(block: Block, name: str) -> list[str]:
    if name not in block.attrs:
        raise _err(block, f"{block.kind} block is missing required attribute {name!r}")
    value = block.attrs[name]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise _err(
            block, f"attribute {name!r} of {block.kind} block must be a list of strings"
        )
    return list(value)


def _require_child(block: Block, kind: str) -> Block:
    child = block.child(kind)
    if child is None:
        raise _err(block, f"{block.kind} block is missing required nested block {kind!r}")
    return child


class Constitution:
    """The semantic model of the five-file UNIIMENTE constitution."""

    def __init__(
        self,
        *,
        version: str,
        status: str,
        ratified_by: str | None,
        permanent_prohibitions: frozenset[str],
        humans_authorize: bool,
        failure_posture: dict[str, Any],
        participant_rights: list[Block],
        hard_refusal_rights: list[Block],
        safety_states: dict[str, str],
        shutdown_may_never_block: list[str],
        sovereignty_ranks: list[tuple[int, str, str]],
        kill_conditions: list[Block],
        amendment_hard_rules: dict[str, bool],
        current_state: str = "normal",
    ):
        if current_state not in safety_states:
            raise UCLError(
                f"current safety state {current_state!r} is not on the safety_states ladder"
            )
        self.version = version
        self.status = status
        self.ratified_by = ratified_by
        self.permanent_prohibitions = permanent_prohibitions
        self.humans_authorize = humans_authorize
        self.failure_posture = failure_posture
        self.participant_rights = participant_rights
        self.hard_refusal_rights = hard_refusal_rights
        self.safety_states = safety_states
        self.shutdown_may_never_block = shutdown_may_never_block
        self.sovereignty_ranks = sovereignty_ranks
        self.kill_conditions = kill_conditions
        self.amendment_hard_rules = amendment_hard_rules
        self.current_state = current_state

    # ------------------------------------------------------------ construction

    @classmethod
    def from_documents(
        cls, documents: Iterable[Document], *, current_state: str = "normal"
    ) -> "Constitution":
        """Build (and fully validate) the model from the parsed .ucl set."""
        blocks = [block for doc in documents for block in doc.blocks]

        constitutions = [b for b in blocks if b.kind == "constitution"]
        if len(constitutions) != 1:
            raise UCLError(
                f"exactly one constitution block is required, found {len(constitutions)}"
            )
        constitution = constitutions[0]

        version = _require_str(constitution, "version")
        status = _require_str(constitution, "status")
        ratified_by = _require_str(constitution, "ratified_by", allow_null=True)

        doctrine = _require_child(constitution, "doctrine")
        humans_authorize = _require_bool(doctrine, "humans_authorize")

        prohibitions_block = _require_child(constitution, "permanent_prohibitions")
        non_delegable = _require_str_list(prohibitions_block, "non_delegable")
        if not non_delegable:
            raise _err(prohibitions_block, "non_delegable must not be empty")
        if len(set(non_delegable)) != len(non_delegable):
            raise _err(prohibitions_block, "non_delegable contains duplicate matters")

        posture_block = _require_child(constitution, "failure_posture")
        failure_posture = {
            "fails_toward": _require_str_list(posture_block, "fails_toward"),
            "never_fails_toward": _require_str(posture_block, "never_fails_toward"),
        }

        rights_blocks = [b for b in blocks if b.kind == "participant_rights"]
        if len(rights_blocks) != 1:
            raise UCLError(
                f"exactly one participant_rights block is required, found {len(rights_blocks)}"
            )
        participant_rights = rights_blocks[0].children_of("right")
        if not participant_rights:
            raise _err(rights_blocks[0], "participant_rights must declare at least one right")
        for right in participant_rights:
            if not right.label:
                raise _err(right, "every right block must be labelled")
            _require_str(right, "rule")
            _require_str(right, "enforcement")
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
