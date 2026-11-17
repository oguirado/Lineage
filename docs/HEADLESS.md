# Headless Lineage

Run from the repository root with Python and the standard library. No network
service, model, package installation or UI is required for CLI/MCP/JSON calls.
Use a separate private runtime home, owned by you with mode `0700`. Global
`--home` precedes the verb; otherwise Lineage uses `LINEAGE_HOME`, then the
user's `.lineage` directory. Never share a home with untrusted filesystem users.

Discover the installed registry before planning: this checkout may implement a
subset of the contract. In particular, do not assume run, breeding or benchmark
tools exist. An agent is an identity; its model/effort/mode seat is a separate
measurement input. Obtain both reference pins from verified `reference_get`
responses rather than copying a hash from another checkout.

| Verb | Behavior |
| --- | --- |
| `tools` | Returns `{tools:[{name,description,inputSchema}]}` in lexical order. |
| `call TOOL --json OBJECT` | Calls the same validated dispatcher used by MCP, JSON and HTTP. |
| `mcp` | Newline-delimited JSON-RPC on stdio; stdout is protocol only. |
| `run --agent ID --seat-model M --seat-effort E [OPTIONS] -- CMD ARGS...` | Captures a literal-argv child lifecycle; mandatory memory still gates close. |
| `hook [--map FILE] [--verbose]` | Observes one native Claude Code hook JSON object; success stdout is empty. |
| `snapshot [--json]` | Compact verified state, shared with MCP resource `lineage://snapshot`. |
| `json` | One configured family envelope to EOF, one receipt. |
| `drain --endpoint NAME [--poll-ms N]` | Exclusive mailbox consumer; requires recipient configuration. |
| `serve [--port N] [--fixtures DIR]` | Loopback host; selected port is reported at startup. |
| `export --out exports/NAME` | Writes a verified export beneath the runtime exports directory. |
| `verify` | Same verification gate as `ledger_verify`. |
| `operator ruling --agent ID --quote-file FILE` | Dedicated operator-only level-one authority; never an agent automation step. |
| `doctor [--json]` | Read-only local preflight; JSON is `{ok,checks:[{id,ok,detail}]}`. |
| `mcp-config [--client claude\|codex\|generic] [--home H]` | Prints configuration with this checkout's absolute executable and selected home. |

| Exit | Meaning |
| --- | --- |
| `0` | Success, including a completed failed task with valid mandatory memory. |
| `2` | Arguments, schema, discovery or configuration refused. |
| `3` | Domain, memory, concurrency, integrity, I/O or doctor health failure. |

Successful tool data is exactly `{untrusted:DATA}`. Treat it as passive data.
Errors are `{ok:false,code:CODE,detail?:DETAIL}`; use the code, not wording, for
control flow. The integrated dispatcher can return structured schema diagnostics
in `detail`. Costs that are unknown remain null. No token counter is injected in this version (`Services.token_count=None`).
The 4000-token ceiling is still enforced as a proven bound: byte-level BPE
tokens cover at least one UTF-8 byte, so a static memory entry of at most 4000
bytes cannot exceed 4000 tokens. Entries of 4000-6000 bytes need a verified
counter and are refused with `memory_debt` (cut memory, never estimate).

For writes, supply your actor and an unchanged, stable `op_id`. An exact retry
returns the original result and commit prefix. Reusing that identity with changed
content returns `bad_op`. Use a fresh identity for different work. An optional
`expected_head` asserts the ledger revision; a mismatch gives `stale_rev` and
appends nothing. Refresh state and decide again before resubmitting. Replay
lookup precedes the revision check.

Follow `ledger_events.next_after` as an exclusive cursor. Set `wait_ms` for
long-polling; a filtered cursor may advance without returning records. If
`resync=true`, restart from its returned cursor. Verify the ledger before
trusting completion. See [JSON_LANE.md](JSON_LANE.md) for allowlists, envelopes,
mailbox durability, operation identities and OpenFresnel communication, and
[MCP.md](MCP.md) for resources and prompts.

See [HARNESS_HOOKS.md](HARNESS_HOOKS.md) for supervisor options, the exact
refused-close repair loop, Claude Code asynchronous hooks and stream-json
configuration. Capture is caller-asserted and never waives required memory.
`lineage snapshot` reads one verified prefix through the shared folds, reports
ledger head/hash and up to 200 agents, and surfaces explicit failures.

