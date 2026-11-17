"""Concurrent loopback adapter over the frozen shared application boundary."""
from dataclasses import dataclass, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import signal
import socket
import sys
import threading
from urllib.parse import urlsplit

from lineage.core import app as _app, registry as _registry, schema as _schema
from lineage.core.errors import LineageError
from lineage.serve import session, static

# Integrated providers own their APIs. Keep the original adapter seam usable
# for isolated contract tests, without changing any provider or global registry.
# A-INT1: K0 aliases can coexist with the integrated native app. Select the
# provider by its real application API, never by aliases installed by a peer.
_K0 = not hasattr(_app, 'CallContext')
if _K0:
    Context = _registry.Context
    dispatch = _app.dispatch
    list_tools = _app.list_tools
    canonical = _schema.canonical
    decode = _schema.decode
    from lineage.core.errors import error_payload
    from lineage.serve.fixtures import _Fixtures
else:
    import json
    from lineage.core import journal

    @dataclass(frozen=True)
    class _Services:
        home: Path
        repo_root: Path
        registry: _registry.Registry
        call_context: _app.CallContext
        ui_dist: Path
        stdout: object
        stderr: object

    @dataclass(frozen=True)
    class Context:
        services: _Services
        authority: str = 'tool'
        transport: str = 'http'

    def canonical(value):
        _schema.validate(value, {})
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(',', ':')).encode('utf-8')

    def decode(raw, *, max_bytes=1048576):
        if len(raw) > max_bytes:
            raise LineageError('bad_args')
        return _schema.strict_loads(raw)

    def error_payload(exc):
        return exc.as_dict()

    def dispatch(name, args, *, ctx):
        return _app.dispatch(name, args, context=ctx.services.call_context,
                             registry=ctx.services.registry).payload

    def list_tools(*, ctx):
        return _app.list_tools(registry=ctx.services.registry)

    def _Fixtures(root, ctx):
        # Admission is fixture-owned; an unavailable provider must never cause
        # a fixture request to consult the live home.
        try:
            from lineage.serve.fixtures import _Fixtures as loader
        except ImportError:
            raise LineageError('bad_args', 'Fixture provider unavailable.') from None
        return loader(root, ctx)


_CAP = 1048576
_STATUS = {'bad_args': 400, 'bad_op': 409, 'stale_rev': 409, 'busy': 503,
           'internal': 500, 'conflict': 409, 'no_agent': 404, 'no_run': 404,
           'run_closed': 409, 'memory_required': 409, 'memory_debt': 409,
           'forbidden_level': 403, 'not_inheritable': 409, 'hash_mismatch': 409,
           'rule_not_declared': 409, 'no_benchmark': 404, 'heldout_forbidden': 409,
           'seat_not_allowed': 409, 'fixture_readonly': 403, 'timeout': 504}


class _Stop(BaseException):
    pass


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(2.0)
        return connection, address

    def handle_error(self, request, client_address):
        # Network and request exceptions never become stderr diagnostics.
        pass


