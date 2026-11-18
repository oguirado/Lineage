"""Read-only local preflight with stable, machine-readable check identifiers."""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import sys

from . import app, registry as extensions
from .schema import strict_loads


def contract_mismatches(registry, *, root: Path) -> list[str]:
    """Compare whole registered input schemas with the normative Arguments blocks."""
    text = (root / 'docs' / 'CONTRACT.md').read_text(encoding='utf-8')
    sections = re.finditer(
        r'^### `([a-z_0-9]+)`\s*\nArguments:\s*\n```json\s*\n(.*?)\n```',
        text, re.S | re.M)
    contract = {match[1]: strict_loads(match[2]) for match in sections}
    return [name for name, spec in sorted(registry.tools.items())
            if contract.get(name) != spec.input_schema]


def _private_home(home: Path) -> str:
    # Check ancestors from the root down before inspecting the leaf.
    if any(parent.is_symlink() for parent in reversed(home.parents)):
        raise ValueError
    info = home.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise ValueError
    return 'owned private home'


def _endpoints(home: Path, registry) -> str:
    from . import envelope, family
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    root_fd = os.open(home, flags)
    try:
        family._owned(os.fstat(root_fd))
        info = family._stat(root_fd, 'family')
        if info is None:
            return 'no endpoints configured; JSON lane disabled'
        family._owned(info)
        directory = os.open('family', flags, dir_fd=root_fd)
        try:
            count = 0
            for name in sorted(os.listdir(directory)):
                if envelope.ENDPOINT_RE.fullmatch(name) is None:
                    raise ValueError
                family._owned(family._stat(directory, name))
                endpoint = os.open(name, flags, dir_fd=directory)
                try:
                    config = envelope.configuration(
                        family._read_regular(endpoint, 'config.json', envelope.MAX_REQUEST_BYTES)[0], name)
                    if not set(config['tools']) <= set(registry.tools):
                        raise ValueError
                    for member in ('spool', 'state', 'dedup'):
                        info = family._stat(endpoint, member)
                        if info is not None:
                            family._owned(info)
                    lock = family._stat(endpoint, 'consumer.lock')
                    if lock is not None:
                        family._regular(lock)
                    count += 1
                finally:
                    os.close(endpoint)
            return str(count) + ' endpoint configurations valid; empty grants authorize nothing'
        finally:
            os.close(directory)
    finally:
        os.close(root_fd)


