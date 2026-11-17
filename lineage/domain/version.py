"""Pure canonical identity for an agent's inheritable version inputs."""
from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from hashlib import sha256
import json
import re

from lineage.core.errors import LineageError

_SAFE = 9007199254740991
_AGENT = re.compile(r'[a-z][a-z0-9-]{2,63}')
_HASH = re.compile(r'[0-9a-f]{64}')


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise LineageError('bad_args', 'invalid JSON value') from None


def _match(value, pattern):
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise LineageError('bad_args', 'invalid identifier or digest')


def _pins(skills):
    if (not isinstance(skills, Sequence) or isinstance(skills, (str, bytes, bytearray))
            or len(skills) > 256):
        raise LineageError('bad_args', 'invalid skill pins')
    result, seen = [], set()
    for pin in skills:
        if type(pin) is not dict or set(pin) != {'skill_id', 'sha256'}:
            raise LineageError('bad_args', 'invalid skill pin fields')
        _match(pin['skill_id'], _AGENT)
        _match(pin['sha256'], _HASH)
        key = (pin['skill_id'], pin['sha256'])
        if key in seen:
            raise LineageError('bad_args', 'duplicate skill pin')
        seen.add(key)
        result.append(deepcopy(pin))
    return sorted(result, key=lambda pin: (pin['skill_id'], pin['sha256']))


def _inputs(constitution_sha256, skills, memory_gen):
    _match(constitution_sha256, _HASH)
    if type(memory_gen) is not int or not 0 <= memory_gen <= _SAFE:
        raise LineageError('bad_args', 'invalid memory generation')
    return {'constitution_sha256': constitution_sha256,
            'skills': _pins(skills), 'memory_gen': memory_gen}


def agent_version(constitution_sha256: str, skills: Sequence[dict],
                  memory_gen: int) -> str:
    """Hash only constitution, sorted pin copies and the memory fold counter."""
    return sha256(_canonical(_inputs(constitution_sha256, skills, memory_gen))).hexdigest()