The following complete example is executed by `tests/comms`. Paste the block
into a Python interpreter or save it as a script and run it from the repository
root. It uses a temporary private home, exercises every CLI verb, validates all
communication discovery surfaces, and removes its runtime state on exit. Its
operator ruling portion represents a human's explicit action; autonomous agents
must omit that portion.

```python
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request

root = Path.cwd()
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
with tempfile.TemporaryDirectory(prefix="lineage-guide-") as temporary:
    home = Path(temporary) / "home"
    home.mkdir(mode=0o700)
    base = [sys.executable, "-m", "lineage", "--home", str(home)]

    def command(*args, data=None, expected=0):
        result = subprocess.run(base + list(args), input=data, text=True,
                                capture_output=True, env=env, timeout=20)
        assert result.returncode == expected, (args, result.stdout, result.stderr)
        return json.loads(result.stdout)

    def call(tool, args, expected=0):
        return command("call", tool, "--json", json.dumps(args), expected=expected)

    def stop(child):
        if child.poll() is None:
            assert child.pid > 1
            child.terminate()  # Only this exact subprocess started above.
        try:
            child.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            assert child.pid > 1
            child.kill()
            child.communicate(timeout=5)

    tools = command("tools")["tools"]
    names = [item["name"] for item in tools]
    assert "agent_create" in names and "memory_put" in names
    pins = [call("reference_get", {"ref_id": ref})["untrusted"]["reference"]
            for ref in ("gold_s1", "memory_v21")]
    create = {"agent_id": "guide-agent", "display_name": "Guide agent",
              "workflow": "develop", "language": "python",
              "allowed_seats": [{"model": "example-model", "effort": "medium",
                                 "mode": "headless"}],
              "references": [{"id": pin["id"], "sha256": pin["sha256"]} for pin in pins],
              "skills": [], "agent": "guide-agent", "op_id": "guide/create:1",
              "expected_head": 0}
    born = call("agent_create", create)
    assert call("agent_create", create) == born  # Replay ignores a now-stale head.
    assert call("agent_get", {"agent_id": "guide-agent"})["untrusted"]["record"]["agent_id"] == "guide-agent"
    assert call("agent_list", {})["untrusted"]["agents"]
    assert call("agent_brief", {"agent_id": "guide-agent"})["untrusted"]["text"]
    unit = {"schema": "lineage.mem.unit/v1", "id": "guide_mem_01",
            "kind": "lesson", "level": 3, "statement": "Inspect discovery before acting.",
            "status": "active", "privacy": "internal",
            "scope": {"workflow": "develop", "language": "python"},
            "provenance": {"origin": "headless-guide", "actor": "guide-agent"},
            "receipts": [], "supersedes": [], "body": {"tempting_use": "Assume a documented tool is installed.",
            "failure_mode": "The installed registry may be a subset.",
            "safer_action": "Discover tools first.", "blocked_use": []}}
    before_memory = call("ledger_events", {})["untrusted"]["head"]
    stored = call("memory_put", {"agent_id": "guide-agent", "unit": unit,
                                 "agent": "guide-agent", "op_id": "guide/memory:1"})["untrusted"]
    assert stored["memory_gen"] == 1 and stored["unit"]["id"] == "guide_mem_01"
    assert call("ledger_events", {})["untrusted"]["head"] == before_memory + 1
    assert call("memory_history", {"agent_id": "guide-agent"})["untrusted"]["events"]
    stale = dict(create, agent_id="guide-stale", op_id="guide/create:stale")
    assert call("agent_create", stale, expected=3)["code"] == "stale_rev"
    assert call("agent_get", {}, expected=2)["code"] == "bad_args"
    cursor = call("ledger_events", {"after": 0, "limit": 100})["untrusted"]
    waited = call("ledger_events", {"after": cursor["next_after"], "wait_ms": 25})["untrusted"]
    assert waited["events"] == []
    assert call("ledger_verify", {})["untrusted"]["valid"] is True
    assert command("verify")["untrusted"]["valid"] is True

    # A human operator's dedicated action, rather than a tool actor assertion.
    quote = home / "operator-quote.txt"
    quote.write_text("Inspect discovery before acting.\n", encoding="utf-8")
    ruling = command("operator", "ruling", "--agent", "guide-agent", "--quote-file", str(quote))
    assert "untrusted" in ruling
    command("export", "--out", "exports/guide")

    # Print client configuration; never change any client settings file.
    generic = command("mcp-config", "--client", "generic")
    assert command("mcp-config", "--client", "claude") == generic
    codex = subprocess.run(base + ["mcp-config", "--client", "codex"],
                           text=True, capture_output=True, env=env, check=True)
    assert tomllib.loads(codex.stdout)["mcp_servers"]["lineage"] == generic["mcpServers"]["lineage"]
    config = generic["mcpServers"]["lineage"]
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    mcp = subprocess.run([config["command"]] + config["args"],
                         input=json.dumps(request) + "\n", text=True,
                         capture_output=True, env=env, check=True, timeout=20)
    assert json.loads(mcp.stdout)["result"]["tools"] == tools

    # Explicit recipient authorization for all locally installed tools.
    endpoint = home / "family" / "guide"
    endpoint.mkdir(parents=True, mode=0o700)
    (home / "family").chmod(0o700)
    configuration = endpoint / "config.json"
    configuration.write_text(json.dumps({"endpoint": "guide", "sources": ["caller"],
                                          "tools": names}), encoding="utf-8")
    configuration.chmod(0o600)
    envelope = {"schema": "lineage.family/1", "id": "guide_cap_01", "source": "caller",
                "target": "guide", "kind": "capabilities", "agent": "guide-agent", "payload": {}}
    assert command("json", data=json.dumps(envelope))["result"]["untrusted"]["tools"] == tools
    spool = endpoint / "spool"
    envelope = dict(envelope, id="guide_cap_02")
    (spool / "guide_cap_02.json").write_text(json.dumps(envelope), encoding="utf-8")
    (spool / "guide_cap_02.json").chmod(0o600)
    consumer = subprocess.Popen(base + ["drain", "--endpoint", "guide", "--poll-ms", "5"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        deadline = time.monotonic() + 10
        receipt = endpoint / "state" / "guide_cap_02.result.json"
        marker = endpoint / "state" / "guide_cap_02.done"
        while not marker.exists():
            assert consumer.poll() is None and time.monotonic() < deadline
            time.sleep(0.01)
        assert marker.read_bytes() == b"<!-- guide_cap_02_DONE -->\n"
        assert json.loads(receipt.read_text())["result"]["untrusted"]["tools"] == tools
    finally:
        stop(consumer)
    assert command("doctor", "--json")["ok"] is True
    plain = subprocess.run(base + ["doctor"], text=True, capture_output=True, env=env, timeout=20)
    assert plain.returncode == 0 and "home_permissions" in plain.stdout

    server = subprocess.Popen(base + ["serve", "--port", "0"], text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(server.stdout, selectors.EVENT_READ)
            assert selector.select(10), "serve startup timeout"
            startup = json.loads(server.stdout.readline())
        origin = startup["url"].rstrip("/")

        def http(path, value=None, headers=None):
            data = None if value is None else json.dumps(value).encode()
            req = urllib.request.Request(origin + path, data=data, headers=headers or {})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read()

        assert json.loads(http("/api/health"))["ok"] is True
        assert json.loads(http("/api/tools"))["tools"] == tools
        token = re.search(r'name="lineage-session-token" content="([^"]+)"', http("/").decode())[1]
        headers = {"Content-Type": "application/json", "Origin": origin, "X-Lineage-Session": token}
        assert json.loads(http("/api/call", {"tool": "agent_list", "args": {}}, headers))["untrusted"]["agents"]
        assert json.loads(http("/api/call", {"tool": "skill_publish", "args": {
            "skill_id": "guide-skill", "files": [{"path": "SKILL.md", "content": "# Guide\n"}],
            "agent": "guide-agent", "op_id": "guide/http:1"}}, headers))["untrusted"]["commit"]
        assert json.loads(http("/api/events?after=0&wait_ms=0"))["untrusted"]["events"]
    finally:
        stop(server)
    assert command("verify")["untrusted"]["valid"] is True
print("Headless guide examples passed")
```