def report(home=None, *, registry=None, root: Path | None = None) -> dict:
    root = Path(__file__).resolve().parents[2] if root is None else Path(root)
    checks = []

    def check(ident, operation, failure):
        try:
            detail = operation()
            checks.append({'id': ident, 'ok': True, 'detail': detail})
        except Exception:
            checks.append({'id': ident, 'ok': False, 'detail': failure})
            return False
        return True

    selected = home if home is not None else os.environ.get('LINEAGE_HOME') or '~/.lineage'
    try:
        if not os.fspath(selected):
            raise ValueError
        selected = Path(selected).expanduser().absolute()
    except (TypeError, ValueError, OSError, RuntimeError):
        home_ok = False
        checks.append({'id': 'home_permissions', 'ok': False, 'detail': 'invalid home'})
    else:
        home_ok = check('home_permissions', lambda: _private_home(selected),
                        'home must exist, be owned, private and free of symlinks')

    def check_home(ident, operation, failure):
        if home_ok:
            check(ident, operation, failure)
        else:
            checks.append({'id': ident, 'ok': False, 'detail': 'skipped: unsafe or invalid home'})

    try:
        registry = extensions.load() if registry is None else registry
        context = app.create_context(selected, registry=registry) if home_ok else None
        checks.append({'id': 'registry', 'ok': bool(registry.tools),
                       'detail': str(len(registry.tools)) + ' registered tools'})
    except Exception:
        registry = context = None
        checks.append({'id': 'registry', 'ok': False, 'detail': 'registry unavailable'})

    def dispatch(name, args):
        if context is None:
            raise ValueError
        result = app.dispatch(name, args, context=context, registry=registry)
        if result.failure is not None:
            raise ValueError
        return result.payload['untrusted']

    unverified = []

    def ledger():
        data = dispatch('ledger_verify', {})
        if data.get('valid') is not True:
            raise ValueError
        # A-OPC1: the frozen ledger_verify result carries no non-verification
        # list; the internal certifier reports it (R4 declared gaps).
        from .events import verify_ledger
        unverified.extend(verify_ledger(selected).get('unverified', []))
        return 'verified ledger; head=' + str(data['head'])

    def conformance():
        if registry is None:
            raise ValueError
        mismatches = contract_mismatches(registry, root=root)
        if mismatches:
            return False, 'schema mismatch: ' + ', '.join(mismatches)
        return True, 'all registered schemas match docs/CONTRACT.md'

    def references():
        for ref_id in ('gold_s1', 'memory_v21'):
            if dispatch('reference_verify', {'ref_id': ref_id}).get('valid') is not True:
                raise ValueError
        return 'gold_s1 and memory_v21 verified'

    def ui():
        from lineage.serve.static import resolve_asset
        resolve_asset('/', root=root / 'ui' / 'dist')
        return 'ui/dist/index.html present'

    check_home('ledger', ledger, 'ledger verification failed or unavailable')
    try:
        ok, detail = conformance()
        checks.append({'id': 'contract_conformance', 'ok': ok, 'detail': detail})
    except Exception:
        checks.append({'id': 'contract_conformance', 'ok': False,
                       'detail': 'contract or registry unavailable'})
    check_home('references', references, 'founding references failed verification')
    check('ui_bundle', ui, 'ui/dist/index.html missing or unsafe; serve cannot load the UI')
    check_home('json_endpoints', lambda: _endpoints(selected, registry),
               'endpoint configuration missing, invalid, unsafe or names unavailable tools')
    if not any(item['id'] == 'ledger' and item['ok'] for item in checks):
        unverified.append({'scope': 'ledger_and_projections', 'reason': 'ledger verification did not complete'})
    unverified.append({'scope': 'live_openfresnel', 'reason': 'preflight does not contact an external receiver'})
    return {'ok': all(item['ok'] for item in checks), 'checks': checks, 'unverified': unverified}


def main(tail, *, home=None, registry=None, stdout=None) -> int:
    from .cli import _emit
    stdout = sys.stdout if stdout is None else stdout
    if tail in (['--operable'], ['--operable', '--json'], ['--json', '--operable']):
        result = operable_report()
        return _emit(stdout, result, 0 if result['ok'] else 3)
    if tail not in ([], ['--json']):
        return _emit(stdout, {'ok': False, 'code': 'bad_args'}, 2)
    result = report(home, registry=registry)
    code = 0 if result['ok'] else 3
    if tail == ['--json']:
        return _emit(stdout, result, code)
    for item in result['checks']:
        stdout.write(('OK' if item['ok'] else 'FAIL') + ' ' + item['id'] + ': ' + item['detail'] + '\n')
    for item in result['unverified']:
        stdout.write('UNVERIFIED ' + item['scope'] + ': ' + item['reason'] + '\n')
    stdout.flush()
    return code


