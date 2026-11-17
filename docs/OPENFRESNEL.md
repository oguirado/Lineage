# OpenFresnel client boundary

`openfresnel_probe` and `openfresnel_spawn` are headless external mutations.
Their extension exports the exact closed discovery schemas in
[CONTRACT.md](CONTRACT.md), with `mutating=True` and no application validators
or folds. Imports and discovery publish nothing. Adapters use the shared
registry and return inner data; dispatch supplies exactly one `untrusted`
wrapper. No alternate dispatcher or local terminal launcher is provided.

## Current compatibility gates

The authoritative outgoing command schema, operation-specific receipt nesting,
remote error grammar, argv carrier, JSON stdin/EOF mechanism and durable receiver
deduplication contract are **AUSENTE — no inventar**. Under SPEC_U20 Amendment B
and M27, the client validates arguments and configuration, then refuses with
`internal` without publication. `parse_receipt` strictly refuses unsupported or
insufficient evidence; no positive receiver shape is guessed. This is an
implemented admission boundary, not a functioning receiver integration.

The exact spawn descriptor retains `$ref: family_envelope.schema.json`.
The installed memory-domain registry facade supports schema-aware descriptor
preflight. The extension initializes that facade and uses its actual
`ToolSpec(name, description, input_schema, effect, handler)` constructor.
Its `journal` descriptor value retains `mutating=True`; U05 explicitly
classifies both bridge names as external acknowledgements. The handlers do
not enter the memory-contract dispatcher or create journal events. Full
registry loading preserves both exact discovery schemas without publication.

Generic shared instance validation still does not support `$ref`, so the
spawn transport-validation portion of A3 remains blocked. The bridge changes
no shared validator and does not weaken discovery schemas. Direct adapter
validation composes structural outer checks with U05's actual frozen
envelope validator, including nested call arguments.
The integrated dispatcher classifies handler configuration errors as execution
failures, so missing configuration currently has CLI exit 3 [MEASURED: integrated
control flow], contrary to required exit 2 [TARGET]. A30 requires an upstream
classification fix; the bridge does not mask that discrepancy.

U05's JSON lane is present and explicitly classifies both bridge operations as
external. Its one-shot replay can be tested at the client seam, but this proves
neither receiver publication nor durable terminal deduplication. Full transport
acceptance, HTTP integration, live interoperability and headless terminal
parity remain blocked or AUSENTE. No historical acknowledgement changes these
gates. A green default suite is not ADMIT.

## Configuration

Selection order is:

1. Explicit `commands_dir`.
2. `LINEAGE_OPENFRESNEL_COMMANDS_DIR`, including an explicitly empty value.
3. `paths.commands_dir` in an explicitly named `contract_file`.

An absent source permits the next source; an invalid selected source gives
`bad_args` and never falls through. Unused lower-priority sources are not opened.
No workspace search, metadata discovery, default commands directory or implicit
creation occurs. Tool arguments reject explicit null configuration.

For example, set `LINEAGE_OPENFRESNEL_COMMANDS_DIR` to an existing runtime
`COMMANDS_DIRECTORY`, or supply `commands_dir` explicitly. These symbols stand
for caller configuration, not paths to be copied literally. A named contract
contains `{"paths":{"commands_dir":"COMMANDS_DIRECTORY"}}`, substituting an
absolute runtime path. Relative contract directory values are refused. Explicit
and environment paths may be relative to the caller's working directory.

Selected directories may be outside the effective Lineage home. Every lexical
component is opened descriptor-relatively with `O_NOFOLLOW` and `O_DIRECTORY`;
a symlink preceding `..` is still refused. Inodes are rechecked around use.
A contract must be a regular, nonsymlink file without symlinked ancestors.
Configuration strings reject NUL, C0, DEL and invalid Unicode before filesystem
calls. Errors never contain configured paths or raw exception filenames.

