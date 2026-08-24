"""A sealed experiment embeds a live dataclass, so the type must evolve safely.

Two sealed specs — `evolution/repair/spec.py` and `evolution/migration/spec.py`
— put `EXPERIMENT.to_dict()` inside their frozen tables. That dict is a
serialisation of a **live** `ExperimentSpec`, so with a plain `asdict` every new
field on that dataclass silently moved both historical seals: the type could not
evolve without breaking a record of what a past experiment *was*.

Found 2026-08-24 by adding `predicted_success_probability` and watching six
sealed-experiment tests fail. They were right to fail — the bytes they cover had
genuinely changed.

The remedy is the one already ratified in this repository for Witness v2, which
had the identical problem: absent optional fields are **dropped from the
serialisation rather than written as null**, so anything hashed before the field
existed hashes the same afterwards. No historical hash was updated to make
current implementation pass, which FOUNDER-RULING-2026-08-23 forbids by name.

This file lives outside `test_repair_spec_frozen.py` deliberately: that file is
itself a pinned `SEALED_BLOBS` entry, and appending these tests to it tripped
`test_no_sealed_repair_file_was_modified_to_achieve_this`. The guard was correct
and the tests moved rather than the pin.
"""
from __future__ import annotations

import dataclasses

from evolution.experiment import ExperimentSpec
from evolution.repair import spec as repair_spec


def test_the_repair_seal_sits_where_it_was_recorded():
    assert repair_spec.spec_hash() == repair_spec.SPEC_SHA256
    assert repair_spec.expectations_hash() == repair_spec.EXPECTATIONS_SHA256


def test_the_migration_seal_sits_where_it_was_recorded():
    from evolution.migration import spec as migration_spec

    assert migration_spec.spec_hash() == migration_spec.SPEC_SHA256


def test_every_optional_field_is_absent_from_an_unset_serialisation():
    """The property that keeps both seals still while the type grows."""
    optional = ExperimentSpec._OPTIONAL
    assert optional, "the drop-set is empty; to_dict is back to a plain asdict"

    declared = {f.name for f in dataclasses.fields(ExperimentSpec)}
    assert optional <= declared, (
        f"_OPTIONAL names fields that do not exist: {sorted(optional - declared)}")

    bare = repair_spec.EXPERIMENT.to_dict()
    for name in optional:
        assert name not in bare, (
            f"{name} is in _OPTIONAL but still serialises when unset; the seal "
            f"moved the moment it was added")


def test_a_forecast_that_is_actually_set_does_serialise():
    """Dropping unset fields must not become dropping the field.

    A spec that states a forecast is a different experiment and must hash
    differently. Otherwise the omission would be hiding data rather than
    preserving a seal — the failure mode with the worse polarity.
    """
    stated = dataclasses.replace(repair_spec.EXPERIMENT,
                                 predicted_success_probability=0.25)

    assert stated.to_dict()["predicted_success_probability"] == 0.25
    assert stated.to_dict() != repair_spec.EXPERIMENT.to_dict()


def test_a_future_optional_field_is_covered_by_the_same_rule():
    """Simulates the next addition rather than trusting the next author.

    An optional field added WITHOUT being declared in `_OPTIONAL` serialises as
    null and moves the seals. This asserts the rule catches that, using a
    throwaway subclass so the real type is untouched.
    """
    @dataclasses.dataclass
    class WithUndeclaredField(ExperimentSpec):
        something_new: float | None = None

    payload = WithUndeclaredField(
        **dataclasses.asdict(repair_spec.EXPERIMENT)).to_dict()

    assert "something_new" in payload and payload["something_new"] is None, (
        "an undeclared optional field must still serialise as null — that is "
        "precisely why it would move a seal, and why _OPTIONAL is opt-in")