class _OperableProbe:
    """Owned temporary runtime and real, bounded CLI subprocesses."""
    def __init__(self, home):
        import json
        self.home = home
        self.root = Path(__file__).resolve().parents[2]
        self.json = json
        self.environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')

    def command(self, *args, raw=None, expected=0):
        import subprocess
        result = subprocess.run([sys.executable, '-B', '-m', 'lineage', '--home', str(self.home), *args],
                                input=raw, capture_output=True, cwd=self.root,
                                env=self.environment, timeout=15)
        if result.returncode != expected:
            raise ValueError('CLI refused self-test operation')
        return self.json.loads(result.stdout)

    def call(self, tool, args, *flags):
        return self.command('call', tool, '--json', self.json.dumps(args), *flags)['untrusted']

    def endpoint(self, name):
        family = self.home / 'family'
        family.mkdir(mode=0o700, exist_ok=True)
        path = family / name
        path.mkdir(mode=0o700)
        (path / 'config.json').write_text(self.json.dumps({
            'endpoint': name, 'sources': ['operable'],
            'tools': ['skill_publish', 'run_beat', 'ledger_events']}), encoding='utf-8')
        (path / 'config.json').chmod(0o600)
        (path / 'spool').mkdir(mode=0o700)
        return path

    def envelope(self, identity, tool, args, *, endpoint='probe-main', dry_run=False):
        return {'schema': 'lineage.family/1', 'id': identity, 'source': 'operable',
                'target': endpoint, 'kind': 'call', 'agent': 'probe-agent',
                'payload': {'tool': tool, 'args': args, **({'dry_run': True} if dry_run else {})}}

    def deliver(self, value, *, expected=0):
        return self.command('json', raw=self.json.dumps(value).encode(), expected=expected)['result']

    def application_bytes(self):
        return {path.relative_to(self.home).as_posix(): path.read_bytes()
                for path in self.home.rglob('*') if path.is_file()
                and path.relative_to(self.home).parts[0] != 'family'}

    def crash_after_commit(self, value):
        """Stop only our verified child, after a durable application witness."""
        import select
        import subprocess
        read_fd, write_fd = os.pipe()
        script = """import os, sys, threading
from lineage.core import cli, family
original = family.Mailbox._witness
def witnessed(self, value, result, name):
    original(self, value, result, name)
    if 'untrusted' in result:
        os.write(int(sys.argv[1]), b'committed')
        threading.Event().wait(10)
family.Mailbox._witness = witnessed
raise SystemExit(cli.main(['--home', sys.argv[2], 'json']))
"""
        process = None
        try:
            process = subprocess.Popen([sys.executable, '-B', '-c', script, str(write_fd), str(self.home)],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       pass_fds=(write_fd,), cwd=self.root, env=self.environment)
            os.close(write_fd)
            write_fd = None
            process.stdin.write(self.json.dumps(value).encode())
            process.stdin.close()
            if not select.select([read_fd], [], [], 8)[0] or os.read(read_fd, 32) != b'committed':
                raise ValueError('durable commit handshake absent')
        finally:
            if write_fd is not None:
                os.close(write_fd)
            os.close(read_fd)
            if process is not None:
                if process.pid > 1 and process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
        # No stale takeover: only this isolated fixture's lock is removed, after
        # wait() proves its exact owner is dead. Normal drain never does this.
        lock = self.home / 'family' / value['target'] / 'consumer.lock'
        if lock.is_symlink() or lock.read_bytes() != b'owned\n':
            raise ValueError('fixture consumer ownership changed')
        lock.unlink()


