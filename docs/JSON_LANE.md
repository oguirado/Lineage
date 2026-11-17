# JSON lane

`lineage.family/1` is a strict, headless recipient-owned transport. A request is
one JSON object; stdio reads it to EOF and writes one canonical receipt plus LF.
Diagnostics use stderr. JSON keys are sorted, Unicode remains UTF-8, and hashes
exclude LF. Duplicate keys, invalid Unicode, non-finite numbers, unsafe integers,
trailing JSON, unknown fields and legacy room/lifecycle messages are refused.
The raw request cap is 65536 bytes [TARGET], including whitespace and LF.
Integers range from -9007199254740991 to 9007199254740991 [TARGET]. Container
nesting is limited to 64 levels [TARGET]. Boolean values are not integers.

The operator must first supply the recipient configuration. The transport never
creates an allowlist. Control directories, starting at the runtime home, must be
owned by the current user and must forbid group and world writes. Configurations
and control/request/result files must be owned regular files without hard links
or symlinks. An endpoint starts with an ASCII letter or digit and otherwise uses
letters, digits, underscores or hyphens, up to 64 characters [TARGET]. A request
id uses the same characters, has length 8 through 64 [TARGET], and cannot be
`invalid0`, which is reserved for unidentifiable malformed-input receipts.

The public layout is relative to the runtime home:

| Member | Purpose |
| --- | --- |
| `family/Endpoint_1/config.json` | Required explicit configuration |
| `family/Endpoint_1/consumer.lock` | Exclusive ownership, shared by both carriers |
| `family/Endpoint_1/spool/<id>.json` | Incoming requests, including durable stdio admission |
| `family/Endpoint_1/state/<id>.result.json` | Receipt data; incomplete until its marker exists |
| `family/Endpoint_1/state/<id>.done` | Exact completion sentinel, durably published last |
| `family/Endpoint_1/state/quarantine-*` | Unsafe request entries, moved without opening targets |
| `family/Endpoint_1/dedup/<id>.json` | Pending or complete identity retention |

For example, explicitly create a private demonstration home and write this
configuration to its `family/Endpoint_1/config.json` before using either carrier:

```json
{"endpoint":"Endpoint_1","sources":["Sender_1"],"tools":["ledger_events","skill_list","skill_publish"]}
```

Run this setup from the repository root, using a new demonstration home. The
explicit modes also protect directories that already exist:

```sh
umask 077
mkdir -p .lineage-demo/family/Endpoint_1
chmod 700 .lineage-demo .lineage-demo/family .lineage-demo/family/Endpoint_1
cat > .lineage-demo/family/Endpoint_1/config.json <<'JSON'
{"endpoint":"Endpoint_1","sources":["Sender_1"],"tools":["ledger_events","skill_list","skill_publish"]}
JSON
chmod 600 .lineage-demo/family/Endpoint_1/config.json
```

Missing, symlinked or unsafe configuration and control paths return `bad_args`
with one concise diagnostic on stderr. The path is relative to the runtime home
(`.` denotes the home itself); configuration contents never appear. For example:
`lineage json: refused family/Endpoint_1/config.json: group/world writable (chmod 600)`.
This diagnostic is separate from the JSON receipt, whose result remains exactly
`{"ok":false,"code":"bad_args"}`.

An empty `sources` list grants no sender access. An empty `tools` list grants no
execution. Tool names must be frozen public names and must also be installed in
the shared registry to execute. This transport does not install domain handlers.
Capabilities describe only the current registered/configured intersection, using
unchanged `{name,description,inputSchema}` descriptors in lexical order.

Save this capabilities request as `capabilities.json`:

```json
{"schema":"lineage.family/1","id":"discover01","source":"Sender_1","target":"Endpoint_1","kind":"capabilities","agent":"alice","payload":{}}
```

```sh
python3 -m lineage --home .lineage-demo json < capabilities.json
```

This exits successfully with `result.untrusted.health="ready"`, the protocol
`lineage.family/1`, and descriptors for `ledger_events`, `skill_list` and
`skill_publish`.

Save this cursor read as `cursor.json`. `after` is an exclusive Lamport cursor;
filters preserve scanned cursor advancement and after-head resynchronization.
An unreadable journal cannot return an empty success. Events require the
`ledger_events` grant and its installed handler.

```json
{"schema":"lineage.family/1","id":"cursor001","source":"Sender_1","target":"Endpoint_1","kind":"events.read","agent":"alice","after":0,"payload":{"limit":100,"wait_ms":0,"kinds":[]}}
```

```sh
python3 -m lineage --home .lineage-demo json < cursor.json
```