Contract input is strict UTF-8 JSON, bounded to 1048576 bytes [TARGET]. Duplicate
keys, non-finite values, trailing JSON and unpaired surrogates are rejected.
The integrated `strict_loads` cap is 65536 bytes [MEASURED: shared source]; the
client uses a private standard-library decoder for larger permitted contracts
with the same strict value checks. It changes no shared decoder or schema.

## Argument and identity contracts

Both tools require caller-asserted `agent` and `op_id`. Optional fields are
`commands_dir`, `contract_file`, and `timeout_ms`; unknown fields, including
`rid`, `argv`, gate, receipt family and `expected_head`, are rejected. The
argument shapes and exact string patterns are those in CONTRACT.md.
The tool byte ceiling is 1048576 bytes [TARGET]. Timeout is a non-Boolean integer
in 1..60000 ms [TARGET], default 20000 ms [CITED: K0 channel contract]. Defaults
are applied before comparing intent. Effective context actor/op identities,
when present, must agree before filesystem access. `operator` and `system`
remain ordinary caller-asserted actors; they confer no operator authority.

`openfresnel_spawn` requires `mode`:

- `json` requires `envelope` and forbids `endpoint`. The strict
  `lineage.family/1` envelope is bounded to 65536 canonical UTF-8 bytes
  [CITED: K0 family contract]. Nested unknown keys, reserved `invalid0`,
  actor/op smuggling and invalid call arguments are refused by U05 validation.
- `drain` requires the exact validated endpoint and forbids `envelope`.

Canonical JSON uses sorted keys, compact separators, UTF-8, `ensure_ascii=False`
and `allow_nan=False`, without a trailing newline for hashing. The required
request identity is the first 32 lowercase hexadecimal characters [TARGET]
of SHA-256 over canonical `{"agent":agent,"op_id":op_id}`. U05 first injects its
`lin-` operation identity derived from source, target and request id; the bridge
must preserve it. Identity publication/restart assertions remain blocked until
the command ABI exists; no runtime publication claim is made here.

## Required publication, recovery and observation

Once an authoritative ABI is supplied, the protocol filenames are `<rid>.tmp`,
`<rid>.json` and `<rid>.result.json` under the configured commands directory.
Publication must finish writing and fsync the owned temporary before atomic
rename and directory fsync. Descriptor-relative operations must refuse unsafe
entries and replacements; cleanup may remove only the attempt's owned temporary.
There is currently no publisher because inventing command keys would violate
M27. Atomic publication positives and fault controls remain explicitly blocked.

Exact retry must preserve rid and command bytes across timeout and restart;
changing only the local timeout does not change remote intent. Changed tool,
mode, endpoint or envelope under retained identity must give `bad_op`, preserving
the prior request. Same-target retained-intent comparison belongs to the bridge;
cross-target retention belongs to U05. No private home-state layout is invented.
Uncertain publication, timeout or a late result never proves absence of remote
execution or exactly-once behavior. Only continued result absence up to a
monotonic deadline gives `timeout`; malformed or unreadable present results give
`internal`. These receiver-dependent paths are blocked, not tested as passing.

## Receipts and errors

The separate receipt families have necessary but insufficient discriminators:

| Family | Required discriminator and evidence |
|---|---|
| compiler | `status` exactly `ok`, `accepted` or `error`; echoed request identity/op and typed operation data required. Correlation/data nesting and error payload grammar remain AUSENTE. |
| deck | Boolean `ok`, integer `api_version:2` [CITED: Deck ABI], matching `request_id` and `op`; typed operation-data nesting/error grammar remain AUSENTE. Boolean or float versions are refused. |
| mixed/unknown | Refused with `internal`, regardless of which discriminator appears affirmative. |

