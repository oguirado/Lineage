"""Memory schema admission over the installed strict JSON primitives."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import hashlib
import os
import stat

from lineage.core import schema as boundary
from lineage.core.errors import LineageError
from lineage.core.journal import canonical_bytes

_native_validate = boundary.validate
_ROOT = Path(__file__).resolve().parents[3]
SAFE = 9007199254740991


class _SchemaStore:
    """Confined, bundled schema access; references never fetch remote content."""
    def __init__(self, root):
        self.root = Path(root)

    def load(self, name):
        return deepcopy(self._load(name))

    @lru_cache(maxsize=16)
    def _load(self, name):
        if not isinstance(name, str) or Path(name).name != name or not name.endswith('.schema.json'):
            raise LineageError('bad_args', 'invalid bundled schema reference')
        try:
            return boundary.strict_loads((self.root / name).read_bytes())
        except Exception:
            raise LineageError('internal', 'bundled schema unavailable') from None


_STORE = _SchemaStore(_ROOT / 'schemas')


def _matches(value, definition, store, base):
    try:
        _check(value, definition, store, base)
    except boundary.SchemaError:
        return False
    return True


def _check(value, definition, store, base):
    # Compose the frozen schema's conditionals from U02 assertions. No alternate
    # JSON decoder, native-memory aliases or remotely resolved schemas are used.
    allowed = set(boundary._KEYWORDS) | {'$ref', 'allOf', 'anyOf', 'if', 'then', 'else', 'not'}
    if type(definition) is not dict or set(definition) - allowed:
        raise boundary.SchemaError('invalid_schema', schema_pointer='')
    simple = {k: v for k, v in definition.items() if k in boundary._KEYWORDS}
    if 'properties' in simple:
        simple['properties'] = {key: {} for key in simple['properties']}
    if 'items' in simple:
        simple['items'] = {}
    _native_validate(value, simple)
    if '$ref' in definition:
        reference = definition['$ref']
        _check(value, store.load(reference), store, reference)
    if isinstance(value, dict):
        for key, child in definition.get('properties', {}).items():
            if key in value:
                _check(value[key], child, store, base)
    if isinstance(value, list) and 'items' in definition:
        for item in value:
            _check(item, definition['items'], store, base)
    for child in definition.get('allOf', ()):
        _check(value, child, store, base)
    if 'anyOf' in definition and not any(_matches(value, child, store, base) for child in definition['anyOf']):
        raise boundary.SchemaError('any_of')
    if 'if' in definition:
        branch = 'then' if _matches(value, definition['if'], store, base) else 'else'
        if branch in definition:
            _check(value, definition[branch], store, base)
    if 'not' in definition and _matches(value, definition['not'], store, base):
        raise boundary.SchemaError('not')


def _validate(value, definition, *, store=None, base=None):
    if store is None:
        return _native_validate(value, definition)
    _native_validate(value, {})
    return _check(value, definition, store, base)


def _decode(raw):
    try:
        return boundary.strict_loads(raw)
    except boundary.SchemaError:
        raise LineageError('bad_args', 'invalid strict JSON') from None


def _shape(value, name):
    try:
        _validate(value, _STORE.load(name), store=_STORE, base=name)
    except boundary.SchemaError:
        raise LineageError('bad_args', 'invalid record shape') from None


def _coordinate(path):
    if (type(path) is not str or not path or '\x00' in path or '\\' in path or path.startswith('/')
            or any(part in ('', '.', '..') for part in path.split('/'))):
        raise LineageError('bad_args', 'invalid evidence coordinate')


def _evidence(receipt, ctx):
    """Walk using pinned directory descriptors and never follow a symlink."""
    _coordinate(receipt['path'])
    descriptors = []
    try:
        home = Path(ctx.services.home)
        fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        parts = receipt['path'].split('/')
        for part in parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        source = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        descriptors.append(source)
        before = os.fstat(source)
        if not stat.S_ISREG(before.st_mode):
            raise OSError
        digest = hashlib.sha256()
        while True:
            chunk = os.read(source, 65536)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(source)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise OSError
        if digest.hexdigest() != receipt['sha256']:
            raise OSError
    except (OSError, ValueError, TypeError):
        raise LineageError('hash_mismatch', 'evidence unavailable or digest mismatch') from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def validate_unit(unit, *, authority, actor, ctx):
    _sync_boundary()
    _shape(unit, 'mem_unit.schema.json')
    if unit['level'] == 1 and not (
            authority == 'operator' and actor == 'operator'
            and ctx.authority == 'operator' and ctx.actor == 'operator'):
        raise LineageError('forbidden_level', 'operator authority required')
    if unit['kind'] == 'workflow' and unit['body']['stats']['successes'] > unit['body']['stats']['runs']:
        raise LineageError('bad_args', 'successes exceed runs')
    for receipt in unit['receipts']:
        _coordinate(receipt['path'])
    if len(canonical_bytes(unit)) > 6000:
        raise LineageError('memory_debt', 'cuts: unit byte capacity exceeded')
    for receipt in unit['receipts']:
        _evidence(receipt, ctx)


# The integrated U02 exposes strict_loads/validate, rather than the K0 store
# facade. Keep its existing two-argument validation behavior unchanged.
if not hasattr(boundary, 'SchemaStore'):
    boundary.SchemaStore = _SchemaStore
    boundary.decode = _decode
    boundary.canonical = canonical_bytes
    boundary.validate = _validate


def _preflight(definition, store):
    """Validate every bundled assertion even in an unselected conditional."""
    allowed = set(boundary._KEYWORDS) | {'$ref', 'allOf', 'anyOf', 'if', 'then', 'else', 'not'}
    if type(definition) is not dict or set(definition) - allowed:
        raise boundary.SchemaError('invalid_schema', schema_pointer='')
    simple = {key: value for key, value in definition.items() if key in boundary._KEYWORDS}
    if 'properties' in simple:
        if type(simple['properties']) is not dict:
            raise boundary.SchemaError('invalid_schema', schema_pointer='')
        simple['properties'] = {key: {} for key in simple['properties']}
    if 'items' in simple:
        simple['items'] = {}
    try:
        _native_validate(None, simple)
    except boundary.SchemaError as exc:
        if exc.schema_pointer is not None:
            raise
    for key in ('properties',):
        for child in definition.get(key, {}).values():
            _preflight(child, store)
    for key in ('items', 'if', 'then', 'else', 'not'):
        if key in definition:
            _preflight(definition[key], store)
    for key in ('allOf', 'anyOf'):
        if key in definition:
            if type(definition[key]) is not list or not definition[key]:
                raise boundary.SchemaError('invalid_schema', schema_pointer='')
            for child in definition[key]:
                _preflight(child, store)
    if '$ref' in definition:
        reference = definition['$ref']
        if (type(reference) is not str or Path(reference).name != reference
                or not reference.endswith('.schema.json')):
            raise boundary.SchemaError('invalid_schema', schema_pointer='')


# Preserve the installed signature for legacy introspection while accepting the
# explicit store facade. Rebind imported error classes when U02 is reloaded;
# its strict decoder and exception must always come from the same generation.
from functools import update_wrapper
update_wrapper(_validate, _native_validate)


def _sync_boundary():
    import sys
    boundary.validate = _validate
    for name in ('lineage.core.registry', 'lineage.core.app', 'lineage.core.cli', 'lineage.core.mcp'):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, 'SchemaError'):
            module.SchemaError = boundary.SchemaError
    from . import _ensure_transport
    _ensure_transport()
