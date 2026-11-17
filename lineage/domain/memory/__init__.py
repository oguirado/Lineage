"""Receipt-backed memory and adapters for the installed headless core.

The installed journal has a payload preparation callback and returns events.
These adapters retain that implementation's locking, replay, hashing and fsync;
K0 snapshots, callback rendering and extension metadata are composed around it.
Legacy callers retain the installed signatures and behavior.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import wraps
import hashlib
import importlib
from pathlib import Path
import secrets
import stat
import time
from typing import Any

from lineage.core import journal as _journal, registry as _registry
from lineage.core.errors import LineageError


@dataclass(frozen=True)
class _Services:
    home: Path
    repo_root: Path
    registry: Any
    clock: Any = None
    id_factory: Any = None
    token_count: Any = None


@dataclass(frozen=True)
class _Context:
    services: _Services
    actor: str = 'system'
    authority: str = 'tool'
    transport: str = 'library'


@dataclass(frozen=True)
class _Command:
    tool: str
    args: dict
    agent: str
    op_id: str
    expected_head: int | None = None


@dataclass(frozen=True)
class _EventDraft:
    kind: str
    payload: dict


@dataclass(frozen=True)
class _Snapshot:
    events: tuple
    state: dict
    head: int
    sha256: str | None


@dataclass(frozen=True)
class _Committed:
    event: dict
    head: int
    sha256: str
    value: dict


@dataclass(frozen=True)
class _FoldSpec:
    kinds: frozenset
    order: int
    apply: Any

    def __call__(self, state, event):
        if event['kind'] in self.kinds:
            return self.apply(state, event)


# A-INT1: preserve the integrated dataclass identity and native constructors.
# Only K0's positional (effect, handler) form needs translation; native tools
# keep their exact fields and handlers, including through Registry's copies.
_native_tool = _registry.ToolSpec
_native_tool_init = getattr(_native_tool.__init__, '_lineage_native', _native_tool.__init__)


@wraps(_native_tool_init)
def _tool_init(self, name, description, input_schema, handler, mutating):
    if isinstance(handler, str) and callable(mutating):
        effect, handler, mutating = handler, mutating, handler == 'journal'
        _native_tool_init(self, name, description, input_schema, handler, mutating)
        object.__setattr__(self, '_contract', True)
        object.__setattr__(self, 'effect', effect)
    else:
        _native_tool_init(self, name, description, input_schema, handler, mutating)


_tool_init._lineage_native = _native_tool_init


def _native(function):
    return getattr(function, '_lineage_native', function)


_native_transact = _native(_journal.transact)
_native_snapshot = _native(_journal.snapshot)
_native_verify = _native(_journal.verify)


def _fold(events, *, registry):
    state = {'memory': {}, 'agents': {}, 'runs': {}}
    ordered = sorted(registry.folds.items(), key=lambda pair: (getattr(pair[1], 'order', 0), pair[0]))
    for event in events:
        for _, callback in ordered:
            if isinstance(callback, _FoldSpec):
                if event['kind'] in callback.kinds:
                    callback.apply(state, deepcopy(event))
            else:
                callback(state, deepcopy(event))
    return state


def _snapshot_of(events, ctx):
    events = deepcopy(tuple(events))
    return _Snapshot(events, _fold(events, registry=ctx.services.registry),
                     events[-1]['lamport'] if events else 0,
                     hashlib.sha256(_journal.canonical_bytes(events[-1]) + b'\n').hexdigest() if events else None)


def _snapshot(*args, ctx=None, **kwargs):
    if ctx is None:
        return _native_snapshot(*args, **kwargs)
    # The installed journal returns an empty prefix even for a missing home.
    # Empty memory is valid only for an established runtime directory.
    try:
        if not stat.S_ISDIR(Path(ctx.services.home).stat().st_mode):
            raise NotADirectoryError
    except OSError:
        raise LineageError('internal', 'authoritative journal unavailable') from None
    try:
        events = _native_snapshot(ctx.services.home)
    except LineageError as exc:
        # Only a completely uninitialized ledger is an established empty home.
        if exc.code != 'internal':
            raise LineageError('internal', 'authoritative journal unavailable') from None
        home = Path(ctx.services.home)
        try:
            if not stat.S_ISDIR(home.stat().st_mode):
                raise NotADirectoryError
        except OSError:
            raise LineageError('internal', 'authoritative journal unavailable') from None
        try:
            (home / 'ledger').stat()
        except FileNotFoundError:
            events = ()
        except OSError:
            raise LineageError('internal', 'authoritative journal unavailable') from None
        else:
            raise LineageError('internal', 'authoritative journal unavailable') from None
    return _snapshot_of(events, ctx)


def _effective(command):
    args = deepcopy(command.args)
    args.pop('op_id', None)
    args.pop('expected_head', None)
    return {'tool': command.tool, 'args': args}


def _transact(*args, ctx=None, **kwargs):
    if ctx is None:
        return _native_transact(*args, **kwargs)
    command, prepare, render = args
    from . import schema
    if command.agent != ctx.actor:
        raise LineageError('conflict', 'command actor mismatch')
    if command.expected_head is not None and (type(command.expected_head) is not int or not 0 <= command.expected_head <= schema.SAFE):
        raise LineageError('bad_args', 'invalid expected head')
    registry = ctx.services.registry
    kind = getattr(prepare, 'kind', None) or {'memory_put': 'memory.put', 'operator_ruling': 'memory.put'}.get(command.tool)
    if kind is None and command.tool in registry.validators:
        kind = command.tool
    if kind is None:
        # Native U03 requires a kind before entering its transaction. Plain K0
        # callbacks may provide it through their draft; preparation is repeated
        # against the locked prefix and all admission remains under that lock.
        inferred = prepare(_snapshot(ctx=ctx))
        if not isinstance(inferred, _EventDraft):
            raise LineageError('bad_args', 'event kind unavailable')
        kind = inferred.kind
    expected_payload = getattr(prepare, 'expected_payload', None)
    rendered = []

    def prepared(history, draft):
        current = _snapshot_of(history, ctx)
        if command.expected_head is not None and command.expected_head != current.head:
            raise LineageError('stale_rev', 'expected head differs')
        result = prepare(current)
        if not isinstance(result, _EventDraft) or result.kind != kind:
            raise LineageError('internal', 'invalid prepared event')
        return deepcopy(result.payload)

    def validate(history, event):
        validator = registry.validators.get(kind)
        if not callable(validator):
            raise LineageError('bad_args', 'event validator unavailable')
        before = _snapshot_of(history, ctx)
        validator(before, event, ctx)
        candidate = _snapshot_of((*history, event), ctx)
        data = render(candidate, event)
        _journal.canonical_bytes(data)
        rendered.append(deepcopy(data))

    event = _native_transact(ctx.services.home, agent=command.agent, op_id=command.op_id,
                             kind=kind, payload=_effective(command), validators={kind: validate},
                             prepare=prepared, clock=ctx.services.clock, id_factory=ctx.services.id_factory)
    if rendered:
        data = rendered[0]
    else:
        if (event['kind'] != kind or (expected_payload is not None
                and event['payload'] != expected_payload)):
            raise LineageError('bad_op', 'operation payload differs')
        # Native U03 recognized a replay before admission. Render only the
        # original committed prefix, never the later current state.
        history = _native_snapshot(ctx.services.home)
        prefix = tuple(item for item in history if item['lamport'] <= event['lamport'])
        data = render(_snapshot_of(prefix, ctx), deepcopy(event))
        _journal.canonical_bytes(data)
    return _Committed(deepcopy(event), event['lamport'], event['sha256'], deepcopy(data))


def _append(draft, *, command, render, ctx):
    def prepare(snapshot):
        return deepcopy(draft)
    prepare.kind = draft.kind
    prepare.expected_payload = deepcopy(draft.payload)
    return _journal.transact(command, prepare, render, ctx=ctx)


def _verify(*args, ctx=None, projections=True, **kwargs):
    if ctx is None:
        return _native_verify(*args, **kwargs)
    report = _native_verify(ctx.services.home, **kwargs)
    return {'valid': report['ok'], 'head': report['head'], 'sha256': report['head_sha256'],
            'torn_tail_bytes': report['torn_tail']['byte_length'] if report['torn_tail'] else 0,
            'issues': deepcopy(report['errors'])}


# A-INT1: introspection continues to describe each integrated native API.
for _adapter, _original in ((_snapshot, _native_snapshot),
                             (_transact, _native_transact), (_verify, _native_verify)):
    wraps(_original)(_adapter)
    _adapter._lineage_native = _original


def _install():
    """Install the dual-call facade once per provider generation, never ToolSpec."""
    for name, value in {'Services': _Services, 'Context': _Context, 'Command': _Command,
                        'EventDraft': _EventDraft, 'Snapshot': _Snapshot, 'Committed': _Committed,
                        'FoldSpec': _FoldSpec}.items():
        setattr(_registry, name, value)
    if _native_tool.__init__ is _native_tool_init:
        _native_tool.__init__ = _tool_init
    _journal.transact = _transact
    _journal.snapshot = _snapshot
    _journal.append = _append
    _journal.fold = _fold
    _journal.verify = _verify

    original_error = _native(_registry.RegistryError)
    class RegistryError(original_error, LineageError):
        _lineage_native = original_error

        def __init__(self, reason, *, name=None):
            LineageError.__init__(self, 'bad_args', {'reason': reason})
            if name is not None:
                self.detail['name'] = name
    if _registry.RegistryError is original_error:
        _registry.RegistryError = RegistryError
    original_descriptor = _native(_registry._descriptor)

    @wraps(original_descriptor)
    def descriptor(spec):
        if isinstance(spec, _native_tool) and getattr(spec, '_contract', False):
            if spec.effect not in {'read', 'journal'}:
                raise _registry.RegistryError('bad_descriptor')
            original_descriptor(_native_tool(spec.name, spec.description, {'type': 'object'},
                                               spec.handler, spec.mutating))
            from .schema import _preflight, _STORE
            try:
                _preflight(spec.input_schema, _STORE)
            except Exception:
                raise _registry.RegistryError('bad_schema', name=spec.name) from None
        else:
            original_descriptor(spec)
    descriptor._lineage_native = original_descriptor
    if _registry._descriptor is original_descriptor:
        _registry._descriptor = descriptor

    from lineage.core import app, mcp
    native_dispatch, native_mcp = _native(app.dispatch), _native(mcp.main)

    @wraps(native_dispatch)
    def dispatch(name, args, *, ctx=None, context=None, registry=None):
        direct = ctx is not None
        chosen = ctx.services.registry if direct else (registry or getattr(context, 'registry', None))
        if not direct and chosen is None:
            # Native CallContext carries validator/fold maps, but no registry.
            # Resolve discovery only when the caller did not supply one.
            try:
                chosen = _registry.load()
            except Exception:
                return app.DispatchResult({'ok': False, 'code': 'internal'}, 'execution')
            if isinstance(context, app.CallContext):
                if (context.validators != chosen.validators or context.folds != chosen.folds):
                    return app.DispatchResult({'ok': False, 'code': 'bad_args'}, 'configuration')
                context = replace(context, validators=chosen.validators, folds=chosen.folds)
        if not direct and context is None:
            try:
                context = app.create_context(registry=chosen)
            except app.ToolError as exc:
                return app.DispatchResult({'ok': False, 'code': exc.code}, 'request')
        tool = chosen.tools.get(name) if isinstance(name, str) else None
        is_contract = tool is not None and getattr(tool.handler, '_memory_contract', False)
        if not is_contract:
            if direct:
                context = app.create_context(ctx.services.home, registry=chosen,
                                             actor=ctx.actor)
            result = native_dispatch(name, args, context=context, registry=chosen)
            return result.payload if direct else result
        if (not direct and isinstance(context, app.CallContext)
                and (context.validators is not chosen.validators
                     or context.folds is not chosen.folds)):
            return app.DispatchResult({'ok': False, 'code': 'bad_args'}, 'configuration')
        if ctx is None:
            ctx = _Context(_Services(context.home, Path(__file__).resolve().parents[3], chosen,
                                     clock=getattr(context, 'clock', None),
                                     id_factory=getattr(context, 'id_factory', None),
                                     token_count=getattr(context, 'token_count', None)))
        from . import schema
        failure = None
        try:
            if tool is None or type(args) is not dict:
                raise LineageError('bad_args', 'invalid tool arguments')
            effective = deepcopy(args)
            if not tool.mutating and 'agent' in tool.input_schema.get('properties', {}):
                effective.setdefault('agent', 'system')
            if name == 'memory_history':
                effective.setdefault('after', 0)
                effective.setdefault('limit', 100)
            try:
                schema._validate(effective, tool.input_schema, store=schema._STORE)
            except schema.boundary.SchemaError:
                raise LineageError('bad_args', 'invalid tool arguments') from None
        except LineageError as exc:
            payload, failure = {'ok': False, 'code': exc.code}, 'request'
        else:
            try:
                effective_ctx = replace(ctx, actor=effective.get('agent', ctx.actor), authority='tool')
                data = tool.handler(effective, effective_ctx)
                _journal.canonical_bytes(data)
                payload = {'untrusted': deepcopy(data)}
            except LineageError as exc:
                payload, failure = {'ok': False, 'code': exc.code}, 'execution'
                if isinstance(exc.detail, str):
                    # Domain diagnostics are fixed, bounded strings.
                    payload['detail'] = exc.detail[:2048]
            except Exception:
                payload, failure = {'ok': False, 'code': 'internal'}, 'execution'
        return payload if direct else app.DispatchResult(payload, failure)
    dispatch._lineage_native = native_dispatch
    if app.dispatch is native_dispatch:
        app.dispatch = dispatch

    @wraps(native_mcp)
    def mcp_main(*args, context=None, registry=None, **kwargs):
        if len(args) > 2:
            raise TypeError('expected at most stdin and stdout')
        for name, stream in zip(('stdin', 'stdout'), args):
            if name in kwargs:
                raise TypeError('multiple values for ' + name)
            kwargs[name] = stream
        if context is None and registry is None:
            registry = _registry.load()
            context = app.create_context(registry=registry)
            # Freeze a native registry snapshot so the installed adapter's
            # type/identity boundary remains intact.
            registry = _registry.Registry(registry.tools, registry.validators, registry.folds)
            context = app.create_context(context.home, registry=registry)
        elif context is None:
            context = app.create_context(registry=registry)
        return native_mcp(context=context, registry=registry, **kwargs)
    mcp_main._lineage_native = native_mcp
    if mcp.main is native_mcp:
        mcp.main = mcp_main
    global _transport_main
    _transport_main = mcp.main


def _ensure_transport():
    # A host may reload its transport module. Reapply only our optional-default
    # adapter; do not replace independently injected dispatch implementations.
    from lineage.core import mcp
    if not hasattr(mcp.main, '_lineage_native'):
        _install()


_install()  # A-INT1: native identities and signatures survive K0 installation.
