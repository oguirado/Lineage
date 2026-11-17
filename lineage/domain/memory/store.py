"""Reproducible memory projections; the committed ledger remains authoritative.

All pathname operations use pinned, no-follow directory descriptors. Published
generations are immutable, and the per-agent publication lock is independent of
the journal lock. Coordination files are deliberately outside the projection.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import errno
import hashlib
import os
from pathlib import Path
import re
import secrets
import stat

from lineage.core import journal, locking
from lineage.core.errors import LineageError
from lineage.domain import layout
from . import entry, fold, schema

_AGENT = re.compile(r'[a-z][a-z0-9-]{2,63}')
_CURRENT = re.compile(rb'gen/([1-9][0-9]*)\n')
_RELATIVE = re.compile(r'[A-Za-z0-9_./-]{1,512}')
_SAFE = 9007199254740991
_RESUME_CAPTURE = ContextVar('memory_resume_result', default=None)


def _identity(agent_id):
    if type(agent_id) is not str or _AGENT.fullmatch(agent_id) is None:
        raise LineageError('bad_args', 'invalid agent identifier')


def _version(agent):
    skills = sorted(agent['skills'], key=lambda pin: (pin['skill_id'], pin['sha256']))
    return hashlib.sha256(journal.canonical_bytes({
        'constitution_sha256': agent['constitution_sha256'],
        'skills': skills, 'memory_gen': agent['memory_gen']})).hexdigest()


def _agent_at(agent_id, events, state):
    """Resolve birth without depending on the later agents unit/materializer."""
    record = None
    for event in events:
        payload = event['payload']
        if event['kind'] == 'agent.born' and payload['record']['agent_id'] == agent_id:
            if record is not None:
                raise LineageError('bad_op', 'duplicate committed agent birth')
            record = deepcopy(payload['record'])
        elif (record is not None and event['kind'] == 'agent.status'
              and payload['agent_id'] == agent_id):
            record['status'] = payload['to']
    if record is None or agent_id in {'system', 'operator'}:
        raise LineageError('no_agent', 'committed target agent unavailable')
    authoritative = state.get('agents', {}).get(agent_id)
    if authoritative is not None:
        return deepcopy(authoritative)
    memory = state.get('memory', {}).get(agent_id)
    if memory is None:
        raise LineageError('internal', 'authoritative memory fold unavailable')
    record['memory_gen'] = memory['memory_gen']
    record['agent_version'] = _version(record)
    return record


def _snapshot_agent(agent_id, snapshot):
    _identity(agent_id)
    try:
        # U10 owns the schema/registry facade lifecycle, including rebinding
        # validators when the host reloads the strict JSON boundary.
        schema._sync_boundary()
        return _agent_at(agent_id, snapshot.events, snapshot.state)
    except LineageError:
        raise
    except Exception:
        raise LineageError('internal', 'authoritative snapshot unavailable') from None


def _snapshot(ctx):
    try:
        schema._sync_boundary()
        return journal.snapshot(ctx=ctx)
    except LineageError as exc:
        if exc.code in {'hash_mismatch', 'busy'}:
            raise
        raise LineageError('internal', 'authoritative snapshot unavailable') from None
    except Exception:
        raise LineageError('internal', 'authoritative snapshot unavailable') from None


def _selected(event, agent_id, runs):
    payload, kind = event['payload'], event['kind']
    if event['agent'] == agent_id:
        return True
    if kind == 'agent.born':
        return payload['record']['agent_id'] == agent_id
    if kind in {'agent.status', 'memory.put', 'memory.retire', 'run.open',
                'run.beat', 'bench.result'}:
        if payload.get('agent_id') == agent_id:
            return True
    if kind == 'run.close':
        return payload['record']['agent_id'] == agent_id
    if kind.startswith('run.'):
        return runs.get(payload.get('run_id')) == agent_id
    return False


def generation_files(agent, units, events, *, token_count):
    """Return fresh complete bytes for every selected historical prefix.

    U10 owns historical supersession and brief counters. Private active units
    always have local unit files; recall filters them through ``entry.eligible``.
    Birth is generation one. Contradictory arguments are ``bad_op``.
    """
    try:
        agent_id = agent['agent_id']
        _identity(agent_id)
        state, runs, prefix, selected, result = {}, {}, [], [], {}
        generation, current = 0, None
        for event in events:
            prefix.append(event)
            fold.apply(state, event)
            if event['kind'] == 'run.open':
                runs[event['payload']['run_id']] = event['payload']['agent_id']
            if event['kind'] == 'agent.born' and event['payload']['record']['agent_id'] == agent_id:
                if current is not None:
                    raise LineageError('bad_op', 'duplicate committed agent birth')
                current = deepcopy(event['payload']['record'])
            if current is None or not _selected(event, agent_id, runs):
                continue
            current = _agent_at(agent_id, prefix, state)
            active = fold.units_for(state, agent_id, include_private=True)
            generation += 1
            name = 'gen/' + str(generation) + '/'
            files = {'MEMORY_ENTRY.static.md': entry.build(current, active, token_count=token_count)}
            selected.append(event)
            files['journal.jsonl'] = b''.join(journal.canonical_bytes(e) + b'\n' for e in selected)
            for unit in active:
                schema._shape(unit, 'mem_unit.schema.json')
                files['units/' + unit['id'] + '.json'] = journal.canonical_bytes(unit) + b'\n'
            manifest = {'agent_id': agent_id, 'generation': generation,
                        'source_head': event['lamport'], 'agent_version': current['agent_version'],
                        'memory_gen': current['memory_gen'],
                        'files': [{'path': path, 'sha256': hashlib.sha256(raw).hexdigest()}
                                  for path, raw in sorted(files.items())]}
            files['manifest.json'] = journal.canonical_bytes(manifest) + b'\n'
            result.update((name + path, raw) for path, raw in files.items())
        if current is None:
            raise LineageError('no_agent', 'committed target agent unavailable')
        # All final active units, including private records, must agree. Some
        # callers intentionally request only public units through units_for.
        active = fold.units_for(state, agent_id, include_private=True)
        supplied = sorted(units, key=lambda unit: unit['id'])
        public = [unit for unit in active if unit['privacy'] != 'private']
        if supplied != list(active) and supplied != public:
            raise LineageError('bad_op', 'memory units contradict committed prefix')
        # A-U11-3: compare with the record folded over the WHOLE prefix. Status
        # transitions (promotion, retirement) after the last memory generation
        # change the agent record without creating a memory generation.
        if agent != _agent_at(agent_id, prefix, state):
            raise LineageError('bad_op', 'agent contradicts committed prefix')
        name = 'gen/' + str(generation)
        result['CURRENT'] = (name + '\n').encode('utf-8')
        for mirror in ('MEMORY_ENTRY.static.md', 'journal.jsonl'):
            result[mirror] = result[name + '/' + mirror]
        return dict(sorted(result.items()))
    except LineageError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise LineageError('bad_op', 'inconsistent committed projection input') from None


def _mapping(agent_id, snapshot, ctx):
    agent = _snapshot_agent(agent_id, snapshot)
    try:
        units = fold.units_for(snapshot.state, agent_id, include_private=True)
        return generation_files(agent, units, snapshot.events,
                                token_count=ctx.services.token_count)
    except LineageError:
        raise
    except Exception:
        raise LineageError('internal', 'authoritative projection input unavailable') from None


def _root(agent_id, ctx, *, snapshot=None):
    agent = _snapshot_agent(agent_id, _snapshot(ctx) if snapshot is None else snapshot)
    try:
        return layout.memory_dir(ctx.services.home, workflow=agent['workflow'],
                                 language=agent['language'], agent_id=agent_id)
    except (TypeError, ValueError):
        raise LineageError('bad_args', 'invalid committed agent path identity') from None


def _parts(relative):
    if (type(relative) is not str or _RELATIVE.fullmatch(relative) is None
            or any(part in {'', '.', '..'} for part in relative.split('/'))):
        raise LineageError('bad_args', 'unsafe relative projection coordinate')
    return relative.split('/')


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _child_directory(parent, name, *, create=False):
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
            os.fsync(parent)
        except FileExistsError:
            pass
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
        opened = os.fstat(fd)
        if not stat.S_ISDIR(named.st_mode) or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino):
            raise LineageError('hash_mismatch', 'directory changed during projection access')
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def _directory(path, *, create=False):
    # abspath is lexical: never resolve a caller-supplied symlink before checks.
    absolute = Path(os.path.abspath(os.fspath(path)))
    descriptors = [os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)]
    try:
        for part in absolute.parts[1:]:
            descriptors.append(_child_directory(descriptors[-1], part, create=create))
        yield descriptors[-1]
        for parent, child, part in zip(descriptors, descriptors[1:], absolute.parts[1:]):
            named, opened = os.stat(part, dir_fd=parent, follow_symlinks=False), os.fstat(child)
            if not stat.S_ISDIR(named.st_mode) or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino):
                raise LineageError('hash_mismatch', 'projection ancestor changed during access')
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


@contextmanager
def _file(root, relative):
    parts, descriptors = _parts(relative), []
    parent = root
    try:
        for part in parts[:-1]:
            parent = _child_directory(parent, part)
            descriptors.append(parent)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        descriptors.append(fd)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise LineageError('hash_mismatch', 'required artifact is not a regular file')
        yield fd
        named, after = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False), os.fstat(fd)
        if _stamp(named) != _stamp(before) or _stamp(after) != _stamp(before):
            raise LineageError('hash_mismatch', 'required artifact changed during verification')
        # Validate every intermediate named directory again, not just the leaf.
        previous = root
        for part, child in zip(parts[:-1], descriptors[:-1]):
            named, opened = os.stat(part, dir_fd=previous, follow_symlinks=False), os.fstat(child)
            if not stat.S_ISDIR(named.st_mode) or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino):
                raise LineageError('hash_mismatch', 'required artifact ancestor changed')
            previous = child
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _read(root, relative, *, maximum):
    with _file(root, relative) as fd:
        result = bytearray()
        while len(result) <= maximum:
            chunk = os.read(fd, min(65536, maximum + 1 - len(result)))
            if not chunk:
                break
            result.extend(chunk)
        return bytes(result)


def _io_error(exc):
    if isinstance(exc, LineageError):
        return exc
    if isinstance(exc, OSError) and exc.errno in {
            errno.ENOENT, errno.ELOOP, errno.ENOTDIR, errno.EISDIR}:
        return LineageError('hash_mismatch', 'required projection artifact missing or unsafe')
    return LineageError('internal', 'projection I/O unavailable')


def _issue(path, code='hash_mismatch', detail='projection differs from committed prefix'):
    return {'path': path, 'code': code, 'detail': detail}


def _inspect(root, expected):
    issues = []
    for path, raw in sorted(expected.items()):
        try:
            actual = _read(root, path, maximum=len(raw))
            if actual != raw:
                issues.append(_issue(path))
        except (OSError, LineageError) as exc:
            error = _io_error(exc)
            issues.append(_issue(path, error.code, error.detail))
    directories = {'.'}
    for path in expected:
        parent = Path(path).parent
        while str(parent) != '.':
            directories.add(parent.as_posix())
            parent = parent.parent

    def scan(fd, prefix=''):
        try:
            names = sorted(os.listdir(fd))
        except OSError:
            issues.append(_issue(prefix or '.', 'internal', 'projection directory unreadable'))
            return
        for name in names:
            # Only these roots belong to the deterministic projection. Hidden
            # crash debris and publisher coordination never authorize a read.
            if not prefix and name not in {'gen', 'CURRENT', 'MEMORY_ENTRY.static.md', 'journal.jsonl'}:
                continue
            if prefix == 'gen' and name.startswith('.'):
                continue
            path = prefix + '/' + name if prefix else name
            if (not _RELATIVE.fullmatch(path)
                    or any(part in {'', '.', '..'} for part in path.split('/'))):
                issues.append(_issue(prefix or '.', 'bad_args', 'unsafe projection filename'))
                continue
            try:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    if path not in directories:
                        issues.append(_issue(path, detail='unexpected projection directory'))
                        continue
                    child = _child_directory(fd, name)
                    try:
                        scan(child, path)
                    finally:
                        os.close(child)
                elif path not in expected or not stat.S_ISREG(info.st_mode):
                    issues.append(_issue(path, detail='unexpected or unsafe projection artifact'))
            except (OSError, LineageError) as exc:
                error = _io_error(exc)
                issues.append(_issue(path, error.code, error.detail))
    scan(root)
    return tuple(sorted(issues, key=lambda issue: (issue['path'], issue['code'], issue['detail'])))


def verify_projection(agent_id, *, snapshot, ctx):
    """Compare exact ledger-derived bytes without repairing any artifact."""
    expected = _mapping(agent_id, snapshot, ctx)
    try:
        with _directory(_root(agent_id, ctx, snapshot=snapshot)) as root:
            return _inspect(root, expected)
    except (OSError, LineageError) as exc:
        error = _io_error(exc)
        return (_issue('.', error.code, error.detail),)


def _write(root, relative, raw):
    parts, descriptors, parent = _parts(relative), [], root
    try:
        for part in parts[:-1]:
            parent = _child_directory(parent, part, create=True)
            descriptors.append(parent)
        fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        try:
            remaining = memoryview(raw)
            while remaining:
                count = os.write(fd, remaining)
                if count <= 0:
                    raise OSError('short artifact write')
                remaining = remaining[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(parent)
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def _atomic(root, name, raw):
    temporary = '.tmp-' + secrets.token_hex(16)
    _write(root, temporary, raw)
    os.replace(temporary, name, src_dir_fd=root, dst_dir_fd=root)
    os.fsync(root)


def _existing(root, name):
    try:
        return os.stat(name, dir_fd=root, follow_symlinks=False)
    except FileNotFoundError:
        return None


def rebuild(agent_id, *, snapshot, ctx):
    """Durably stage new generations, then publish pointer and root mirrors."""
    expected = _mapping(agent_id, snapshot, ctx)  # Admission precedes all I/O.
    memory = _root(agent_id, ctx, snapshot=snapshot)
    desired = int(_CURRENT.fullmatch(expected['CURRENT']).group(1))
    try:
        with _directory(memory, create=True) as root:
            lock = os.open('.publish.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                           0o600, dir_fd=root)
            try:
                if not stat.S_ISREG(os.fstat(lock).st_mode):
                    raise LineageError('hash_mismatch', 'unsafe publication lock')
                locking.lock_exclusive(lock)
                try:
                    if _existing(root, 'CURRENT') is not None:
                        raw = _read(root, 'CURRENT', maximum=64)
                        parsed = _CURRENT.fullmatch(raw)
                        if parsed is None or int(parsed.group(1)) > _SAFE:
                            raise LineageError('hash_mismatch', 'unsafe CURRENT contents')
                        if int(parsed.group(1)) > desired:
                            raise LineageError('stale_rev', 'newer committed memory projection exists')
                    gen = _child_directory(root, 'gen', create=True)
                    try:
                        generations = {}
                        for path, raw in expected.items():
                            if path.startswith('gen/'):
                                _, number, relative = path.split('/', 2)
                                generations.setdefault(number, {})[relative] = raw
                        # Refuse all damaged immutable generations before writing
                        # any new generation or changing root mirrors.
                        for number, files in generations.items():
                            if _existing(gen, number) is not None:
                                old = _child_directory(gen, number)
                                try:
                                    issues = _inspect_generation(old, files)
                                    if issues:
                                        raise LineageError('hash_mismatch', 'published generation differs: gen/' + number)
                                finally:
                                    os.close(old)
                        for number in sorted(generations, key=int):
                            if _existing(gen, number) is not None:
                                continue
                            stage = '.stage-' + secrets.token_hex(16)
                            os.mkdir(stage, 0o700, dir_fd=gen)
                            staged = _child_directory(gen, stage)
                            try:
                                for path, raw in sorted(generations[number].items()):
                                    _write(staged, path, raw)
                                os.fsync(staged)
                                if _inspect_generation(staged, generations[number]):
                                    raise LineageError('hash_mismatch', 'staged generation verification failed')
                                identity = os.fstat(staged)
                                os.rename(stage, number, src_dir_fd=gen, dst_dir_fd=gen)
                                named = os.stat(number, dir_fd=gen, follow_symlinks=False)
                                if (not stat.S_ISDIR(named.st_mode)
                                        or (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino)):
                                    raise LineageError('hash_mismatch', 'staged generation substituted during publication')
                                os.fsync(gen)
                            finally:
                                os.close(staged)
                        # A retry may reuse a generation whose previous caller
                        # failed between rename and the directory durability gate.
                        os.fsync(gen)
                        for name in ('CURRENT', 'MEMORY_ENTRY.static.md', 'journal.jsonl'):
                            raw = expected[name]
                            if _existing(root, name) is not None:
                                if _read(root, name, maximum=len(raw)) == raw:
                                    continue
                            _atomic(root, name, raw)
                        issues = _inspect(root, expected)
                        if issues:
                            raise LineageError('hash_mismatch', 'published projection verification failed')
                    finally:
                        os.close(gen)
                finally:
                    locking.unlock(lock)
            finally:
                os.close(lock)
        return tuple(memory / path for path in sorted(expected))
    except (OSError, LineageError) as exc:
        raise _io_error(exc) from None


def _inspect_generation(root, expected):
    """Inspect a generation, including undeclared files and empty directories."""
    issues = []
    for path, raw in sorted(expected.items()):
        try:
            if _read(root, path, maximum=len(raw)) != raw:
                issues.append(_issue(path))
        except (OSError, LineageError) as exc:
            error = _io_error(exc)
            issues.append(_issue(path, error.code, error.detail))
    allowed_dirs = {str(Path(path).parent) for path in expected if '/' in path}

    def scan(fd, prefix=''):
        for name in sorted(os.listdir(fd)):
            path = prefix + '/' + name if prefix else name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode) and path in allowed_dirs:
                child = _child_directory(fd, name)
                try:
                    scan(child, path)
                finally:
                    os.close(child)
            elif path not in expected or not stat.S_ISREG(info.st_mode):
                issues.append(_issue(path, detail='unexpected or unsafe generation artifact'))
    scan(root)
    return tuple(issues)


def _install_resume_dispatch():
    """Bridge U11 reads through the integrated U10 positional dispatch facade.

    That facade supplies defaults only for U10 reads and drops request details.
    Keep its registry validation, context construction and single result wrapper;
    normalize only calls owned by this extension. Other owners are untouched.
    """
    from dataclasses import replace
    from lineage.core import app

    previous = app.dispatch
    if getattr(previous, '_u11_resume_bridge', False):
        return

    def dispatch(name, args, *, ctx=None, context=None, registry=None):
        chosen = ctx.services.registry if ctx is not None else registry
        tool = chosen.tools.get(name) if chosen is not None and type(name) is str else None
        owned = tool is not None and getattr(tool.handler, '_memory_resume', False)
        effective = args
        if owned and type(args) is dict:
            effective = deepcopy(args)
            effective.setdefault('agent', 'system')
            if name == 'memory_route':
                effective.setdefault('limit', 10)
        result = previous(name, effective, ctx=ctx, context=context, registry=registry)
        payload = result if ctx is not None else result.payload
        if (owned and name == 'memory_bootcheck' and payload.get('ok') is False
                and payload.get('code') == 'bad_args'
                and not str(payload.get('detail', '')).startswith('E_BOOTCHECK')):
            payload = dict(payload, detail='E_BOOTCHECK invalid tool arguments')
            result = payload if ctx is not None else replace(result, payload=payload)
        capture = _RESUME_CAPTURE.get()
        if owned and name == 'memory_bootcheck' and capture is not None:
            capture.append(deepcopy(payload))
        return result

    # Expose the integrated native application API to discovery/introspection;
    # ctx is the optional positional-domain facade, as for U10's journal bridge.
    from inspect import signature
    public = signature(previous)
    dispatch.__signature__ = public.replace(parameters=[
        parameter for name, parameter in public.parameters.items() if name != 'ctx'])
    dispatch._u11_resume_bridge = True
    # Preserve the native-provider identity used by U10 when transports rebind.
    # Otherwise its installer nests a fresh facade outside our defaults/errors.
    dispatch._lineage_native = getattr(previous, '_lineage_native', previous)
    app.dispatch = dispatch


def _install_memory_publication():
    """Complete integrated memory transactions after their journal lock releases.

    U10's installed transaction API returns Committed and does not publish U11
    projections. Preserve that API and its replay result. Enable publication only
    for registries that have installed this extension, never for native callers.
    """
    from functools import wraps

    previous = journal.transact
    if getattr(previous, '_u11_publication_bridge', False):
        return

    @wraps(previous)
    def transact(*args, ctx=None, **kwargs):
        committed = previous(*args, ctx=ctx, **kwargs)
        if ctx is None or not args:
            return committed
        command = args[0]
        if getattr(command, 'tool', None) not in {'memory_put', 'operator_ruling', 'memory_retire'}:
            return committed
        tool = ctx.services.registry.tools.get('memory_bootcheck')
        if tool is None or not getattr(tool.handler, '_memory_resume', False):
            return committed
        try:
            # A replay returns the original logical result. Publish the current
            # verified prefix so a retry never attempts to regress CURRENT.
            snapshot = _snapshot(ctx)
            target = command.args['agent_id']
            from lineage.domain import agents
            if isinstance(ctx.services.registry.folds.get('agents'), agents._AgentsFold):
                agents.refresh_projections(target, ctx=ctx)
            else:
                rebuild(target, snapshot=snapshot, ctx=ctx)
        except LineageError as exc:
            if exc.code in {'hash_mismatch', 'busy', 'stale_rev'}:
                raise
            raise LineageError('internal', 'committed memory projection unavailable') from None
        except Exception:
            raise LineageError('internal', 'committed memory projection unavailable') from None
        return committed

    transact._u11_publication_bridge = True
    journal.transact = transact


def _install_resume_json():
    """Retain U11 boot diagnostics through the installed family carrier.

    The carrier strips optional domain details. U11's E_BOOTCHECK diagnostic is
    required, so capture the same shared-dispatch result within this delivery;
    never invoke the read twice or bypass carrier admission/receipt validation.
    Context-local capture prevents cross-thread or nested delivery confusion.
    """
    from lineage.core import jsonlane

    previous = jsonlane._dispatch
    if getattr(previous, '_u11_resume_bridge', False):
        return

    def dispatch(value, config, runtime):
        capture = []
        token = _RESUME_CAPTURE.set(capture)
        try:
            result = previous(value, config, runtime)
        finally:
            _RESUME_CAPTURE.reset(token)
        if len(capture) == 1:
            payload = capture[0]
            if (payload.get('ok') is False and result.get('ok') is False
                    and payload.get('code') == result.get('code')
                    and str(payload.get('detail', '')).startswith('E_BOOTCHECK')
                    and jsonlane._valid_for(payload, 'memory_bootcheck')):
                return payload
        return result

    dispatch._u11_resume_bridge = True
    jsonlane._dispatch = dispatch


def _install_resume_lifecycle():
    """Recompose publication after the integrated provider refreshes its facade.

    U10 owns provider setup and may replace journal.transact when a transport is
    first loaded or reloaded. Retain that setup, then compose only U11's seams.
    """
    from functools import wraps
    from lineage.domain import memory
    from lineage.core.events import _install_projection_verification

    _install_projection_verification()
    previous = memory._ensure_transport
    if getattr(previous, '_u11_resume_bridge', False):
        return

    @wraps(previous)
    def ensure_transport():
        previous()
        _install_resume_dispatch()
        _install_memory_publication()
        _install_resume_json()
        _install_projection_verification()

    ensure_transport._u11_resume_bridge = True
    memory._ensure_transport = ensure_transport