An empty `kinds` list means all event kinds, as does omitting `kinds`. The lane
removes an empty list before tool validation; the frozen tool schema is unchanged.
On the new demonstration home this exits successfully with
`result.untrusted.events=[]` and `result.untrusted.head=0` [TARGET]. Use a fresh
request id to observe a later journal prefix.

Save this journal call as `publish.json`. Calls use the ordinary domain handler,
including its validator, ownership, revision, memory and authorization gates.

```json
{"schema":"lineage.family/1","id":"publish01","source":"Sender_1","target":"Endpoint_1","kind":"call","agent":"alice","correlation_id":"example01","payload":{"tool":"skill_publish","args":{"skill_id":"example-skill","files":[{"path":"SKILL.md","content":"# Example\n"}]}}}
```

```sh
python3 -m lineage --home .lineage-demo json < publish.json
python3 -m lineage --home .lineage-demo json < publish.json
```

Both invocations exit successfully with the published `example-skill` and a
`commit` under `result.untrusted`, echoing `correlation_id="example01"`.
The second invocation is an exact retry: it returns the original committed
result, including the original commit prefix, without appending another event.
Formatting changes preserve the canonical digest. To exercise collision refusal,
save the following changed request as `changed.json`, then run the command below
it after completing `publish.json`:

```json
{"schema":"lineage.family/1","id":"publish01","source":"Sender_1","target":"Endpoint_1","kind":"call","agent":"alice","correlation_id":"example01","payload":{"tool":"skill_publish","args":{"skill_id":"changed-skill","files":[{"path":"SKILL.md","content":"# Example\n"}]}}}
```

```sh
python3 -m lineage --home .lineage-demo json < changed.json
```

This exits with `3` [TARGET], returns `result={"ok":false,"code":"bad_op"}`
and preserves original retention and journal bytes. Use a
fresh id to request a different operation. The envelope's complete canonical
SHA-256 digest binds source, target, actor, kind, arguments and optional context.
The separate `op_id` is `lin-` followed by 44 lowercase hex characters [TARGET]
from SHA-256 of UTF-8 `source + NUL + target + NUL + id`.

The transport injects `agent` into every effective tool argument object and
`op_id` for journal/external effects. Explicit client arguments named `agent` or
`op_id` are refused. Caller context is reconstructed with tool authority and
`transport="json"`; an `operator` actor grants no operator authority. Defaults
are inserted before registered argument validation. Optional envelope `run_id`
is correlation only; it cannot supply a missing tool argument and must match an
argument `run_id` when present. Valid `correlation_id` is echoed without invention.

A successful receipt contains exactly `result={"untrusted":data}`. A failure
contains `result={"ok":false,"code":...}` with optional sanitized bounded detail.
Both receipt and actual tool result alternatives are checked against the frozen
schemas. `publish(identity, result, envelope=None)` takes the request id;
correlation is omitted when no envelope is supplied.

| Exit | Meaning |
| --- | --- |
| `0` [TARGET] | Successful dispatch, including a valid domain result for a failed task |
| `2` [TARGET] | `bad_args`: malformed input, missing/unsafe config, denied grant or held consumer lock |
| `3` [TARGET] | Domain refusal, `bad_op` collision, corrupt recovery or internal I/O failure |

A malformed object with an unambiguous strictly decoded valid id uses that id.
Invalid syntax, duplicate keys or encoding errors use `invalid0`. No regex or
permissive parser recovers an id. Multiple envelopes cannot partially execute.

For continuous mailbox delivery:

```sh
python3 -m lineage --home .lineage-demo drain --endpoint Endpoint_1 --poll-ms 25
```

The default interval is 25 ms [TARGET], with an inclusive range of 1 through
60000 ms [TARGET]. Producers publish `<id>.json` into `spool` in lexical delivery
order using an adjacent temporary, complete write, file fsync, atomic rename and
directory fsync. Temporary publications and result files are ignored. Unsafe or
non-id request basenames are quarantined; a malformed or mismatched body gets a
`bad_args` receipt only under its validated basename stem, never its body id.

Only one consumer owns an endpoint. Stdio immediately returns `bad_args` with
exit `2` [TARGET] while drain or another stdio consumer holds `consumer.lock`.
There is no timestamp/PID takeover. A lock left after abrupt termination requires
explicit operator recovery outside this protocol. Release removes only the exact
owned inode, and reports replacement. Graceful interruption closes owned resources.

All accepted non-preview requests bind their identity in retention, including reads. Cursor
read retries retain their original page; use a fresh id for a fresh observation.
Capabilities re-evaluate the currently granted registry intersection on retry,
while retaining the original digest binding. Direct `jsonlane.dispatch` also
acquires ownership and uses retention; direct `Mailbox.dispatch` requires an open
owned mailbox. Its config is re-read on every delivery, before retained lookup
and before execution. Revoked permission cannot disclose retained data.

