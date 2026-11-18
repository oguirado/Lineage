"""Portable Lineage CLI and lazy seams for commands owned by other units."""
from collections.abc import Sequence
from contextlib import redirect_stdout
import importlib
import importlib.util
import sys
from typing import BinaryIO, TextIO

from . import app, registry as extensions
from .registry import Registry, RegistryError
from .schema import SchemaError, strict_loads

_HOOKS = {
    "run": ("lineage.core.supervisor", "main"),
    "hook": ("lineage.core.hook", "main"),
    "snapshot": ("lineage.core.snapshot", "main"),
    "export": ("lineage.core.export", "main"),
    "verify": ("lineage.core.events", "verify_main"),
    "json": ("lineage.core.jsonlane", "main"),
    "drain": ("lineage.core.family", "main"),
    "serve": ("lineage.serve.http", "main"),
    "operator": ("lineage.ext.memory", "operator_main"),
}
_HELP = """Lineage headless application
Usage: lineage [--home HOME] COMMAND
Commands:
  tools                         List installed tools
  call TOOL --json OBJECT [--dry-run]  Invoke a tool with strict JSON arguments
  run --agent ID --seat-model M --seat-effort E [OPTIONS] -- CMD ARGS...
                                Capture a native command run
  hook [--map FILE] [--verbose]  Capture one harness hook from stdin
  snapshot [--json]             Read compact verified orchestration state
  mcp                           Run the MCP stdio server
  doctor [--json | --operable]   Check local health without writes or network
  mcp-config [--client CLIENT] [--home HOME]  Print MCP config (claude/codex/generic)
  export --out DIR              Export through the owning command
  verify                        Verify through the owning command
  json                          Process a JSON envelope
  drain --endpoint NAME         Consume a configured mailbox
  serve                         Start the local application host
  operator ruling               Record an operator ruling
Use COMMAND --help for command help.
"""


def _emit(stdout: TextIO, payload: dict, code: int) -> int:
    import json
    stdout.write(json.dumps(payload, ensure_ascii=False, allow_nan=False,
                            sort_keys=True, separators=(",", ":")) + "\n")
    stdout.flush()
    return code


def _bad(stdout: TextIO) -> int:
    return _emit(stdout, {"ok": False, "code": "bad_args"}, 2)


def _delegate(module_name: str, hook_name: str, tail: list[str], *,
              context: app.CallContext, registry: Registry, stdin: BinaryIO,
              stdout: TextIO, stderr: TextIO) -> int:
    try:
        spec = importlib.util.find_spec(module_name)
    except ModuleNotFoundError as exc:
        # A missing parent is an absent optional command, whereas a dependency
        # failure during installed module execution is handled below.
        if exc.name and (module_name == exc.name or module_name.startswith(exc.name + ".")):
            return _bad(stdout)
        raise
    if spec is None:
        return _bad(stdout)
    module = importlib.import_module(module_name)
    hook = getattr(module, hook_name, None)
    if not callable(hook):
        if module_name == "lineage.ext.memory" and hook_name == "operator_main":
            return _operator_ruling(tail, context=context, registry=registry, stdout=stdout)
        return _bad(stdout)
    code = hook(tail, context=context, registry=registry, stdin=stdin,
                stdout=stdout, stderr=stderr)
    if type(code) is not int or code not in (0, 2, 3):
        return _emit(stdout, {"ok": False, "code": "internal"}, 3)
    return code



def _operator_ruling(tail, *, context, registry, stdout):
    """Adapt the installed domain writer when no extension CLI hook exists."""
    import hashlib
    from pathlib import Path
    from lineage.domain.memory import units
    from .errors import LineageError
    try:
        if len(tail) != 4:
            return _bad(stdout)
        options = dict(zip(tail[::2], tail[1::2]))
        if set(options) != {"--agent", "--quote-file"}:
            return _bad(stdout)
        quote = Path(options["--quote-file"]).read_bytes()
        # The domain owns the ruling's quote-derived operation identity. This
        # dedicated CLI carries no caller op_id and grants no tool authority.
        identity = hashlib.sha256((options["--agent"] + ":" + hashlib.sha256(quote).hexdigest()).encode()).hexdigest()
        command = extensions.Command("operator_ruling", {}, "operator", "ruling_" + identity[:57])
        services = extensions.Services(context.home, Path(__file__).resolve().parents[2], registry,
                                       token_count=None)
        ctx = extensions.Context(services, "operator", authority="operator", transport="cli")
        result = units.operator_ruling(options["--agent"], quote, command=command, ctx=ctx)
        return _emit(stdout, {"untrusted": result.value}, 0)
    except LineageError as exc:
        result = {"ok": False, "code": exc.code}
        if isinstance(exc.detail, str):
            result["detail"] = exc.detail[:2048]
        return _emit(stdout, result, 2 if exc.code == "bad_args" else 3)
    except (OSError, ValueError, UnicodeError):
        return _emit(stdout, {"ok": False, "code": "bad_args"}, 2)


