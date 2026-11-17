"""A21–A24: URL confinement and descriptor-safe serving, including deterministic swaps."""
import os
from pathlib import Path

from tests.serve._support import LineageError, ServerCase, cases, load_surface


class ResolveTests(ServerCase):
    def test_a21_nested_regular_file(self):
        with load_surface() as modules:
            actual = modules.static.resolve_asset('/assets/theme.css', root=self.root / 'ui/dist')
        self.assertEqual(actual, self.root / 'ui/dist/assets/theme.css')
        self.assertEqual(actual.read_bytes(), self.assets['assets/theme.css'])

    def test_a21_root_denotes_index(self):
        with load_surface() as modules:
            actual = modules.static.resolve_asset('/', root=self.root / 'ui/dist')
        self.assertEqual(actual, self.root / 'ui/dist/index.html')

    def test_a23_os_ancestor_symlink_permitted(self):
        (self.root / 'alias').symlink_to(self.root / 'ui', target_is_directory=True)
        with load_surface() as modules:
            result = modules.static.resolve_asset('/app.js', root=self.root / 'alias/dist')
        self.assertEqual(result.read_bytes(), self.assets['app.js'])

    def test_a23_symlinked_root_refused(self):
        root = self.root / 'linked-dist'
        root.symlink_to(self.root / 'ui/dist', target_is_directory=True)
        self.refused('/app.js', root=root)

    def test_a23_symlinked_directory_refused(self):
        (self.root / 'ui/dist/linked').symlink_to(self.root / 'outside', target_is_directory=True)
        self.refused('/linked/theme.css')

    def test_a23_symlinked_leaf_refused(self):
        (self.root / 'ui/dist/linked.css').symlink_to(self.root / 'outside/theme.css')
        self.refused('/linked.css')

    def test_a23_fifo_refused_without_opening(self):
        os.mkfifo(self.root / 'ui/dist/pipe')
        self.refused('/pipe')

    def refused(self, path, root=None):
        with load_surface() as modules:
            try:
                modules.static.resolve_asset(path, root=root or self.root / 'ui/dist')
            except LineageError as exc:
                self.assertEqual(exc.code, 'bad_args')
            else:
                self.fail('Unsafe asset path admitted')


BAD_PATHS = [
    ('dotdot', '/../outside/theme.css'), ('dot', '/assets/./theme.css'),
    ('encoded_dotdot', '/%2e%2e/outside/theme.css'), ('encoded_dot', '/%2e/app.js'),
    ('encoded_separator', '/assets%2ftheme.css'), ('encoded_backslash', '/assets%5ctheme.css'),
    ('backslash', '/assets\\theme.css'), ('nul', '/assets/%00theme.css'),
    ('bad_escape', '/%GG'), ('short_escape', '/%2'), ('invalid_utf8', '/%ff'),
    ('double_dotdot', '/%252e%252e/outside/theme.css'),
    ('double_separator', '/assets%252ftheme.css'), ('network_path', '//127.0.0.1/app.js'),
    ('absolute_form', 'http://127.0.0.1/app.js'),
    ('prefix_sibling', '/../dist-other/theme.css'), ('mixed', '/.%2e/outside/theme.css'),
    ('directory', '/assets'), ('missing', '/absent.css'),
]
cases(ResolveTests, 'a22_resolve', BAD_PATHS, lambda self, value: self.refused(value))


class StaticHTTPTests(ServerCase):
    def test_a23_component_replacement_cannot_disclose(self):
        server = self.start(race=True)
        response = server.request('/assets/theme.css')
        self.assertTrue(server.state['raced'].is_set(), 'Race control never reached asset open')
        self.assertIn(response.status, (200, 404))
        self.assertNotIn(b'OUTSIDE_SENTINEL', response.body)
        if response.status == 200:
            self.assertEqual(response.body, self.assets['assets/theme.css'])
        else:
            self.assert_error(response, 404)

    def test_a24_missing_build_named_error(self):
        (self.root / 'ui/dist').rename(self.root / 'saved-build')
        server = self.start()
        for path in ('/', '/index.html'):
            value = self.assert_error(server.request(path), 503, 'internal')
            self.assertEqual(value.get('detail'), 'UI build unavailable.')
        self.assertEqual(server.request('/api/health').status, 200)
        (self.root / 'saved-build').rename(self.root / 'ui/dist')
        self.assertEqual(server.request('/').status, 200)

    def test_a24_missing_index_is_not_missing_asset(self):
        (self.root / 'ui/dist/index.html').unlink()
        server = self.start()
        self.assert_error(server.request('/index.html'), 503, 'internal')
        self.assert_error(server.request('/absent.css'), 404)

    def test_a23_http_fifo_never_blocks(self):
        os.mkfifo(self.root / 'ui/dist/pipe')
        self.assert_error(self.start().request('/pipe'), 404)

    def test_a23_http_symlinked_root(self):
        dist = self.root / 'ui/dist'
        dist.rename(self.root / 'saved-build')
        dist.symlink_to(self.root / 'saved-build', target_is_directory=True)
        response = self.start().request('/app.js')
        self.assert_error(response, 404)
        self.assertNotIn(self.assets['app.js'], response.body)


def bad_http(self, target):
    response = self.start().request(target)
    self.assert_error(response, 404)
    self.assertNotIn(b'OUTSIDE_SENTINEL', response.body)
    self.assertNotIn(b'HOME_SENTINEL', response.body)


cases(StaticHTTPTests, 'a22_http', BAD_PATHS, bad_http)


def mime(self, value):
    path, expected = value
    response = self.start().request('/' + path)
    self.assertEqual(response.status, 200)
    self.assertEqual(response.body, self.assets[path])
    media = response.headers['content-type'].lower()
    self.assertEqual(media.split(';')[0], expected)
    if expected.startswith('text/') or expected in ('image/svg+xml', 'application/json'):
        self.assertIn('charset=utf-8', media.replace(' ', '').replace(chr(34), ''))


cases(StaticHTTPTests, 'a21_mime', [
    ('css', ('assets/theme.css', 'text/css')), ('js', ('app.js', 'text/javascript')),
    ('mjs', ('app.mjs', 'text/javascript')), ('svg', ('icon.svg', 'image/svg+xml')),
    ('json', ('data.json', 'application/json')), ('png', ('pixel.png', 'image/png')),
    ('woff2', ('font.woff2', 'font/woff2')),
], mime)
