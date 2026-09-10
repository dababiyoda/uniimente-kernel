"""SR-001 frozen controls. Synthetic data only; never invoke an external tool."""
import builtins
import copy
import json
from dataclasses import asdict

import pytest

from events.spine import Event, EventSpine
from provenance.ledger import EvidenceLedger
from adapters import bridge_transport as transport

ANCHOR = 'sha256:' + 'a' * 64


def close(ledger):
    if hasattr(ledger, 'close'):
        ledger.close()


def event():
    return Event('signal.received', 'external:synthetic', 'synthetic', {},
                 'alfonso_lopez', event_id='synthetic-event-1')


def test_genesis_hash_is_recomputed():
    ledger = EvidenceLedger(ANCHOR)
    ledger.records[0].payload['constitution_hash'] = 'foreign'
    assert not ledger.verify_chain()[0]


def test_foreign_constitution_refused(tmp_path):
    path = str(tmp_path / 'chain.jsonl')
    close(EvidenceLedger(ANCHOR, path))
    with pytest.raises(ValueError):
        EvidenceLedger('sha256:' + 'b' * 64, path)


@pytest.mark.parametrize('data', ['', '\n', '{', '{}\n'])
def test_empty_or_truncated_history_refused(tmp_path, data):
    path = tmp_path / 'chain.jsonl'
    path.write_text(data)
    with pytest.raises(ValueError):
        EvidenceLedger(ANCHOR, str(path))


def test_restart_recovers_deduplication(tmp_path):
    path = str(tmp_path / 'chain.jsonl')
    ledger = EvidenceLedger(ANCHOR, path)
    e = event()
    EventSpine(ledger).ingest(e)
    close(ledger)
    restored = EvidenceLedger(ANCHOR, path)
    assert EventSpine(restored).ingest(e) is None
    assert len(restored.by_type('event')) == 1
    close(restored)


def test_conflicting_event_identity_refuses():
    spine = EventSpine(EvidenceLedger(ANCHOR))
    e = event()
    spine.ingest(e)
    changed = copy.deepcopy(e)
    changed.payload = {'forged': True}
    with pytest.raises(ValueError):
        spine.ingest(changed)


def test_definite_append_failure_does_not_consume_event(monkeypatch):
    ledger = EvidenceLedger(ANCHOR)
    spine = EventSpine(ledger)
    original = ledger.append
    def fail(*a, **kw):
        raise OSError('definite refusal before write')
    monkeypatch.setattr(ledger, 'append', fail)
    e = event()
    with pytest.raises(OSError):
        spine.ingest(e)
    monkeypatch.setattr(ledger, 'append', original)
    assert spine.ingest(e) is not None


def test_failed_ledger_append_does_not_advance_memory(tmp_path, monkeypatch):
    ledger = EvidenceLedger(ANCHOR, str(tmp_path / 'chain.jsonl'))
    original = builtins.open
    def fail(path, mode='r', *a, **kw):
        if 'a' in mode:
            raise OSError('definite refusal before write')
        return original(path, mode, *a, **kw)
    monkeypatch.setattr(builtins, 'open', fail)
    before = asdict(ledger.records[-1])
    with pytest.raises(OSError):
        ledger.append('test', {'x': 1})
    assert asdict(ledger.records[-1]) == before
    close(ledger)


def test_transport_missing_key_is_never_unsigned(monkeypatch):
    monkeypatch.delenv('WEALTHMACHINE_SIGNING_KEY', raising=False)
    for flag in (None, False, True):
        with pytest.raises(transport.BridgeSecurityError):
            transport.verify_headers({}, b'{}', nonce_cache=transport.NonceCache(),
                                     require_signature=flag)


def test_unknown_contract_version_refused(monkeypatch):
    monkeypatch.setenv('WEALTHMACHINE_SIGNING_KEY', 'synthetic-only-transport-key')
    with pytest.raises(transport.BridgeSecurityError):
        h = transport.build_headers(b'{}', identity='daleobanks', schema_version='99.0')
        transport.verify_headers(h, b'{}', nonce_cache=transport.NonceCache())


def test_invalid_signature_cannot_poison_nonce(monkeypatch):
    monkeypatch.setenv('WEALTHMACHINE_SIGNING_KEY', 'synthetic-only-transport-key')
    h = transport.build_headers(b'{}', identity='daleobanks', schema_version='1.1')
    cache = transport.NonceCache()
    altered = {**h, transport.H_SIGNATURE: 'f' * 64}
    with pytest.raises(transport.BridgeSecurityError):
        transport.verify_headers(altered, b'{}', nonce_cache=cache)
    assert transport.verify_headers(h, b'{}', nonce_cache=cache)['signed'] == 'true'


@pytest.mark.parametrize('signature', ['é' * 64, 'A' * 64, ''])
def test_malformed_signature_refuses_without_type_error(monkeypatch, signature):
    monkeypatch.setenv('WEALTHMACHINE_SIGNING_KEY', 'synthetic-only-transport-key')
    headers = transport.build_headers(b'{}', identity='daleobanks', schema_version='1.1')
    headers[transport.H_SIGNATURE] = signature
    with pytest.raises(transport.BridgeSecurityError):
        transport.verify_headers(headers, b'{}', nonce_cache=transport.NonceCache())


def test_boolean_is_not_a_hash_version():
    ledger = EvidenceLedger(ANCHOR)
    ledger.records[0].hash_version = True
    assert not ledger.verify_chain()[0]