A status alone never establishes capabilities, availability or launch. Pure
`parse_receipt` does not mutate input or touch files, validates direct dictionary
values (including nested non-finite values and Unicode), and discards remote
text. Its fixed diagnostics contain no remote controls, secrets, paths,
tracebacks or instructions. Generated details are bounded sanitized strings;
remote codes never become arbitrary wire codes.

The future closed probe result is `{rid,available:true,verbs,receipt_family}`;
a present empty verbs array is valid, an absent array is not. The future closed
spawn result is `{rid,state:"launched",terminal_id,pane_id,screen_id,receipt_family}`.
Terminal identity is required; unavailable pane/screen identity is explicit null.
These are normalized contract results, not accepted receiver wire fixtures.

| Code | Required surface classification |
|---|---|
| `bad_args` | Invalid arguments/configuration; CLI exit 2, HTTP 400 [TARGET]. Handler configuration exit classification remains blocked upstream. |
| `bad_op` | Retained identity reused for changed command intent; CLI exit 3, HTTP 409 [TARGET]. |
| `conflict` | Documented remote conflict or safe publication collision; CLI exit 3, HTTP 409 [TARGET]. |
| `timeout` | Continued absence until deadline; CLI exit 3, HTTP 504 [TARGET]. |
| `internal` | Unsupported/malformed receipt, unproven receiver binding or unexpected I/O; CLI exit 3, HTTP 500 [TARGET]. |

Failures have exactly `{ok:false,code,detail?}`. Shared transports own CLI/MCP/JSON/
HTTP wrappers, error routing and HTTP origin/session/fixture authorization.
Source-backed remote failure translation is blocked until its grammar exists.

## Launch and application completion

Required launch argv uses the current `sys.executable`, `-m`, `lineage`, global
`--home` with the caller's effective home, then `json`; or `drain`, `--endpoint`,
and the validated endpoint. It is an array, never shell text. JSON must deliver
the exact canonical envelope to child stdin followed by EOF through a documented
receiver mechanism; drain has no envelope input. That carrier is AUSENTE, so no
launch is published, no invented stdin field is emitted and no subprocess is
started by the bridge. Envelope quotes and shell metacharacters remain data.

The child must follow U05 recipient configuration, source/tool allowlists and
actor/op injection. A terminal acknowledgement can mean only `launched`, never
application completion. It cannot create or close a run, pay memory debt,
append an application ledger event, establish benchmark fitness or fabricate a
commit. Application completion needs a separate U05 receipt and, for a journal
mutation, a verified matching ledger witness.

## Hermetic verification and evidence

U05 refuses group-writable recipient directories and configuration files.
The reconciled fixtures create an owner-only home, family directory, recipient
and configuration explicitly, independently of the runner's umask. The default
oracle command is:

```text
python3 -m unittest discover -s tests/bridge -t .
```

The repair regressions load the full registry without publication, preserve the
frozen descriptor schemas, check U05's external classification, exercise fixture
creation under a permissive umask and require writable configuration to fail.
Existing replay, operation identity, source authorization and ledger-isolation
assertions remain unchanged. See the Amendments A-U20 section of
[the oracle inventory](../tests/bridge/ORACLE.md).

Tests use disposable directories, fake observers, hostile receipt values,
descriptor-swap faults, virtual time and client-seam doubles. No real terminal,
network, model, installation or external project modification occurs. A fake
observer checks generic canonical JSON only; it supplies no invented positive
receiver fixture. Adapter tests exercise actual shared CLI/MCP and U05 one-shot
replay with a doubled client; this is bounded transport evidence only.

Run prerequisites separately:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.bridge.upstream_gates
```

This suite deliberately reports blocked assertions, never skipped or passing
gates. It covers schema loading, CLI classification, missing receiver command/
receipt/stdin/dedupe contracts, publication/retry controls, full transport and
live compatibility proofs. Specified, stub-red, fake-observer-green,
transport-integrated and live-verified evidence are distinct. Live OpenFresnel
interoperability, terminal parity and production dedupe evidence are AUSENTE.
