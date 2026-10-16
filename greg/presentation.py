"""Read-only cognitive result cards from the canonical receipt ledger."""

def cognitive_summaries(journal):
    keys=("problem_id", "method", "selection_rationale", "output", "uncertainty", "proof_class", "receipt_id", "reason_code", "outcome_state", "latency", "money_cost", "missing_information")
    result=[]
    for record in journal.ledger.by_type("receipt"):
        answer=record.payload.get("result",{}).get("output")
        if isinstance(answer,dict) and answer.get("schema_version", "").startswith("greg-cognition/"):
            card={k:answer.get(k) for k in keys}
            card['selection_rationale']=answer.get('method_selection_reason')
            card['proof_class']=answer.get('proof_type')
            result.append(card)
    return result[-10:][::-1]
