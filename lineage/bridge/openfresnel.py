"""OpenFresnel admission and configuration boundary.

Receiver publication and affirmative decoding remain closed until an authoritative
command, receipt-data and stdin carrier contract is supplied. No guessed wire
format is emitted. See docs/OPENFRESNEL.md for the compatibility gates.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
from typing import Any

from lineage.core.app import CallContext as Context
from lineage.core import envelope as family
from lineage.core.errors import LineageError
from lineage.core.schema import strict_loads, validate, MAX_JSON_BYTES

JSONObject = dict[str, Any]
Data = JSONObject
_TOOL_LIMIT = 1048576  # [TARGET: U20 M3/M11]
_FAMILY_LIMIT = 65536  # [CITED: K0 family contract]
_ENV = 'LINEAGE_OPENFRESNEL_COMMANDS_DIR'
_AGENT = {'type': 'string', 'minLength': 3, 'maxLength': 64,
          'pattern': r'^[a-z][a-z0-9-]{2,63}(?![\s\S])'}
_OP = {'type': 'string', 'minLength': 1, 'maxLength': 128,
       'pattern': r'^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\s\S])'}
_PATH = {'type': 'string', 'minLength': 1, 'maxLength': 4096}
_COMMON = {'commands_dir': _PATH, 'contract_file': _PATH,
           'timeout_ms': {'type': 'integer', 'minimum': 1, 'maximum': 60000},
           'agent': _AGENT, 'op_id': _OP}


def argument_schema(tool: str) -> JSONObject:
    """Return a detached, exact K0 descriptor without import-time file I/O."""
    properties = deepcopy(_COMMON)
    required = ['agent', 'op_id']
    if tool == 'openfresnel_spawn':
        properties.update(mode={'enum': ['json', 'drain']}, endpoint={
            'type': 'string', 'minLength': 1, 'maxLength': 64,
            'pattern': r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}(?![\s\S])'},
            envelope={'$ref': 'family_envelope.schema.json'})
        required.insert(0, 'mode')
    elif tool != 'openfresnel_probe':
        raise LineageError('bad_args', 'Unknown bridge operation')
    return {'type': 'object', 'properties': properties, 'required': required,
            'additionalProperties': False}


@dataclass(frozen=True)
class Command:
    tool: str
    args: JSONObject
    agent: str
    op_id: str
    expected_head: int | None = None


def _bad() -> LineageError:
    return LineageError('bad_args', 'Invalid bridge arguments or configuration')


def _path(value: Any) -> str:
    try:
        if (type(value) is not str or not 1 <= len(value) <= 4096
                or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise ValueError
        value.encode('utf-8')
        return value
    except (ValueError, UnicodeError):
        raise _bad() from None


def _identity(info):
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


@contextmanager
def _safe_open(text: str, *, directory: bool):
    """Walk lexical components through retained no-follow parent descriptors.

    In particular, an ancestor preceding '..' must be checked before any lexical
    normalization. Recheck every named inode before and after use.
    """
    text = _path(text)
    descriptors = []
    links = []
    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        root = os.sep if os.path.isabs(text) else '.'
        parent = os.open(root, flags | os.O_DIRECTORY)
        descriptors.append(parent)
        parts = [p for p in text.split(os.sep) if p and p != '.']
        for index, name in enumerate(parts):
            want_dir = directory or index < len(parts) - 1
            fd = os.open(name, flags | (os.O_DIRECTORY if want_dir else 0), dir_fd=parent)
            descriptors.append(fd)
            info = os.fstat(fd)
            if not (stat.S_ISDIR(info.st_mode) if want_dir else stat.S_ISREG(info.st_mode)):
                raise _bad()
            links.append((parent, name, _identity(info)))
            parent = fd
        if not directory and not parts:
            raise _bad()

        def check():
            for base, name, expected in links:
                if _identity(os.stat(name, dir_fd=base, follow_symlinks=False)) != expected:
                    raise _bad()
        check()
        yield parent
        check()
    except (OSError, ValueError, TypeError, RuntimeError):
        raise _bad() from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _decode_contract(raw: bytes) -> JSONObject:
    """Adapt the integrated decoder's smaller cap without relaxing JSON checks."""
    try:
        if len(raw) > _TOOL_LIMIT:
            raise ValueError
        if len(raw) <= MAX_JSON_BYTES:
            value = strict_loads(raw)
        else:
            def pairs(items):
                result = {}
                for key, item in items:
                    if key in result:
                        raise ValueError
                    result[key] = item
                return result
            def constant(_):
                raise ValueError
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                               parse_constant=constant)
            validate(value, {})
        family.canonical(value)
        if type(value) is not dict:
            raise ValueError
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise _bad() from None


