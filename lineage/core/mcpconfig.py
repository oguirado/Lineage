"""Print portable MCP client configuration; never open client settings files."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys


def configuration(*, client='generic', home=None) -> str:
    if client not in ('claude', 'codex', 'generic'):
        raise ValueError
    selected = home if home is not None else os.environ.get('LINEAGE_HOME') or '~/.lineage'
    if not os.fspath(selected):
        raise ValueError
    selected = str(Path(selected).expanduser().resolve())
    selected.encode('utf-8')
    executable = Path(__file__).resolve().parents[2] / 'bin' / 'lineage'
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError
    command = str(executable)
    command.encode('utf-8')
    args = ['--home', selected, 'mcp']
    if client == 'codex':
        text = ('[mcp_servers.lineage]\ncommand = ' + json.dumps(command, ensure_ascii=False)
                + '\nargs = ' + json.dumps(args, ensure_ascii=False) + '\n')
        return text.replace('\x7f', '\\u007f')
    return json.dumps({'mcpServers': {'lineage': {'command': command, 'args': args}}},
                      sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n'


def main(tail, *, home=None, stdout=None) -> int:
    from .cli import _emit
    stdout = sys.stdout if stdout is None else stdout
    try:
        if len(tail) % 2:
            raise ValueError
        options = {}
        for key, value in zip(tail[::2], tail[1::2]):
            if (key not in ('--client', '--home') or key in options
                    or not value or value.startswith('--')):
                raise ValueError
            options[key] = value
        if home is not None and '--home' in options:
            raise ValueError
        text = configuration(client=options.get('--client', 'generic'),
                             home=options.get('--home', home))
    except (ValueError, TypeError, OSError, RuntimeError):
        return _emit(stdout, {'ok': False, 'code': 'bad_args'}, 2)
    stdout.write(text)
    stdout.flush()
    return 0