class _Handler(BaseHTTPRequestHandler):
    server_version = 'Lineage'
    sys_version = ''

    def log_message(self, format, *args):
        pass

    def __getattr__(self, name):
        if name.startswith('do_'):
            return self._handle
        raise AttributeError(name)

    def handle_expect_100(self):
        # Validation is centralized; no interim acknowledgement is needed.
        return True

    def send_error(self, code, message=None, explain=None):
        self._error(400 if code != 414 else 413)

    def _send(self, status, body, content_type='application/json', *, headers=None, no_store=True):
        self.close_connection = True
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        if no_store:
            self.send_header('Cache-Control', 'no-store')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _json(self, status, value, **kwargs):
        body = canonical(value)
        self._send(status, body, **kwargs)

    def _error(self, status, code='bad_args', detail='', *, headers=None):
        value = {'ok': False, 'code': code}
        if detail:
            value['detail'] = detail
        self._json(status, value, headers=headers)

    def _single(self, name, *, required=False):
        values = self.headers.get_all(name, [])
        if len(values) > 1 or (required and len(values) != 1):
            raise LineageError('bad_args')
        return values[0] if values else None

    def _authorized(self, mutation=False):
        try:
            host = self._single('Host', required=True)
            origin = self._single('Origin')
            token = self._single('X-Lineage-Session')
            session.authorize(host=host, origin=origin, token=token,
                              expected_authority=self.server.authority,
                              expected_token=self.server.token, mutation=mutation)
        except LineageError:
            self._error(403)
            return False
        return True

    def _dispatch(self, name, args):
        try:
            result = dispatch(name, args, ctx=self.server.ctx)
            # Enforce the frozen result seam; do not adapt legacy objects.
            if not isinstance(result, dict):
                raise ValueError('Invalid dispatch result')
            if set(result) == {'untrusted'}:
                canonical(result)
                return result
            if not (set(result) <= {'ok', 'code', 'detail'} and result.get('ok') is False
                    and result.get('code') in _STATUS):
                raise ValueError('Invalid dispatch result')
            if _K0 and 'detail' in result and (not isinstance(result['detail'], str) or not 0 < len(result['detail']) <= 2048):
                raise ValueError('Invalid error detail')
            canonical(result)
            return result
        except LineageError as exc:
            return error_payload(exc)
        except Exception:
            return {'ok': False, 'code': 'internal'}

    def _result(self, result):
        self._json(_STATUS[result['code']] if result.get('ok') is False else 200, result)

    def _query(self, query):
        result = {'after': 0, 'limit': 100, 'wait_ms': 0}
        seen = set()
        if not query:
            return result
        # Query syntax itself is closed: encoded aliases and separators are refused.
        for pair in query.split('&'):
            key, sep, value = pair.partition('=')
            if key not in ('after', 'wait_ms') or key in seen or not sep or not re.fullmatch(r'0|[1-9][0-9]*', value):
                raise LineageError('bad_args')
            seen.add(key)
            if len(value) > 16:
                raise LineageError('bad_args')
            number = int(value)
            if number > (30000 if key == 'wait_ms' else 9007199254740991):
                raise LineageError('bad_args')
            result[key] = number
        return result

    def _body(self):
        if any(self.headers.get_all(name) for name in ('Transfer-Encoding', 'Expect', 'Upgrade')):
            self._error(400)
            return None
        try:
            length = self._single('Content-Length', required=True)
            media = self._single('Content-Type')
        except LineageError:
            self._error(400)
            return None
        if not re.fullmatch(r'[0-9]+', length or ''):
            self._error(400)
            return None
        significant = length.lstrip('0') or '0'
        if len(significant) > 7 or int(significant) > _CAP:
            self._error(413)
            return None
        length = int(significant)
        if not media or not re.fullmatch(r'application/json(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?\s*', media, re.I):
            self._error(415)
            return None
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise LineageError('bad_args')
            value = decode(raw, max_bytes=_CAP)
            if not isinstance(value, dict) or set(value) != {'tool', 'args'} or not isinstance(value['tool'], str) or not isinstance(value['args'], dict):
                raise LineageError('bad_args')
            return value
        except (LineageError, OSError, ValueError, UnicodeError):
            self._error(400)
            return None

    def _handle(self):
        try:
            self._route()
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            self.close_connection = True
        except LineageError as exc:
            self._error(_STATUS.get(exc.code, 500), exc.code if exc.code in _STATUS else 'internal')
        except Exception:
            try:
                self._error(500, 'internal')
            except OSError:
                pass

    def _route(self):
        if not self._authorized():
            return
        if any(self.headers.get_all(name) for name in ('Expect', 'Upgrade', 'Transfer-Encoding')):
            self._error(400)
            return
        target = self.raw_requestline.decode('iso-8859-1').split()[1]
        if not target.startswith('/') or target.startswith('//'):
            self._error(404)
            return
        parsed = urlsplit(target)
        path = parsed.path
        api = path in ('/api/health', '/api/tools', '/api/call', '/api/events')
        if path.startswith('/api/') and not api:
            self._error(404)
            return
        allowed = 'POST' if path == '/api/call' else 'GET'
        if self.command != allowed:
            self._error(405, headers={'Allow': allowed})
            return
        if api and path != '/api/events' and '?' in target:
            self._error(400)
            return
        if path == '/api/call':
            request = self._body()
            if request is None:
                return
            name, args = request['tool'], request['args']
            spec = self.server.ctx.services.registry.tools.get(name)
            if spec is None:
                self._error(400)
                return
            protected = _protected(name, spec)
            if protected and self.server.fixture_data is not None:
                self._error(403, 'fixture_readonly')
                return
            if protected and not self._authorized(mutation=True):
                return
            self._result(self._dispatch(name, args))
        elif path == '/api/tools':
            self._json(200, {'tools': list_tools(ctx=self.server.ctx)})
        elif path == '/api/events':
            args = self._query(parsed.query)
            if 'ledger_events' not in self.server.ctx.services.registry.tools:
                self._error(503, 'internal', 'Cursor provider unavailable.')
                return
            self._result(self._dispatch('ledger_events', args))
        elif path == '/api/health':
            if (not _K0
                    and self.server.fixture_data is None
                    and 'ledger_events' not in self.server.ctx.services.registry.tools):
                try:
                    history = journal.snapshot(self.server.ctx.services.home)
                    head = history[-1]['lamport'] if history else 0
                except Exception:
                    self._error(503, 'internal', 'Ledger unavailable.')
                    return
            elif self.server.fixture_data is not None:
                head = self.server.fixture_data.head
            else:
                if 'ledger_events' not in self.server.ctx.services.registry.tools:
                    self._error(503, 'internal', 'Ledger provider unavailable.')
                    return
                result = self._dispatch('ledger_events', {'after': 0, 'limit': 100, 'wait_ms': 0})
                if set(result) != {'untrusted'} or not isinstance(result['untrusted'], dict):
                    self._error(503, 'busy' if result.get('code') == 'busy' else 'internal', 'Ledger unavailable.')
                    return
                head = result['untrusted'].get('head')
                if type(head) is not int or not 0 <= head <= 9007199254740991:
                    self._error(503, 'internal', 'Ledger head unavailable.')
                    return
            self._json(200, dict(ok=True, protocol='lineage.family/1', head=head,
                                 fixtures=self.server.fixture_data is not None))
        else:
            self._asset(target)

    def _asset(self, target):
        root = getattr(self.server.ctx.services, 'ui_dist',
                       self.server.ctx.services.repo_root / 'ui' / 'dist')
        try:
            parts = static._parts(target)
        except (LineageError, ValueError):
            self._error(404)
            return
        index = parts == ['index.html']
        if index and '?' in target:
            self._error(400)
            return
        try:
            candidate, data = static._read_asset(target, root=root)
        except LineageError as exc:
            if exc.code == 'internal':
                self._error(500, 'internal')
            elif index and (not root.exists() or not (root / 'index.html').exists()):
                self._error(503, 'internal', 'UI build unavailable.')
            else:
                self._error(404)
            return
        if index:
            data = static._bootstrap(data, self.server.token)
        self._send(200, data, static._MIME.get(candidate.suffix.lower(), 'application/octet-stream'), no_store=index)


