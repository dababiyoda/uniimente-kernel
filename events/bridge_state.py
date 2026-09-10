"""Durable transport freshness and bounded internal operation claims.

Semantic owner: Kernel events/. Truth: existing EventSpine/EvidenceLedger.
One POSIX writer per state path; no distributed claims or effect authorization.
An outstanding claim after replacement requires reconciliation, not auto-retry.
"""
import os

from events.spine import Event, EventSpine
from provenance.ledger import EvidenceLedger, sha256_json


class OperationConflict(ValueError):
    pass


class BridgeState:
    def __init__(self, path, constitution_hash, *, owner, legal_principal):
        if not path or not constitution_hash or owner not in ('daleobanks', 'wealthmachine', 'kernel'):
            raise ValueError('explicit state path, anchor and owner required')
        self.ledger = EvidenceLedger(constitution_hash, path)
        self.spine = EventSpine(self.ledger)
        self.owner = owner
        if not legal_principal or legal_principal == 'UNIIMENTE':
            self.ledger.close()
            raise ValueError('existing accountable legal principal required; never UNIIMENTE')
        self.legal_principal = legal_principal
        for event in self.spine.replay('bridge.'):
            if (event.source != 'spiffe://uniimente.internal/adapter/' + owner
                    or event.actor != 'spiffe://uniimente.internal/organ/' + owner
                    or event.legal_principal != legal_principal):
                self.ledger.close()
                raise ValueError('bridge history owner/principal mismatch; no identity inheritance')
        self._active = set()
        self._pid = os.getpid()

    def close(self):
        self.ledger.close()

    def _events(self, kind):
        return self.spine.replay('bridge.' + kind)

    def _record(self, kind, payload, parent=None):
        event = Event('bridge.' + kind, 'spiffe://uniimente.internal/adapter/' + self.owner,
                      'spiffe://uniimente.internal/organ/' + self.owner, payload,
                      self.legal_principal, causal_parent=parent)
        self.spine.emit(event)
        return event.event_id

    def check_and_store(self, nonce):
        with self.ledger._lock:
            if any(e.payload['nonce'] == nonce for e in self._events('nonce')):
                return False
            self._record('nonce', {'nonce': nonce})
            return True

    def begin(self, *, caller, operation, key, body_digest):
        identity = sha256_json([caller, self.owner, operation, key])
        with self.ledger._lock:
            records = [e for e in self._events('operation') if e.payload['id'] == identity]
            if records:
                original, last = records[0], records[-1]
                if original.payload['body_digest'] != body_digest:
                    raise OperationConflict('logical key reused with different payload')
                if last.payload['state'] == 'completed':
                    if last.payload['result_digest'] != sha256_json(last.payload['result']):
                        raise OperationConflict('retained result integrity mismatch')
                    return identity, last.payload
                return identity, {'state': 'running' if identity in self._active
                                  and os.getpid() == self._pid else 'reconciliation_required'}
            self._record('operation.claimed', {'id': identity, 'caller': caller,
                'operation': operation, 'key': key, 'body_digest': body_digest, 'state': 'running'})
            self._active.add(identity)
            return identity, {'state': 'claimed'}

    def finish(self, identity, result):
        with self.ledger._lock:
            records = [e for e in self._events('operation') if e.payload['id'] == identity]
            if (not records or records[-1].payload['state'] != 'running'
                    or identity not in self._active or os.getpid() != self._pid):
                raise OperationConflict('no active claim; appraisal/result cannot be replaced')
            self._record('operation.completed', {**records[0].payload, 'state': 'completed',
                         'result': result, 'result_digest': sha256_json(result)},
                         parent=records[0].event_id)
            self._active.remove(identity)

    def abandon(self, identity):
        # No authority to discard the obligation or retry uncertain work.
        self._active.discard(identity)

    def result(self, assessment_id, *, caller):
        for ev in reversed(self._events('operation.completed')):
            p = ev.payload
            result = p['result']
            if p['caller'] == caller and assessment_id in (result.get('id'),
                                                           result.get('opportunity_packet_id')):
                if p['result_digest'] != sha256_json(result):
                    raise OperationConflict('retained result digest mismatch')
                return result
        return None