def operable_report():
    """Mechanical operable checklist; production home is never consulted."""
    from concurrent.futures import ThreadPoolExecutor
    from tempfile import TemporaryDirectory
    checks = []
    unverified = [
        {'scope': 'live_openfresnel', 'reason': 'external delivery and receiver completion are not exercised'},
        {'scope': 'public_document_persona', 'reason': 'a mechanical probe cannot certify an unfamiliar human or agent persona'},
        {'scope': 'gui_window_accessibility', 'reason': 'headless probe does not inspect GUI windows or accessibility'},
        {'scope': 'human_signatures', 'reason': 'risk annotations do not authenticate human approval'}]

    def check(identity, operation):
        try:
            operation()
            checks.append({'id': identity, 'ok': True})
        except Exception:
            checks.append({'id': identity, 'ok': False, 'detail': 'mechanical assertion failed'})

    def require(condition):
        if not condition:
            raise ValueError

    with TemporaryDirectory(prefix='lineage-operable-') as temporary:
        probe = _OperableProbe(Path(temporary))
        main = probe.endpoint('probe-main')
        def package(name):
            return {'skill_id': name, 'files': [{'path': 'SKILL.md', 'content': 'Passive self-test context.\n'}]}

        def risk():
            tools = probe.command('tools')['tools']
            require(bool(tools) and all(item['annotations']['lineage_risk'] in app._RISKS for item in tools))
            require(all(next(item for item in tools if item['name'] == name)['annotations']['lineage_risk'] == 'irreversible'
                        for name in ('agent_retire', 'skill_retire')))
        check('risk_classes', risk)

        def dry():
            before = probe.application_bytes()
            args = {**package('probe-dry'), 'agent': 'probe-agent', 'op_id': 'probe:/dry'}
            result = probe.call('skill_publish', args, '--dry-run')
            require(result['dry_run'] and result['events'][0]['kind'] == 'skill.published')
            request = probe.envelope('dryprobe1', 'skill_publish', package('probe-dry'), dry_run=True)
            require(probe.deliver(request)['untrusted']['dry_run'])
            require(before == probe.application_bytes())
            require(not (main / 'dedup' / 'dryprobe1.json').exists())
        check('dry_run_no_effects', dry)

        def cancel():
            request = probe.envelope('cancel001', 'skill_publish', package('probe-cancelled'))
            abort = main / 'spool' / 'cancel001.abort'
            abort.write_bytes(b'')
            abort.chmod(0o600)
            require(probe.deliver(request, expected=3) == {
                'ok': False, 'code': 'bad_op', 'detail': 'cancelled by order'})
            other = probe.envelope('survive01', 'skill_publish', package('probe-survivor'))
            require('untrusted' in probe.deliver(other))
            require(probe.deliver(request, expected=3)['detail'] == 'cancelled by order')
        check('cancel_one_request', cancel)

        def restart():
            request = probe.envelope('restart01', 'skill_publish', package('probe-restart'))
            probe.crash_after_commit(request)
            # Cancellation after the durable commit must preserve that commit.
            abort = main / 'spool' / 'restart01.abort'
            abort.write_bytes(b'')
            abort.chmod(0o600)
            first = probe.deliver(request)
            second = probe.deliver(request)
            require(first == second and 'commit' in first['untrusted'])
            events = probe.call('ledger_events', {})['events']
            from .envelope import operation_id
            require(sum(item['op_id'] == operation_id(request) for item in events) == 1)
        check('kill_resume_without_duplicate', restart)

        def serialize():
            refs = [probe.call('reference_get', {'ref_id': ident})['reference'] for ident in ('gold_s1', 'memory_v21')]
            seat = {'model': 'fixture', 'effort': 'low', 'mode': 'headless'}
            probe.call('agent_create', {'agent_id': 'probe-agent', 'display_name': 'Operable fixture',
                'workflow': 'develop', 'language': 'python', 'allowed_seats': [seat],
                'references': [{'id': item['id'], 'sha256': item['sha256']} for item in refs],
                'skills': [], 'agent': 'probe-agent', 'op_id': 'probe:/agent'})
            probe.call('run_open', {'run_id': 'proberun1', 'agent_id': 'probe-agent', 'seat': seat,
                'task': {'id': 'probetask', 'kind': 'test', 'language': 'python'},
                'parents_context': [], 'memory_arm': 'none', 'agent': 'probe-agent', 'op_id': 'probe:/open'})
            probe.endpoint('probe-peer')
            orders = [probe.envelope('serial001', 'run_beat', {'run_id': 'proberun1', 'progress': 'first'}),
                      probe.envelope('serial002', 'run_beat', {'run_id': 'proberun1', 'progress': 'second'}, endpoint='probe-peer')]
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(probe.deliver, orders))
            heads = sorted(item['untrusted']['commit']['head'] for item in results)
            require(heads[1] == heads[0] + 1)
        check('shared_agent_serializes', serialize)

        def sentinel():
            receipts = list(main.joinpath('state').glob('*.result.json'))
            require(bool(receipts))
            for path in receipts:
                ident = path.name[:-len('.result.json')]
                require(path.with_name(ident + '.done').read_bytes() == ('<!-- ' + ident + '_DONE -->\n').encode())
        check('done_sentinel', sentinel)

        def verify():
            data = probe.command('verify')['untrusted']
            require(data['valid'] is True)
        check('independent_verification', verify)
    return {'ok': all(item['ok'] for item in checks), 'checks': checks, 'unverified': unverified}