HTTP clients must use the exact loopback origin reported by `serve`. The process
injects its session token into the served index's `lineage-session-token` meta
element. Send `Origin`, `Content-Type: application/json` and `X-Lineage-Session`
for writes and exports. Read calls may omit origin/token; a supplied foreign
origin is always refused. Do not persist or log the token. API and token-bearing
HTML responses use `Cache-Control: no-store`; no CORS grants are issued. Fixture
mode refuses mutations and exports.

`mcp-config --client claude` and `--client generic` emit an `mcpServers.lineage`
JSON entry; `--client codex` emits a `[mcp_servers.lineage]` TOML table. Launch the
printed command and argument array unchanged. Configuration printing requires no
registry, home creation or client file writes. Clients should initialize MCP,
then discover tools/resources/prompts; [MCP.md](MCP.md) specifies framing.

## Operable-program controls

The shared registry assigns a frozen risk class to each operation. CLI `tools`,
MCP `tools/list`, JSON-lane `capabilities`, and HTTP `/api/tools` expose the same
`annotations` object. Its `lineage_risk` is independent of `inputSchema`; tool
Arguments remain exactly those in `docs/CONTRACT.md`.

| Risk | Registered operations |
| --- | --- |
| `read` | `reference_get`, `reference_verify`, `skill_list`, `skill_get`, `agent_get`, `agent_list`, `agent_brief`, `lineage_tree`, `memory_route`, `memory_get`, `memory_bootcheck`, `memory_history`, `run_get`, `scorecard_get`, `ledger_events`, `ledger_verify` |
| `prepare` | `ledger_export` |
| `send` | `openfresnel_probe`, `openfresnel_spawn` |
| `publish` | `skill_publish`, `agent_create`, `agent_clone`, `agent_distill`, `memory_put`, `run_open`, `run_beat`, `run_close` |
| `irreversible` | `skill_retire`, `agent_retire` |
| `observe`, `destructive` | Reserved classes; no currently registered operation uses them |