Durability proceeds as follows: durable `pending` retention; ordinary handler
execution/replay; verified application witness; durable `complete` retention;
durable result publication; durable completion marker; removal of the original
request and directory fsync.
Only a terminal receipt followed by safe request removal increments sweep count.
`busy`, `internal` and uncertain external `timeout` stay pending, keep their
request and may publish a failure receipt. Drain spaces retries with in-memory
exponential backoff, from 1 second up to 32 seconds [TARGET], instead of dispatching
the same transient failure on every poll. A deterministic domain refusal is
retained; a new id requests evaluation after domain state changes.

A crash after commit is recovered by invoking the original registered handler
with the same operation identity. The journal deduplicates under its own lock;
no journal snapshot stays locked across dispatch. Projection files are not
witnesses. A journal success must match the verified event ids, actor, head and
hash. Compound operations may use deterministic child identities consisting of
the root operation id, a hyphen and an ASCII alphanumeric/underscore/hyphen suffix
of 1 through 15 characters [TARGET]; their returned Commit links the selected
verified events. No fictitious root event is required. A forged result file or
complete record without this witness fails recovery.

External handlers receive the same deterministic `op_id` on uncertain retry and
own their remote retry protocol. An acknowledgement with `state="launched"`
remains an acknowledgement. It proves neither application completion nor a closed
memory gate. This guide makes no live interoperability or persona/capsule claim.

The installed application exposes `CallContext`, explicit `registry` arguments,
`DispatchResult.payload`, `ToolSpec.mutating` and verified tuple journal snapshots.
The lane adapts these interfaces privately; it does not add aliases to dependency
modules or bypass their handlers. This guide is scoped to the supplied public
Lineage contracts and installed application interfaces.

## Operable-program transport additions

These carrier additions leave every registered tool Arguments schema unchanged.
They are validated explicitly by the carrier around the frozen K0 envelope and
receipt shapes; `schemas/` is not rewritten. Discovery descriptors gain the
standard MCP `annotations` hints and `annotations.lineage_risk`, with identical
values on CLI, MCP and HTTP. The full risk table is in `docs/HEADLESS.md`.

For `kind: "call"`, the optional Boolean `payload.dry_run` is outside
`payload.args`. Other kinds refuse this flag. For example:

    {"schema":"lineage.family/1","id":"preview_01","source":"Sender_1","target":"Endpoint_1","kind":"call","agent":"demo-agent","payload":{"tool":"skill_publish","args":{"skill_id":"demo-skill","files":[{"path":"SKILL.md","content":"Passive context.\n"}]},"dry_run":true}}

A successful preview returns `untrusted: {dry_run: true, risk, expected_head,
events}`. Proposed events contain `kind`, `payload_sha256`, and `expected_head`.
Journal preparation and validators inspect the current verified prefix without
append. External tools never publish commands or start programs. No preview is
stored in `dedup`; repeating a preview observes the current snapshot. Transport
request/receipt publications still occur. Explicit `false` follows ordinary
execution and retention. `ledger_verify` additionally returns the closed
`unverified: [{scope, reason}]` list described in the headless guide.

Cancellation is an order: publish an owned regular
`family/<endpoint>/spool/<id>.abort` using the same confinement, ownership,
permission and no-link rules as request files. The body carries no authority;
the exact basename selects only that request. Unsafe entries are quarantined
without following their targets. A cancellation before commit produces:

    {"ok":false,"code":"bad_op","detail":"cancelled by order"}

`cancelled` is absent from the fixed error vocabulary, so this explicit mapping
uses `bad_op`. It is a domain refusal. The consumer continues processing other
requests. The abort is checked before dispatch and again immediately before a
journal commit under the ledger lock. Cancellation linearizes at that last
check. An already committed operation, including a pending delivery recovered
after a crash, returns its committed receipt; cancellation never rolls it back.
A cancelled preview is not retained. Normal cancellation results are retained.
External cancellation is checked before entering the external handler; live
receiver-side cancellation is not claimed.

Every receipt publication also produces `state/<id>.done` with exactly:

    <!-- <id>_DONE -->

The marker includes a final LF. The consumer first removes any prior marker,
then durably publishes the receipt, and publishes the marker last using file
fsync, atomic rename, and directory fsync. A receipt without its exact sibling
marker is **in progress**, including after an interrupted re-publication.
Readers must validate the marker before consuming the receipt;
`Mailbox.completed(id)` returns `None` until that condition holds. The marker
means receipt publication completed; inspect `result` to determine success or
refusal. Retention and the application witness remain necessary for replay: a
marker alone does not prove a journal mutation.
