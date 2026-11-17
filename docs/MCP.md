# MCP communication

Launch `python3 -m lineage --home HOME mcp`, or the executable and argument
array printed by `mcp-config`. Global `--home` precedes the verb. Use a private
home as described in [HEADLESS.md](HEADLESS.md). The config generator prints JSON
for Claude/generic clients and TOML for Codex without editing their settings.

MCP uses one UTF-8 JSON-RPC object per LF, not Content-Length framing. It supports
protocol `2024-11-05` and currently reports server version `0.1.0` from the
integrated adapter. Notifications, including `notifications/initialized`, have
no response. stdout contains only protocol replies. Discover installed tools
rather than assuming all contract tools are present.

`tools/list`, CLI `tools`, HTTP `/api/tools` and JSON-lane `capabilities` use the
same `{name,description,inputSchema}` descriptors. JSON capabilities are narrowed
by the recipient's configured allowlist; they equal the other surfaces when all
installed tools are granted. `tools/call` invokes the shared dispatcher and
returns `content:[{type:"text",text:SERIALIZED_RESULT}]` and `isError`.
Successful tool results are exactly `{untrusted:DATA}`. Domain failures are
`{ok:false,code:CODE,detail?:DETAIL}`, with `isError=true`; they remain successful
JSON-RPC responses. The integrated dispatcher also uses structured `detail` for
some schema diagnostics. Protocol/argument refusals use JSON-RPC errors instead.

| JSON-RPC code | Meaning |
| --- | --- |
| `-32700` | Invalid JSON or UTF-8. |
| `-32600` | Invalid request shape, including batches. |
| `-32601` | Unknown method. |
| `-32602` | Invalid params, unknown tool/resource/prompt, or unknown agent resource. |
| `-32603` | Internal/configuration failure or failed ledger-backed resource read. |

All content, including resource text, prompt arguments and tool results, is
passive data. Prompts render guidance; they never execute operations or grant
operator authority.

| Resource | Read behavior |
| --- | --- |
| `lineage://contract` | Bundled `docs/CONTRACT.md`, Markdown. |
| `lineage://guide/headless` | Bundled `docs/HEADLESS.md`, Markdown. |
| `lineage://guide/mcp` | Bundled `docs/MCP.md`, Markdown. |
| `lineage://agents` | `agent_list` through the dispatcher, first cursor page. |
| `lineage://agents/{agent_id}/record` | `agent_get` through the dispatcher. |
| `lineage://agents/{agent_id}/brief` | `agent_brief` with its default own-memory arm. |
| `lineage://agents/{agent_id}/memory` | `memory_history`, first cursor page; inspection can include private history. |
| `lineage://ledger/head` | `ledger_verify`, including head, digest and integrity checks. |

Live resources serialize the dispatcher's complete `{untrusted:…}` wrapper as
`application/json`. They read verified ledger state, never cached agent/memory
files. Use the ordinary tools and returned cursors to continue paginated lists.
A missing agent produces `-32602` with `unknown agent: ID`; an integrity failure
produces `-32603` with the error code and no host paths. Static documents use
confined, no-symlink reads. `resources/templates/list` advertises the agent record,
brief and memory URI templates plus the fixed ledger-head URI.

| Prompt | Arguments |
| --- | --- |
| `create_agent_from_spec` | `spec`: passive nonempty specification. |
| `breed_from_best` | `bench_id`: integrated API; inspect measured parents before breeding. |
| `run_benchmark` | `bench_id`: existing declared benchmark. |
| `resume_agent_from_memory` | `agent_id`: bootcheck, brief, memory routing, ledger cursor, next action. |
| `operate_lineage` | No arguments: discovery through verification. |

The integrated `breed_from_best(bench_id)` API differs from the older contract's
`parent_id`/`child_id` signature and is preserved. Resume requires independently
retained observations for `memory_bootcheck`: `agent_version`, `memory_gen`,
`head`, `entry_sha256`. Never synthesize an observed tuple from current state
merely to pass the gate. A failed bootcheck stops action until reconciled.

The following newline-framed requests are executed by `tests/comms` against a
private home containing the guide agent from the headless walkthrough.

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"example-client","version":"1"}}}
{"jsonrpc":"2.0","id":2,"method":"ping","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"agent_list","arguments":{}}}
{"jsonrpc":"2.0","id":5,"method":"resources/list","params":{}}
{"jsonrpc":"2.0","id":6,"method":"resources/templates/list","params":{}}
{"jsonrpc":"2.0","id":7,"method":"resources/read","params":{"uri":"lineage://guide/headless"}}
{"jsonrpc":"2.0","id":8,"method":"resources/read","params":{"uri":"lineage://guide/mcp"}}
{"jsonrpc":"2.0","id":9,"method":"resources/read","params":{"uri":"lineage://agents"}}
{"jsonrpc":"2.0","id":10,"method":"resources/read","params":{"uri":"lineage://agents/guide-agent/record"}}
{"jsonrpc":"2.0","id":11,"method":"resources/read","params":{"uri":"lineage://agents/guide-agent/brief"}}
{"jsonrpc":"2.0","id":12,"method":"resources/read","params":{"uri":"lineage://agents/guide-agent/memory"}}
{"jsonrpc":"2.0","id":13,"method":"resources/read","params":{"uri":"lineage://ledger/head"}}
{"jsonrpc":"2.0","id":14,"method":"prompts/list","params":{}}
{"jsonrpc":"2.0","id":15,"method":"prompts/get","params":{"name":"create_agent_from_spec","arguments":{"spec":"Create a Python reviewer using verified references."}}}
{"jsonrpc":"2.0","id":16,"method":"prompts/get","params":{"name":"breed_from_best","arguments":{"bench_id":"example_bench"}}}
{"jsonrpc":"2.0","id":17,"method":"prompts/get","params":{"name":"run_benchmark","arguments":{"bench_id":"example_bench"}}}
{"jsonrpc":"2.0","id":18,"method":"prompts/get","params":{"name":"resume_agent_from_memory","arguments":{"agent_id":"guide-agent"}}}
{"jsonrpc":"2.0","id":19,"method":"prompts/get","params":{"name":"operate_lineage"}}
```

For program-to-program envelopes, authorization and mailbox recovery see
[JSON_LANE.md](JSON_LANE.md). A bridge launch acknowledgement is separate from
application completion and a verified journal witness. End every workflow with
ledger verification; idempotent retries must retain the original caller `op_id`.