def serve(*, ctx: Context, port: int = 0, fixtures: Path | None = None) -> None:
    if type(port) is not int or not 0 <= port <= 65535 or not isinstance(ctx, Context):
        raise LineageError('bad_args')
    if fixtures is not None and not isinstance(fixtures, Path):
        raise LineageError('bad_args')
    try:
        ctx = replace(ctx, authority='tool', transport='http')
        # Check the local adapter boundary before allocating the listener.
        ctx.services.registry.tools
        fixture_data = _Fixtures(fixtures, ctx) if fixtures is not None else None
        if fixture_data is not None:
            ctx = fixture_data.ctx
        token = session.new_token()
        server = _Server(('127.0.0.1', port), _Handler)
    except LineageError:
        raise
    except Exception:
        raise LineageError('internal') from None
    previous = {}
    def stop(signum, frame):
        raise _Stop()
    try:
        server.ctx = ctx
        server.fixture_data = fixture_data
        server.token = token
        server.authority = '127.0.0.1:' + str(server.server_address[1])
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGINT, signal.SIGTERM):
                previous[sig] = signal.signal(sig, stop)
        startup_port = server.server_address[1]
        stderr = getattr(ctx.services, 'stderr', sys.stderr)
        stderr.write(canonical({'port': startup_port}).decode('utf-8') + '\n')
        stderr.flush()
        stdout = getattr(ctx.services, 'stdout', None)
        if stdout is not None:
            _emit(stdout, {'ok': True, 'url': 'http://' + server.authority + '/',
                           'port': startup_port})
        server.serve_forever(poll_interval=0.05)
    except (_Stop, KeyboardInterrupt):
        pass
    except Exception:
        raise LineageError('internal') from None
    finally:
        server.server_close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _protected(name, spec):
    if hasattr(spec, 'effect'):
        return spec.effect in ('journal', 'external') or name == 'ledger_export'
    return spec.mutating or name in ('ledger_export', 'openfresnel_probe',
                                     'openfresnel_spawn')


def _emit(stream, value):
    stream.write(canonical(value).decode('utf-8') + '\n')
    stream.flush()


def main(tail, *, context, registry, stdin, stdout, stderr) -> int:
    """CLI-owned runtime to HTTP adapter; report readiness only after binding."""
    try:
        options = {}
        if len(tail) % 2:
            raise LineageError('bad_args')
        for flag, value in zip(tail[::2], tail[1::2]):
            if (flag not in ('--port', '--fixtures', '--ui-dist')
                    or flag in options or not isinstance(value, str)
                    or not value or value.startswith('--')):
                raise LineageError('bad_args')
            options[flag] = value
        raw_port = options.get('--port', '0')
        if (re.fullmatch(r'[0-9]{1,5}', raw_port) is None
                or int(raw_port) > 65535):
            raise LineageError('bad_args')
        port = int(raw_port)
        repo_root = Path(__file__).resolve().parents[2]
        ui_dist = (Path(options['--ui-dist']).expanduser().absolute()
                   if '--ui-dist' in options else repo_root / 'ui' / 'dist')
        fixtures = (Path(options['--fixtures']).expanduser().absolute()
                    if '--fixtures' in options else None)
        # Reuse the actual CLI context construction and keep its validator/fold
        # identities attached to the supplied registry, just as MCP does.
        call_context = _app.create_context(context.home, registry=registry,
                                           actor=context.actor, op_id=context.op_id)
        ctx = Context(_Services(call_context.home, repo_root, registry,
                                call_context, ui_dist, stdout, stderr))
        serve(ctx=ctx, port=port, fixtures=fixtures)
        return 0
    except LineageError as exc:
        code = exc.code if exc.code in _STATUS else 'internal'
        _emit(stdout, {'ok': False, 'code': code})
        return 2 if code == 'bad_args' else 3
    except (ValueError, TypeError):
        _emit(stdout, {'ok': False, 'code': 'bad_args'})
        return 2
    except Exception:
        _emit(stdout, {'ok': False, 'code': 'internal'})
        return 3