def main(argv: Sequence[str] | None = None, *, stdin: BinaryIO | None = None,
         stdout: TextIO | None = None, stderr: TextIO | None = None,
         registry: Registry | None = None) -> int:
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    try:
        return _main(argv, stdin=stdin, stdout=stdout, stderr=stderr, registry=registry)
    except Exception:
        try:
            return _emit(stdout, {"ok": False, "code": "internal"}, 3)
        except Exception:
            return 3


def _main(argv: Sequence[str] | None, *, stdin: BinaryIO | None,
          stdout: TextIO, stderr: TextIO, registry: Registry | None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if any(type(arg) is not str for arg in args):
        return _bad(stdout)
    home = None
    if args[:1] == ["--home"]:
        if len(args) < 2 or not args[1] or args[1].startswith("-"):
            return _bad(stdout)
        home, args = args[1], args[2:]
    if not args or args in (["--help"], ["-h"]):
        stdout.write(_HELP)
        stdout.flush()
        return 0
    verb, tail = args[0], args[1:]
    if verb not in {"tools", "call", "mcp", "doctor", "mcp-config", *_HOOKS}:
        return _bad(stdout)
    if verb == "operator":
        if tail[:1] != ["ruling"]:
            return _bad(stdout)
        tail = tail[1:]
    if tail in (["--help"], ["-h"]):
        stdout.write(_HELP)
        stdout.flush()
        return 0
    if verb == "mcp-config":
        from . import mcpconfig
        return mcpconfig.main(tail, home=home, stdout=stdout)
    if verb == "doctor":
        from . import doctor
        return doctor.main(tail, home=home, registry=registry, stdout=stdout)
    if "--home" in tail and verb != "run":
        return _bad(stdout)
    if verb in ("tools", "mcp") and tail:
        return _bad(stdout)
    dry_run = verb == "call" and tail.count("--dry-run") == 1
    if dry_run:
        tail = [item for item in tail if item != "--dry-run"]
    if verb == "call" and (len(tail) != 3 or tail[1] != "--json"
                           or tail[0].startswith("-")):
        return _bad(stdout)
    if stdin is None:
        stdin = getattr(sys.stdin, "buffer", sys.stdin)
    try:
        with redirect_stdout(stderr):
            if registry is None:
                registry = extensions.load()
            context = app.create_context(home, registry=registry)
    except RegistryError as exc:
        return _emit(stdout, {"ok": False, "code": "bad_args", "detail": exc.detail}, 2)
    except app.ToolError:
        return _bad(stdout)
    if verb == "tools":
        return _emit(stdout, {"tools": app.list_tools(registry=registry)}, 0)
    if verb == "call":
        try:
            value = strict_loads(tail[2])
            if type(value) is not dict:
                raise SchemaError("type")
        except SchemaError as exc:
            return _emit(stdout, {"ok": False, "code": "bad_args",
                                  "detail": app.schema_diagnostic(exc)}, 2)
        with redirect_stdout(stderr):
            result = (app.preview if dry_run else app.dispatch)(tail[0], value, context=context, registry=registry)
        return _emit(stdout, result.payload, result.exit_code)
    if verb == "mcp":
        from . import mcp
        return mcp.main(context=context, registry=registry, stdin=stdin,
                        stdout=stdout, stderr=stderr)
    with redirect_stdout(stderr):
        return _delegate(*_HOOKS[verb], tail, context=context, registry=registry,
                         stdin=stdin, stdout=stdout, stderr=stderr)
