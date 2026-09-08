"""Kernel contract owner. Strict JSON and full Draft 2020-12 validation.

Installed as the same pinned boundary distribution in both organ consumers.
No network reference resolution, permissive optional dependency, or mirror.
"""
import json
from functools import lru_cache
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('duplicate JSON key')
            out[key] = value
        return out
    def invalid(value):
        raise ValueError('non-finite JSON value')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError('malformed JSON bytes') from exc


@lru_cache
def validator(name):
    if name not in ('opportunity-packet', 'venture-assessment',
                    'wire-opportunity-packet', 'wire-venture-assessment',
                    'capability-grant', 'workflow-execution'):
        raise ValueError('unregistered contract')
    schema = strict_json(files('contracts').joinpath(name + '.schema.json').read_bytes())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_contract(payload, name):
    # Re-encode to reject Python NaN/Infinity and non-JSON objects too.
    json.dumps(payload, allow_nan=False)
    errors = sorted(validator(name).iter_errors(payload), key=lambda e: str(list(e.path)))
    if errors:
        raise ValueError(f'{name}: {errors[0].message}')
    return payload
