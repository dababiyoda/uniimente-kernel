"""Narrow source extraction plus explicitly provisional synthesis; never truth by citation."""
from .contracts import CognitionError

RESPONSE_SCHEMA = {"type":"object", "additionalProperties":False,
    "required":["claims","contradictions","uncertainty"], "properties":{
        "claims":{"type":"array","minItems":1,"maxItems":32,"items":{"type":"object","additionalProperties":False,
            "required":["text","source_id","quote","kind"],"properties":{
                "text":{"type":"string","minLength":1}, "source_id":{"type":["string","null"]},
                "quote":{"type":["string","null"]}, "kind":{"enum":["extracted","proposed"]}}}},
        "contradictions":{"type":"array","items":{"type":"string"}},
        "uncertainty":{"type":"string","minLength":1}}}


def validate_sources(sources):
    """Validate evidence before optional inference spends any model budget."""
    if not isinstance(sources, list) or not sources or len(sources) > 32:
        raise CognitionError("bounded sources required")
    index = {}
    for source in sources:
        if (not isinstance(source, dict) or not isinstance(source.get("id"), str)
                or not 1 <= len(source["id"]) <= 128 or not isinstance(source.get("text"), str)):
            raise CognitionError("source identity and text required")
        if source["id"] in index or not source["text"]:
            raise CognitionError("duplicate or empty source")
        index[source["id"]] = source["text"]
    return index


def validate_semantic(answer, sources):
    if not isinstance(answer, dict) or set(answer) != {"claims", "contradictions", "uncertainty"}:
        raise CognitionError("semantic response fields invalid")
    index = validate_sources(sources)
    if not isinstance(answer["claims"], list) or not 1 <= len(answer["claims"]) <= 32:
        raise CognitionError("bounded nonempty claims required")
    for claim in answer["claims"]:
        if not isinstance(claim, dict) or set(claim) != {"text", "source_id", "quote", "kind"}:
            raise CognitionError("typed semantic claim required")
        if claim["kind"] not in ("extracted", "proposed") or not isinstance(claim["text"], str) or not claim["text"].strip():
            raise CognitionError("claim kind/text invalid")
        if claim["kind"] == "extracted":
            if claim["source_id"] not in index or not claim["quote"] or claim["quote"] not in index[claim["source_id"]] or claim["text"] != claim["quote"]:
                raise CognitionError("evidence mismatch: extracted fact must equal an exact source span")
        elif claim["source_id"] is not None and claim["source_id"] not in index:
            raise CognitionError("invented source")
    if not isinstance(answer["contradictions"], list) or not all(isinstance(x, str) for x in answer["contradictions"]):
        raise CognitionError("contradictions must be retained text")
    if not isinstance(answer["uncertainty"], str) or not answer["uncertainty"].strip():
        raise CognitionError("uncertainty required")
    return answer