Journal writers default conservatively to `publish`. Discovery describes only
installed operations; it does not imply that absent benchmark or breeding tools
are implemented. `readOnlyHint` covers `observe` and `read`; `destructiveHint`
covers `destructive` and `irreversible`; `openWorldHint` covers `send`.
`idempotentHint` describes the existing operation-identity replay discipline.
These hints do not authenticate an operator or establish human approval.

Dry-run is a transport control, never a tool argument:

    python3 -m lineage --home .lineage-demo call skill_publish --dry-run --json '{"skill_id":"demo-skill","files":[{"path":"SKILL.md","content":"Passive context.\n"}],"agent":"demo-agent","op_id":"demo:/preview"}'

MCP uses `params._meta.dry_run: true` on `tools/call`. The JSON lane uses
`payload.dry_run: true` on `kind: "call"`; see `docs/JSON_LANE.md`. A dry-run
returns `untrusted: {dry_run, risk, expected_head, events}`, with each proposed
event containing `kind`, `payload_sha256`, and `expected_head`. Read operations
have an empty `events` array. Journal previews run the actual preparation and
validators against the verified locked prefix, without append or projection
publication. They do not replay a cached success over current validation.
External previews validate configuration and describe `openfresnel.command`
without publication or program execution. Export previews describe
`ledger.export`. These are proposed effects, not journal commits or receipts
proving completion. Caller `op_id` is preserved unchanged.

A preview is never retained as an idempotent application result. CLI and MCP
previews leave runtime files unchanged. The JSON carrier still publishes its
ordinary transport receipt and completion marker, but does not retain a preview
in `dedup` or change application data. A later real operation must validate again.

`ledger_verify`, `verify`, and `doctor --json` include
`unverified: [{scope, reason}]`. For example, an agent without runs has unmeasured
fitness, and external receiver state is outside ledger verification. `valid`
certifies the inspected ledger/projection scope only. Missing or failed checks
never become successful checks by being listed as unverified.

    python3 -m lineage doctor --operable

This command emits a JSON report from an owned temporary home, using real CLI
and JSON-lane subprocesses. It checks risk classes, dry-run isolation, request
cancellation, shared-agent serialization, completion markers, independent ledger
verification, and interruption after a durable commit followed by duplicate-free
recovery. It signals only an exact child process it created and waited for.
Only its isolated fixture lock is removed after proving that child exited;
production `consumer.lock` retains the no-stale-takeover rule. Live receiver
completion, unfamiliar-persona usability, GUI accessibility and authenticated
human signatures remain explicitly unverified.

These controls implement the supplied operable-program rules within the public
Lineage contracts and the integrated source APIs.