def commands_dir(*, commands_dir: str | None = None,
                 contract_file: str | None = None) -> Path:
    if commands_dir is not None:
        selected = _path(commands_dir)
    elif _ENV in os.environ:
        selected = _path(os.environ[_ENV])
    elif contract_file is not None:
        with _safe_open(_path(contract_file), directory=False) as fd:
            if os.fstat(fd).st_size > _TOOL_LIMIT:
                raise _bad()
            chunks = bytearray()
            while len(chunks) <= _TOOL_LIMIT:
                chunk = os.read(fd, min(65536, _TOOL_LIMIT + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
            value = _decode_contract(bytes(chunks))
        paths = value.get('paths')
        if type(paths) is not dict:
            raise _bad()
        selected = _path(paths.get('commands_dir'))
        if not os.path.isabs(selected):
            raise _bad()
    else:
        raise _bad()
    with _safe_open(selected, directory=True):
        return Path(os.path.abspath(selected))


def validated_args(tool: str, args: JSONObject, *, ctx: Context) -> JSONObject:
    """Validate closed outer arguments and the full U05 nested envelope.

    The integrated structural validator cannot resolve references. Its outer
    check is composed with the actual U05 frozen-schema validation, preserving
    the exact discovery descriptor and all nested assertions.
    """
    try:
        raw = family.canonical(args)
        if len(raw) > _TOOL_LIMIT or type(args) is not dict:
            raise ValueError
        shape = argument_schema(tool)
        outer = dict(args)
        if tool == 'openfresnel_spawn':
            shape['properties'].pop('envelope')
            nested = outer.pop('envelope', None)
            mode = outer.get('mode')
            if mode == 'json':
                if 'envelope' not in args or 'endpoint' in args:
                    raise ValueError
                encoded = family.canonical(nested)
                if len(encoded) > _FAMILY_LIMIT or type(nested) is not dict:
                    raise ValueError
                family.validate(encoded, nested.get('target'))
            elif mode == 'drain':
                if 'endpoint' not in args or 'envelope' in args:
                    raise ValueError
            else:
                raise ValueError
        validate(outer, shape)
        for key in ('commands_dir', 'contract_file'):
            if key in args:
                _path(args[key])
        if ((ctx.actor is not None and ctx.actor != args['agent'])
                or (ctx.op_id is not None and ctx.op_id != args['op_id'])):
            raise ValueError
        effective = deepcopy(args)
        effective.setdefault('timeout_ms', 20000)
        return effective
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
        raise _bad() from None


def _admit(command: Command, tool: str, supplied: JSONObject, ctx: Context) -> None:
    if (not isinstance(command, Command) or command.tool != tool
            or command.expected_head is not None):
        raise _bad()
    effective = validated_args(tool, command.args, ctx=ctx)
    if command.agent != effective['agent'] or command.op_id != effective['op_id']:
        raise _bad()
    actual = {'agent': command.agent, 'op_id': command.op_id, **supplied}
    if validated_args(tool, actual, ctx=ctx) != effective:
        raise _bad()


def _binding_refusal(selected: str | None, contract: str | None) -> Data:
    # Establish configuration safety first, without creating or opening any
    # publication entry. An unknown ABI cannot safely distinguish retained
    # requests, unrelated files or old acknowledgements.
    commands_dir(commands_dir=selected, contract_file=contract)
    raise LineageError('internal', 'Receiver command and receipt binding AUSENTE; publication refused')


def probe(*, commands_dir: str | None = None, contract_file: str | None = None,
          timeout_ms: int = 20000, command: Command, ctx: Context) -> Data:
    supplied = {'timeout_ms': timeout_ms}
    if commands_dir is not None:
        supplied['commands_dir'] = commands_dir
    if contract_file is not None:
        supplied['contract_file'] = contract_file
    _admit(command, 'openfresnel_probe', supplied, ctx)
    return _binding_refusal(commands_dir, contract_file)


def spawn(mode: str, *, endpoint: str | None = None,
          envelope: JSONObject | None = None, commands_dir: str | None = None,
          contract_file: str | None = None, timeout_ms: int = 20000,
          command: Command, ctx: Context) -> Data:
    supplied = {'mode': mode, 'timeout_ms': timeout_ms}
    for key, value in (('endpoint', endpoint), ('envelope', envelope),
                       ('commands_dir', commands_dir), ('contract_file', contract_file)):
        if value is not None:
            supplied[key] = value
    _admit(command, 'openfresnel_spawn', supplied, ctx)
    return _binding_refusal(commands_dir, contract_file)


def parse_receipt(value: JSONObject, *, rid: str, op: str) -> JSONObject:
    """Pure strict refusal until operation-data nesting has a source contract.

    Known discriminators/correlation are necessary, never sufficient evidence.
    Remote error text is discarded, so paths, secrets and instructions cannot
    become diagnostics or executable content.
    """
    try:
        raw = family.canonical(value)
        if len(raw) > _TOOL_LIMIT or type(value) is not dict:
            raise ValueError
        if type(rid) is not str or op not in ('capabilities', 'spawn_terminal'):
            raise ValueError
        if 'status' in value:
            if ('ok' in value or 'api_version' in value
                    or value['status'] not in ('ok', 'accepted', 'error')):
                raise ValueError
        elif (type(value.get('ok')) is not bool
              or type(value.get('api_version')) is not int
              or value['api_version'] != 2):
            raise ValueError
        if value.get('request_id') != rid or value.get('op') != op:
            raise ValueError
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise LineageError('internal', 'Invalid or unsupported receiver receipt') from None
    raise LineageError('internal', 'Receiver operation data binding AUSENTE; receipt refused')
