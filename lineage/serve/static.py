"""Single-decode URL confinement and descriptor-relative, no-follow reads."""
import errno
import os
from pathlib import Path
import re
import stat
from html.parser import HTMLParser
from urllib.parse import unquote_to_bytes, urlsplit

from lineage.core.errors import LineageError

_MIME = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
         '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
         '.svg': 'image/svg+xml; charset=utf-8', '.json': 'application/json; charset=utf-8',
         '.png': 'image/png', '.woff2': 'font/woff2'}


def _parts(url_path):
    if not isinstance(url_path, str) or not url_path.startswith('/') or url_path.startswith('//'):
        raise LineageError('bad_args')
    parsed = urlsplit(url_path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise LineageError('bad_args')
    raw = parsed.path
    if re.search(r'%(?![0-9a-fA-F]{2})|%(?:2f|5c)', raw, re.I):
        raise LineageError('bad_args')
    try:
        decoded = unquote_to_bytes(raw).decode('utf-8', 'strict')
    except (UnicodeError, ValueError):
        raise LineageError('bad_args') from None
    if any(c in decoded for c in ('\\', '\x00', '%')) or any(ord(c) < 32 for c in decoded):
        raise LineageError('bad_args')
    parts = ['index.html'] if decoded == '/' else decoded[1:].split('/')
    if any(p in ('', '.', '..') for p in parts):
        raise LineageError('bad_args')
    return parts


def _lookup_error(exc):
    if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
        return LineageError('bad_args')
    return LineageError('internal')


def resolve_asset(url_path: str, *, root: Path) -> Path:
    parts = _parts(url_path)
    candidate = root
    try:
        if not stat.S_ISDIR(candidate.lstat().st_mode):
            raise LineageError('bad_args')
        for i, part in enumerate(parts):
            candidate = candidate / part
            mode = candidate.lstat().st_mode
            if not (stat.S_ISREG(mode) if i == len(parts) - 1 else stat.S_ISDIR(mode)):
                raise LineageError('bad_args')
    except OSError as exc:
        raise _lookup_error(exc) from None
    return candidate


def _read_asset(url_path, *, root):
    # Resolution checks usability; only pinned descriptors authorize the later read.
    candidate = resolve_asset(url_path, root=root)
    parts = _parts(url_path)
    descriptor = None
    try:
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for i, part in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if i < len(parts) - 1:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise LineageError('bad_args')
        with os.fdopen(descriptor, 'rb') as source:
            descriptor = None
            data = source.read()
        return candidate, data
    except OSError as exc:
        raise _lookup_error(exc) from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


class _IndexParser(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.offsets = [0]
        for line in text.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))
        self.removals = []
        self.head = None

    def handle_starttag(self, tag, attrs):
        line, column = self.getpos()
        start = self.offsets[line - 1] + column
        end = start + len(self.get_starttag_text())
        if tag == 'meta' and any(k == 'name' and (v or '').casefold() == 'lineage-session-token' for k, v in attrs):
            self.removals.append((start, end))
        if tag == 'head' and self.head is None:
            self.head = end

    handle_startendtag = handle_starttag


def _bootstrap(data, token):
    text = data.decode('utf-8')
    parser = _IndexParser(text)
    parser.feed(text)
    insertion = parser.head or 0
    edits = [(a, b, '') for a, b in parser.removals]
    edits.append((insertion, insertion, '<meta name="lineage-session-token" content="' + token + '">'))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text.encode('utf-8')
