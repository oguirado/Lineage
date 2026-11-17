"""Independent assertions and hermetic runtime fixtures, never receiver policy."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib
import inspect
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from lineage.bridge import openfresnel as bridge
from lineage.core.app import CallContext
from lineage.core.errors import LineageError

ROOT = Path(__file__).resolve().parents[2]
ENV = 'LINEAGE_OPENFRESNEL_COMMANDS_DIR'
AGENT = 'tester'
OP_ID = 'fixture:operation-1'
RID = hashlib.sha256(b'{"agent":"tester","op_id":"fixture:operation-1"}').hexdigest()[:32]
TOOL_LIMIT = 1048576  # [TARGET: M3/M11]
FAMILY_LIMIT = 65536  # [CITED: K0 family contract]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def request_id(agent=AGENT, op_id=OP_ID):
    return hashlib.sha256(canonical({'agent': agent, 'op_id': op_id})).hexdigest()[:32]


def family(**changes):
    value = {'schema': 'lineage.family/1', 'id': 'request01',
             'source': 'source', 'target': 'receiver', 'kind': 'capabilities',
             'agent': AGENT, 'payload': {}}
    value.update(changes)
    return value


def call_envelope(tool='openfresnel_probe', args=None, **changes):
    return family(kind='call', payload={'tool': tool, 'args': args or {}}, **changes)


def contract_schema(tool):
    text = (ROOT / 'docs/CONTRACT.md').read_text(encoding='utf-8')
    section = text.split('### `' + tool + '`', 1)[1]
    return json.loads(section.split('```json', 1)[1].split('```', 1)[0])


def image(root):
    """Do not follow symlinks, open FIFOs, or depend on wall-clock metadata."""
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs.sort()
        for name in sorted(dirs + files):
            p = Path(base) / name
            key = p.relative_to(root).as_posix()
            if p.is_symlink():
                result[key] = ('link', os.readlink(p))
            elif p.is_file():
                result[key] = ('file', p.read_bytes())
            elif p.is_dir():
                result[key] = ('directory',)
            else:
                result[key] = ('special',)
    return result


class VirtualClock:
    """Bounded virtual polling; no real sleeps and no guessed readiness."""
    def __init__(self):
        self.now = 0.0
        self.calls = 0
        self.on_wait = None

    def monotonic(self):
        self.calls += 1
        if self.calls > 10000:
            raise AssertionError('polling did not honor its bounded deadline')
        self.now += 0.001
        return self.now

    def sleep(self, seconds):
        if seconds < 0:
            raise AssertionError('negative polling interval')
        self.now += seconds
        if self.on_wait:
            self.on_wait()

    @contextmanager
    def installed(self):
        # Accommodate both time.monotonic and an imported alias; no private
        # helper name or polling implementation is prescribed.
        originals = {time.monotonic: self.monotonic, time.sleep: self.sleep}
        with ExitStack() as stack:
            for module in tuple(sys.modules.values()):
                if module is None or not getattr(module, '__name__', '').startswith('lineage.bridge'):
                    continue
                for name, value in tuple(vars(module).items()):
                    for old, new in originals.items():
                        if value is old:
                            stack.enter_context(mock.patch.object(module, name, new))
            stack.enter_context(mock.patch.object(time, 'monotonic', self.monotonic))
            stack.enter_context(mock.patch.object(time, 'sleep', self.sleep))
            yield self


class FakeConsumer:
    """Observes client publication without inventing ANY command/receipt keys.

    Raw hostile results are test-owned byte fixtures, not a supported ABI.
    Success receipt and argv/stdin binding are deliberately AUSENTE.
    """
    def __init__(self, directory, rid=RID):
        self.directory = directory
        self.rid = rid
        self.seen = []

    def observe(self):
        final = self.directory / (self.rid + '.json')
        if not final.exists():
            return None
        raw = final.read_bytes()
        value = json.loads(raw)
        if type(value) is not dict or raw != canonical(value):
            raise AssertionError('consumer saw a partial or noncanonical final command')
        if raw not in self.seen:
            self.seen.append(raw)
        return value

    def publish_raw(self, raw):
        temporary = self.directory / (self.rid + '.result.fixture')
        temporary.write_bytes(raw)
        temporary.replace(self.directory / (self.rid + '.result.json'))


class BridgeCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lineage-bridge-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'home'
        # A-U20: U05 requires an owner-only runtime home, independent of umask.
        self.home.mkdir(mode=0o700)
        self.channel = self.base / 'commands'
        self.channel.mkdir()
        self.other = self.base / 'other'
        self.other.mkdir()
        self.contract = self.base / 'contract.json'
        self.contract.write_bytes(canonical({'paths': {'commands_dir': str(self.other)}}))
        self.ctx = CallContext(self.home, {}, {})
        self.clock = VirtualClock()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.dict(os.environ))
        os.environ.pop(ENV, None)
        self.install_write_guard()
        # Any attempted terminal/model/network/process-group effect is a failed
        # assertion, never an actual side effect. No subprocess is launched.
        for target in ('subprocess.Popen', 'subprocess.run', 'subprocess.call',
                       'os.system', 'os.kill', 'os.killpg', 'socket.socket',
                       'socket.create_connection', 'os.posix_spawn', 'os.posix_spawnp'):
            self.stack.enter_context(mock.patch(target, side_effect=AssertionError('forbidden external effect')))

    def recipient_configuration(self, *, sources, tools):
        # A-U20: provision U05's real recipient API with owner-only fixture modes.
        configuration = self.home / 'family' / 'receiver'
        configuration.parent.mkdir(mode=0o700)
        configuration.mkdir(mode=0o700)
        config = configuration / 'config.json'
        config.write_bytes(canonical({'endpoint': 'receiver', 'sources': sources,
                                      'tools': tools}))
        config.chmod(0o600)
        return configuration

    def install_write_guard(self):
        import builtins
        real_builtin, real_io, real_os = builtins.open, io.open, os.open
        def permitted(path, dir_fd=None):
            if isinstance(path, int):
                path = os.readlink(Path(os.sep) / 'proc' / 'self' / 'fd' / str(path))
            candidate = Path(os.fsdecode(path))
            if dir_fd is not None and not candidate.is_absolute():
                parent = Path(os.readlink(Path(os.sep) / 'proc' / 'self' / 'fd' / str(dir_fd)))
                candidate = parent / candidate
            if not candidate.resolve().is_relative_to(self.base):
                raise AssertionError('write outside the disposable runtime directory')
        def stream_open(original):
            def guarded(path, mode='r', *args, **kwargs):
                if any(c in mode for c in 'wax+'):
                    permitted(path)
                return original(path, mode, *args, **kwargs)
            return guarded
        def descriptor_open(path, flags, *args, **kwargs):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                permitted(path, kwargs.get('dir_fd'))
            return real_os(path, flags, *args, **kwargs)
        self.stack.enter_context(mock.patch.object(builtins, 'open', side_effect=stream_open(real_builtin)))
        self.stack.enter_context(mock.patch.object(io, 'open', side_effect=stream_open(real_io)))
        self.stack.enter_context(mock.patch.object(os, 'open', side_effect=descriptor_open))
        for name in ('unlink', 'remove', 'mkdir', 'rmdir'):
            original = getattr(os, name)
            def guarded(path, *args, _original=original, **kwargs):
                permitted(path, kwargs.get('dir_fd'))
                return _original(path, *args, **kwargs)
            self.stack.enter_context(mock.patch.object(os, name, side_effect=guarded))
        for name in ('rename', 'replace'):
            original = getattr(os, name)
            def guarded(src, dst, *args, _original=original, **kwargs):
                permitted(src, kwargs.get('src_dir_fd'))
                permitted(dst, kwargs.get('dst_dir_fd'))
                return _original(src, dst, *args, **kwargs)
            self.stack.enter_context(mock.patch.object(os, name, side_effect=guarded))

    def invoke(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except NotImplementedError as exc:
            self.fail(str(exc) + ': ' + function.__module__ + '.' + function.__name__)

    def error(self, code, function, *args, **kwargs):
        try:
            value = self.invoke(function, *args, **kwargs)
        except LineageError as exc:
            self.assertEqual(exc.code, code)
            detail = exc.detail
            if detail is not None:
                self.assertIs(type(detail), str)
                self.assertTrue(1 <= len(detail) <= 2048)
                self.assertFalse(any(ord(c) < 32 or ord(c) == 127 for c in detail))
                for private in (str(self.base), str(self.home), str(self.channel), str(self.contract)):
                    self.assertNotIn(private, detail)
            return exc
        self.fail('expected ' + code + ', received ' + repr(value))

    def no_effect_error(self, code, function, *args, **kwargs):
        before = image(self.base)
        try:
            return self.error(code, function, *args, **kwargs)
        finally:
            self.assertEqual(image(self.base), before, 'rejection changed runtime files')

    def command(self, tool='openfresnel_probe', *, agent=AGENT, op_id=OP_ID, **args):
        effective = {'agent': agent, 'op_id': op_id, 'timeout_ms': 20000, **args}
        return bridge.Command(tool, effective, agent, op_id)

    def probe(self, **changes):
        options = {'commands_dir': str(self.channel), 'timeout_ms': 5, **changes}
        command = self.command(**options)
        return self.invoke(bridge.probe, **options, command=command, ctx=self.ctx)

    def parse_error(self, value, *, op='capabilities', rid=RID):
        before = deepcopy(value)
        self.error('internal', bridge.parse_receipt, value, rid=rid, op=op)
        # NaNs compare unequal; identity of the original container is not
        # relied on and mutation is checked with deterministic repr instead.
        self.assertEqual(repr(value), repr(before), 'parser modified its input')

    def extension(self):
        return importlib.import_module('lineage.ext.openfresnel')

    def handler(self, tool, args):
        name = '_probe' if tool == 'openfresnel_probe' else '_spawn'
        return self.invoke(getattr(self.extension(), name), args, context=self.ctx)

    def descriptors(self):
        ext = self.extension()
        self.assertIs(type(ext.TOOLS), tuple)
        self.assertEqual({s.name for s in ext.TOOLS},
                         {'openfresnel_probe', 'openfresnel_spawn'},
                         'U20 stub: both tool descriptors must be implemented')
        self.assertEqual(len(ext.TOOLS), 2)
        return ext.TOOLS


def install_cases(cls, prefix, cases, body):
    """Each hostile input is an independently counted, named unittest."""
    for name, value in cases.items():
        def test(self, value=value):
            body(self, deepcopy(value))
        test.__name__ = prefix + name
        test.__doc__ = 'Negative/hostile contrast: ' + name.replace('_', ' ')
        setattr(cls, test.__name__, test)


@contextmanager
def client_double(case, name, result):
    """Replace the public client seam, accommodating either import style."""
    ext = case.extension()
    original = getattr(bridge, name)
    fake = mock.Mock(return_value=deepcopy(result))
    with ExitStack() as stack:
        for key, value in tuple(vars(ext).items()):
            if value is original:
                stack.enter_context(mock.patch.object(ext, key, fake))
        stack.enter_context(mock.patch.object(bridge, name, fake))
        yield fake
