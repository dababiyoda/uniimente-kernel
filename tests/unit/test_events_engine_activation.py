import pytest

import events.engine as engine


def test_failed_activation_receipt_does_not_leave_replacement_active(monkeypatch):
    class Replacement:
        pass

    class FailingLedger:
        def append(self, *args, **kwargs):
            raise OSError("activation receipt unavailable")

    for name in (
        "_ACTIVE",
        "_ACTIVE_ID",
        "_ALLOWLIST",
        "_VALIDATOR",
        "_ACTIVATED_BY",
    ):
        monkeypatch.setattr(engine, name, getattr(engine, name))

    assert engine.assert_default_is_original()

    with pytest.raises(OSError, match="activation receipt unavailable"):
        with engine.activate(
            Replacement,
            provider_id="W-test-replacement",
            workflow_ids={"wf-test"},
            activated_by="human:test",
            validator=lambda payload, context: [],
            ledger=FailingLedger(),
        ):
            pytest.fail("activation must not enter without a durable receipt")

    assert engine.assert_default_is_original()
    assert engine.active_provider_id() is None
