"""Strict, hash-pinned synthetic banks and confined artifact reads."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from types import SimpleNamespace

from lineage.core import journal, registry, schema
from lineage.core.errors import LineageError
from lineage.domain.memory import schema as memory_schema

_ROOT = Path(__file__).resolve().parents[3]
_SAFE = 9007199254740991
_ID = {'type': 'string', 'minLength': 8, 'maxLength': 64,
       'pattern': r'^[A-Za-z0-9_-]{8,64}(?![\s\S])'}
_AGENT = {'type': 'string', 'minLength': 3, 'maxLength': 64,
          'pattern': r'^[a-z][a-z0-9-]{2,63}(?![\s\S])'}


def _object(properties, required=None):
    return {'type': 'object', 'properties': properties,
            'required': list(properties) if required is None else required,
            'additionalProperties': False}


@lru_cache(maxsize=16)
def _definition(name):
    return memory_schema._STORE.load(name)


def _check(value, definition):
    """Compose bundled assertions over the integrated strict scalar validator.

    This local facade also handles oneOf and exclusive bounds, absent from the
    installed schema facade. It never modifies a shared validator or descriptor.
    """
    if type(definition) is bool:
        if not definition:
            raise schema.SchemaError('false_schema')
        return
    simple = {k: v for k, v in definition.items() if k in schema._KEYWORDS}
    if 'properties' in simple:
        simple['properties'] = dict.fromkeys(simple['properties'], {})
    if 'items' in simple:
        simple['items'] = {}
    memory_schema._native_validate(value, simple)
    if '$ref' in definition:
        _check(value, _definition(definition['$ref']))
    if isinstance(value, dict):
        for key, child in definition.get('properties', {}).items():
            if key in value:
                _check(value[key], child)
    if isinstance(value, list) and 'items' in definition:
        for child in value:
            _check(child, definition['items'])
    if 'exclusiveMinimum' in definition and value <= definition['exclusiveMinimum']:
        raise schema.SchemaError('exclusiveMinimum')
    if 'exclusiveMaximum' in definition and value >= definition['exclusiveMaximum']:
        raise schema.SchemaError('exclusiveMaximum')
    for child in definition.get('allOf', ()):
        _check(value, child)
    def matches(child):
        try:
            _check(value, child)
            return True
        except schema.SchemaError:
            return False
    for keyword in ('anyOf', 'oneOf'):
        if keyword in definition:
            count = sum(matches(child) for child in definition[keyword])
            if count == 0 or keyword == 'oneOf' and count != 1:
                raise schema.SchemaError(keyword)
    if 'if' in definition:
        branch = 'then' if matches(definition['if']) else 'else'
        if branch in definition:
            _check(value, definition[branch])
    if 'not' in definition and matches(definition['not']):
        raise schema.SchemaError('not')


def _validate(value, definition):
    try:
        memory_schema._native_validate(value, {})
        _check(value, definition)
    except (schema.SchemaError, TypeError, ValueError, OverflowError, RecursionError):
        raise LineageError('bad_args', 'invalid arena value') from None


def _canonical(value):
    _validate(value, {})
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _decode(raw, *, max_bytes=1048576):
    try:
        if type(raw) is not bytes or len(raw) > max_bytes:
            raise ValueError
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError
                result[key] = value
            return result
        def constant(value):
            raise ValueError
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=constant)
        _validate(value, {})
        return value
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise LineageError('bad_args', 'invalid strict arena JSON') from None


def _context(ctx, *, actor=None):
    services = getattr(ctx, 'services', None)
    if services is None:
        services = SimpleNamespace(home=ctx.home, repo_root=_ROOT,
            registry=registry.Registry({}, ctx.validators, ctx.folds),
            clock=getattr(ctx, 'clock', None), id_factory=getattr(ctx, 'id_factory', None),
            token_count=None)
    return SimpleNamespace(services=services,
        actor=(getattr(ctx, 'actor', None) or 'system') if actor is None else actor,
        authority='tool', transport=getattr(ctx, 'transport', 'library'))


def _read(root, relative, *, maximum=1048576, code='hash_mismatch'):
    """Pin every component without following links, including the final file."""
    descriptors = []
    try:
        parts = relative.split('/')
        if any(p in ('', '.', '..') for p in parts):
            raise OSError
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        for i, part in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if i < len(parts) - 1:
                flags |= os.O_DIRECTORY
            fd = os.open(part, flags, dir_fd=fd)
            descriptors.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            raise OSError
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, min(65536, maximum + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum:
                raise OSError
        after = os.fstat(fd)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if fields(before) != fields(after):
            raise OSError
        return b''.join(chunks)
    except (OSError, TypeError, ValueError):
        raise LineageError(code, 'arena artifact unavailable or changed') from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _bank_shape():
    outcome = _definition('run.schema.json')['properties']['outcome']
    task = _object({'id': _ID, 'split': {'enum': ['select', 'heldout']},
        'kind': {'type': 'string', 'minLength': 1, 'maxLength': 64},
        'language': {'type': 'string', 'minLength': 1, 'maxLength': 64},
        'prompt': {'type': 'string', 'minLength': 1, 'maxLength': 65536},
        'expected': _object({'baseline': outcome, 'candidate': outcome})})
    return _object({'schema': {'const': 'lineage.bank/v1'}, 'bank_id': _AGENT,
                    'tasks': {'type': 'array', 'items': task, 'maxItems': 1000000}})


def _validate_bank(bank):
    _validate(bank, _bank_shape())
    if len({t['id'] for t in bank['tasks']}) != len(bank['tasks']):
        raise LineageError('bad_args', 'duplicate bank task identity')


def load(bank_id: str, *, ctx) -> dict:
    _validate(bank_id, _AGENT)
    root = _context(ctx).services.repo_root
    prefix = 'arena/banks/' + bank_id + '/'
    manifest = _read(root, prefix + 'MANIFEST.sha256')
    match = re.fullmatch(rb'([0-9a-f]{64})  bank\.json\n', manifest)
    if match is None:
        raise LineageError('hash_mismatch', 'invalid bank manifest')
    raw = _read(root, prefix + 'bank.json')
    if hashlib.sha256(raw).hexdigest() != match[1].decode('ascii'):
        raise LineageError('hash_mismatch', 'bank manifest digest differs')
    bank = _decode(raw)
    _validate_bank(bank)
    if bank['bank_id'] != bank_id:
        raise LineageError('hash_mismatch', 'bank identity differs')
    return deepcopy(bank)


def verify(bank: dict, expected_sha256: str) -> None:
    _validate_bank(bank)
    if (type(expected_sha256) is not str or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None
            or _digest(bank) != expected_sha256):
        raise LineageError('hash_mismatch', 'canonical bank digest differs')


def tasks(bank: dict, *, purpose: str) -> tuple[dict, ...]:
    _validate_bank(bank)
    if purpose not in ('select', 'confirm'):
        raise LineageError('bad_args', 'invalid benchmark purpose')
    split = 'select' if purpose == 'select' else 'heldout'
    chosen = tuple(deepcopy(task) for task in bank['tasks'] if task['split'] == split)
    if not chosen:
        raise LineageError('bad_args', 'eligible bank split is empty')
    return chosen
