"""Shared validated application boundary; domain handlers own transactions."""
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, replace
import importlib
import os
from pathlib import Path
from typing import Any, Literal

from .registry import Fold, Registry, Validator
from .schema import SchemaError, validate

ERROR_CODES = frozenset("""bad_args bad_op stale_rev busy internal conflict no_agent
no_run run_closed memory_required memory_debt forbidden_level not_inheritable
hash_mismatch rule_not_declared no_benchmark heldout_forbidden seat_not_allowed
fixture_readonly timeout""".split())


@dataclass(frozen=True)
class CallContext:
    home: Path
    validators: Mapping[str, Validator]
    folds: Mapping[str, Fold]
    actor: str | None = None
    op_id: str | None = None


@dataclass(frozen=True)
class DispatchResult:
    payload: dict[str, Any]
    failure: Literal["request", "configuration", "execution"] | None = None

    @property
    def exit_code(self) -> int:
        if self.failure is None:
            return 0
        return 3 if self.failure == "execution" else 2


class ToolError(Exception):
    def __init__(self, code: str, detail: Any = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(code)


def create_context(home: str | os.PathLike[str] | None = None, *,
                   registry: Registry, actor: str | None = None,
                   op_id: str | None = None) -> CallContext:
    chosen = home if home is not None else os.environ.get("LINEAGE_HOME", "~/.lineage")
    try:
        if os.fspath(chosen) == "":
            raise ValueError
        resolved = Path(chosen).expanduser().resolve()
    except (TypeError, ValueError, OSError, RuntimeError):
        raise ToolError("bad_args") from None
    return CallContext(resolved, registry.validators, registry.folds, actor, op_id)


def list_tools(*, registry: Registry) -> list[dict[str, Any]]:
    return [{"name": spec.name, "description": spec.description,
             "inputSchema": deepcopy(spec.input_schema),
             "annotations": annotations(spec)}
            for _, spec in sorted(registry.tools.items())]


def schema_diagnostic(exc: SchemaError) -> dict[str, Any]:
    return {"reason": exc.reason, "pointer": exc.pointer,
            "schema_pointer": exc.schema_pointer}


def _execution_error(exc: Exception) -> DispatchResult:
    recognized = isinstance(exc, ToolError)
    if not recognized:
        # U03 is an optional integration peer, never an import prerequisite.
        try:
            domain_type = importlib.import_module("lineage.core.errors").LineageError
            recognized = isinstance(exc, domain_type)
        except Exception:
            recognized = False
    payload: dict[str, Any] = {"ok": False, "code": "internal"}
    if recognized:
        try:
            if type(exc.code) is str and exc.code in ERROR_CODES:
                validate(exc.detail, {})
                payload = {"ok": False, "code": exc.code}
                if exc.detail is not None:
                    payload["detail"] = deepcopy(exc.detail)
        except Exception:
            payload = {"ok": False, "code": "internal"}
    return DispatchResult(payload, "execution")


def dispatch(name: str, args: dict[str, Any], *, context: CallContext,
             registry: Registry) -> DispatchResult:
    if type(name) is not str or name not in registry.tools:
        return DispatchResult({"ok": False, "code": "bad_args"}, "request")
    if (context.validators is not registry.validators
            or context.folds is not registry.folds):
        return DispatchResult({"ok": False, "code": "bad_args"}, "configuration")
    spec = registry.tools[name]
    try:
        if type(args) is not dict:
            raise SchemaError("type")
        # The integrated structural validator cannot resolve the bridge's
        # frozen nested family $ref; use the installed wire validator for it.
        if (name == 'openfresnel_spawn' and spec.input_schema.get('properties', {}).get(
                'envelope', {}).get('$ref') == 'family_envelope.schema.json'):
            from . import envelope
            try:
                envelope._check(args, spec.input_schema, 'family_envelope.schema.json')
            except envelope.InvalidEnvelope:
                raise SchemaError('schema_mismatch') from None
        else:
            try:
                validate(args, spec.input_schema)
            except SchemaError as exc:
                # A-APP1: frozen tool schemas may use keywords beyond the U02
                # structural subset (e.g. bench_declare's $ref to
                # bench_declared.schema.json with exclusive bounds). Only then,
                # fall back to the installed wire validator, which resolves the
                # repository schemas; the same dispatcher serves every carrier.
                if exc.reason != 'unsupported_keyword':
                    raise
                from . import envelope
                try:
                    envelope._check(args, spec.input_schema, 'event.schema.json')
                except (envelope.InvalidEnvelope, KeyError, TypeError, ValueError, RecursionError):
                    raise SchemaError('schema_mismatch') from None
        detached = deepcopy(args)
    except SchemaError as exc:
        failure = "configuration" if exc.schema_pointer is not None else "request"
        return DispatchResult({"ok": False, "code": "bad_args",
                               "detail": schema_diagnostic(exc)}, failure)
    except Exception:
        return DispatchResult({"ok": False, "code": "internal"}, "execution")
    try:
        data = spec.handler(detached, context=context)
        validate(data, {})
        return DispatchResult({"untrusted": deepcopy(data)})
    except Exception as exc:
        return _execution_error(exc)


# Transport controls are deliberately outside the frozen tool input schemas.
_RISKS = ("observe", "read", "prepare", "send", "publish", "destructive", "irreversible")
_DRY_RUN = ContextVar("lineage_dry_run", default=False)
_COMMIT_GUARD = ContextVar("lineage_commit_guard", default=None)


def annotations(spec):
    return {"readOnlyHint": spec.risk in {"observe", "read"},
            "destructiveHint": spec.risk in {"destructive", "irreversible"},
            "idempotentHint": True,
            "openWorldHint": spec.risk == "send",
            "lineage_risk": spec.risk}


class _Prepared(BaseException):
    def __init__(self, event, head):
        self.event, self.head = event, head


class _PreviewEffect(BaseException):
    pass


class _Cancelled(BaseException):
    """Transport order that domain error sanitizers must not rewrite."""


def _audit_preview(event, args):
    if not _DRY_RUN.get():
        return
    if event == 'open':
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(char in mode for char in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            raise _PreviewEffect
    if event in {'os.mkdir', 'os.remove', 'os.rmdir', 'os.rename', 'os.link',
                 'os.symlink', 'os.truncate', 'os.chmod', 'os.chown', 'os.utime',
                 'os.fork', 'os.posix_spawn', 'os.system', 'subprocess.Popen',
                 'socket.connect', 'socket.bind', 'os.kill', 'os.killpg'}:
        raise _PreviewEffect


def _enable_operable_hooks():
    # A-K0-9: memory's dual-call adapter captures the native transaction. Route
    # that captured callable, preserving its exact normal execution behavior.
    from . import journal
    from lineage.domain import memory
    original = memory._native_transact
    if not getattr(original, '_operable_preview', False):
        def transaction(*args, **kwargs):
            if _DRY_RUN.get():
                return _prepare_transaction(*args, **kwargs)
            return original(*args, **kwargs)
        transaction._operable_preview = True
        memory._native_transact = transaction
    commit = journal._commit
    if not getattr(commit, '_operable_guard', False):
        def guarded_commit(*args, **kwargs):
            guard = _COMMIT_GUARD.get()
            if guard is not None:
                try:
                    guard()
                except Exception as exc:
                    if (getattr(exc, 'code', None) == 'bad_op'
                            and getattr(exc, 'detail', None) == 'cancelled by order'):
                        raise _Cancelled from None
                    raise
            return commit(*args, **kwargs)
        guarded_commit._operable_guard = True
        journal._commit = guarded_commit
    if not getattr(_enable_operable_hooks, 'auditing', False):
        sys.addaudithook(_audit_preview)
        _enable_operable_hooks.auditing = True


def _prepare_transaction(home=None, *, agent, op_id, kind, payload, validators,
                         evidence=(), prepare=None, clock=None, id_factory=None,
                         lock_timeout_s=1.0):
    from . import journal
    from .errors import LineageError
    journal._guard()
    resolved = journal.resolve_home(home)
    journal._evidence(list(evidence))
    journal._validate_timeout(lock_timeout_s)
    if not journal._matches(journal._AGENT, agent) or not journal._matches(journal._OP, op_id):
        raise LineageError('bad_args')
    # Read mode acquires the existing stable lock, without creating an empty
    # ledger or repairing a torn suffix. Replay lookup is intentionally absent.
    with journal._authority(resolved, False, lock_timeout_s) as fd:
        raw = journal._read(fd)
        serialized = []
        report, history, _ = journal._scan(raw, True, canonical_history=serialized)
        journal._verified(report)
        request = {'ledger': 'main', 'agent': agent, 'op_id': op_id,
                   'kind': kind, 'payload': payload, 'evidence': list(evidence)}
        digest = hashlib.sha256(journal.canonical_bytes(request)).hexdigest()
        draft = {'schema': 'lineage.event/v1', 'id': 'e-' + hashlib.sha256(
                    (digest + ':' + str(report['head'])).encode()).hexdigest()[:16],
                 'lamport': report['head'] + 1,
                 'ts': clock() if clock is not None else time.time_ns() // 1_000_000,
                 **request, 'request_sha256': digest, 'prev_sha256': report['head_sha256']}
        if prepare is not None:
            draft['payload'] = journal._callback(prepare, tuple(serialized), draft)
        event = {**draft, 'sha256': hashlib.sha256(journal.canonical_bytes(draft)).hexdigest()}
        journal._envelope(event)
        callback = validators.get(kind)
        if callback is None:
            raise LineageError('bad_args')
        if journal._callback(callback, tuple(serialized), event) is not None:
            raise LineageError('internal')
        raise _Prepared(event, report['head'])


def _preview_data(spec, head, event=None):
    from .journal import canonical_bytes
    events = [] if event is None else [{
        'kind': event['kind'], 'payload_sha256': hashlib.sha256(
            canonical_bytes(event['payload'])).hexdigest(),
        'expected_head': head}]
    return {'dry_run': True, 'risk': spec.risk, 'expected_head': head, 'events': events}


def _invoke_operable(spec, original, args, positional, keywords, context):
    if not _DRY_RUN.get():
        return original(args, *positional, **keywords)
    from . import journal
    home = context.services.home if hasattr(context, 'services') else context.home
    try:
        if spec.name.startswith('openfresnel_'):
            from lineage.bridge import openfresnel
            effective = openfresnel.validated_args(spec.name, args, ctx=context)
            openfresnel.commands_dir(**{key: effective[key] for key in ('commands_dir', 'contract_file') if key in effective})
            history = journal.snapshot(home)
            head = history[-1]['lamport'] if history else 0
            return _preview_data(spec, head, {'kind': 'openfresnel.command',
                                             'payload': {'tool': spec.name, 'args': effective}})
        if spec.name == 'ledger_export':
            from . import export
            plan = export.prepare_export(home, out=args['out'])
            return _preview_data(spec, plan['head'], {'kind': 'ledger.export', 'payload': plan['payload']})
        original(args, *positional, **keywords)
        history = journal.snapshot(home)
        return _preview_data(spec, history[-1]['lamport'] if history else 0)
    except _Prepared as prepared:
        return _preview_data(spec, prepared.head, prepared.event)
    except _PreviewEffect:
        raise ToolError('bad_op', 'dry-run refused an unprepared side effect') from None


def preview(name, args, *, context, registry):
    from .registry import ToolSpec, _operable_handler
    _enable_operable_hooks()
    if (context.validators is not registry.validators or context.folds is not registry.folds):
        return DispatchResult({'ok': False, 'code': 'bad_args'}, 'configuration')
    # A private registry snapshot preserves installed handler identities and the
    # public ToolSpec constructor. The ordinary dispatcher still owns all input
    # validation, actor defaults and error classification.
    rehearsal = Registry({key: ToolSpec(spec.name, spec.description, spec.input_schema,
                                      _operable_handler(spec), spec.mutating)
                          for key, spec in registry.tools.items()}, registry.validators, registry.folds)
    context = replace(context, validators=rehearsal.validators, folds=rehearsal.folds)
    token = _DRY_RUN.set(True)
    try:
        return dispatch(name, args, context=context, registry=rehearsal)
    finally:
        _DRY_RUN.reset(token)


@contextmanager
def before_commit(guard):
    _enable_operable_hooks()
    token = _COMMIT_GUARD.set(guard)
    try:
        yield
    finally:
        _COMMIT_GUARD.reset(token)
