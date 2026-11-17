# Lineage K0 Python interfaces

This is an implementation target, not implemented code or a test receipt. Runtime evidence is AUSENTE. All numerical bounds in this document are [TARGET] unless tagged [CITED]. The normative wire shapes, defaults, tools and errors are in `docs/CONTRACT.md` and the eight `schemas/*.schema.json` files. Standard-library Python 3.12 [CITED: campaign technical base] is the core implementation language. TypeScript is confined to the UI. No module imports a transport to implement domain policy.

## Shared types and ownership

[K0 decision] The following frozen dataclasses and aliases live in `lineage/core/registry.py` except LineageError (`errors.py`) and the schema aliases (`schema.py`). Signatures below include self where applicable. These definitions specify cross-module calling conventions; they do not require a new shared module.

```python
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

JSONValue = type(None) | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
JSONObject = dict[str, JSONValue]
Data = JSONObject
Event = JSONObject
Agent = JSONObject
MemoryUnit = JSONObject
Run = JSONObject
BenchDeclared = JSONObject
BenchResult = JSONObject
BenchVerdict = JSONObject
Seat = JSONObject
Cost = JSONObject
Outcome = JSONObject
Evidence = JSONObject
Cursor = JSONObject
Verification = JSONObject
State = dict[str, JSONObject]
Clock = Callable[[], int]                 # epoch milliseconds, never floating seconds
IdFactory = Callable[[], str]             # e- plus 16 lowercase hex characters
TokenCounter = Callable[[str], int]       # verified reference-compatible counter
Authority = Literal["tool", "operator"]
Effect = Literal["read", "journal", "external"]

@dataclass(frozen=True)
class Command:
    tool: str
    args: JSONObject                    # validated effective args, defaults inserted
    agent: str
    op_id: str
    expected_head: int | None = None

@dataclass(frozen=True)
class EventDraft:
    kind: str
    payload: JSONObject
    evidence: tuple[Evidence, ...] = ()

@dataclass(frozen=True)
class Snapshot:
    events: tuple[Event, ...]
    head: int
    raw_head_sha256: str | None          # None for a known empty prefix
    state: State

@dataclass(frozen=True)
class Committed:
    event: Event
    value: Data                          # inner result, includes Commit where specified
    head: int
    sha256: str                         # event.sha256, not raw line digest

@dataclass(frozen=True)
class Services:
    home: Path
    repo_root: Path
    registry: "Registry"
    clock: Clock
    id_factory: IdFactory
    token_count: TokenCounter | None

@dataclass(frozen=True)
class Context:
    services: Services
    actor: str
    authority: Authority = "tool"
    transport: Literal["library", "cli", "mcp", "json", "http"] = "library"

Prepare = Callable[[Snapshot], EventDraft]
Render = Callable[[Snapshot, Event], Data]
Handler = Callable[[JSONObject, Context], Data]
Validator = Callable[[Snapshot, Event, Context], None]
Fold = Callable[[State, Event], None]

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: JSONObject
    effect: Effect
    handler: Handler

@dataclass(frozen=True)
class FoldSpec:
    kinds: frozenset[str]
    order: int
    apply: Fold
```

Handlers use positional `(args, ctx)` to match Handler. Domain functions below use keyword-only ctx. Schema records are JSON dicts, not object instances with implicit fields. Public functions return defensive data copies; callers cannot mutate the authoritative snapshot. Context is created by the runtime, never deserialized from tool input. Only the operator CLI branch may set authority=operator; all transport tools force tool authority even if args.agent is operator. No caller can supply an already-passed gate.

State has namespaces `references`, `skills`, `memory`, `agents`, `runs`, `arena`, `scorecards`, `tree`, `promotion`. Each fold owns its namespace. Agent status from consecutive failures is an immutable-journal-derived fold result, not an edit to agent.json. Expensive projection I/O runs after durable commit; a failed projection write leaves the event durable, reports internal, and an exact retry rebuilds before returning the original logical result. A read consults folds, never mutable agent files.

## Errors and strict schema API

```python
# lineage/core/errors.py
class LineageError(Exception):
    code: str
    detail: str
    def __init__(self, code: str, detail: str = "") -> None: ...

def error_payload(exc: Exception) -> JSONObject: ...

# lineage/core/schema.py
class SchemaStore:
    def __init__(self, root: Path) -> None: ...
    def load(self, name: str) -> JSONObject: ...
    def resolve(self, reference: str, *, base: str) -> JSONObject | bool: ...

def decode(raw: bytes, *, max_bytes: int = 1048576) -> JSONValue: ...
def canonical(value: JSONValue) -> bytes: ...
def digest(value: JSONValue) -> str: ...
def validate(value: JSONValue, schema: JSONObject | bool, *,
             store: SchemaStore, base: str, pointer: str = "") -> None: ...
def load_record(raw: bytes, name: str, *, store: SchemaStore,
                max_bytes: int = 1048576) -> JSONObject: ...
```

LineageError.code is one of the fixed tool errors in CONTRACT. detail is sanitized and bounded to 2048 characters on the wire. The loader rejects duplicate keys recursively, non-finite numbers (including float overflow), invalid UTF-8, unpaired surrogates, extra trailing JSON and oversize input. canonical emits sorted compact UTF-8 without LF. All numeric comparisons reject bool as integer/number; const, enum and uniqueItems also distinguish bool from numbers. Integer values are restricted to the shared safe-integer range. Unknown fields report a JSON Pointer, including escaped `~` and `/` segments.

[K0 decision] The required mini-validator subset is boolean schemas; $ref, $defs; type; properties/patternProperties/required/additionalProperties; items/minItems/maxItems/uniqueItems; minLength/maxLength/pattern; minimum/maximum/exclusiveMinimum/exclusiveMaximum; const/enum; allOf/anyOf/oneOf/not; if/then/else. $schema/$id/title/description/default are annotations; default insertion is dispatch policy, not schema validation. Unsupported assertion keywords are a configuration bad_args failure, never silently ignored. Only bundled relative references and local JSON Pointer fragments resolve; no network/file URI resolution or directory escape. A schema title is not an identity check on a record.

The eight schema filenames are event.schema.json, agent.schema.json, run.schema.json, mem_unit.schema.json, family_envelope.schema.json, family_receipt.schema.json, bench_declared.schema.json and tool_error.schema.json. Record loading handles syntax/shape only; domain validators prove hashes, authority, gates and cross-field relations. Pattern-bounded dynamic maps appear only in descriptor schema documents and JSON values within them.

## Journal and lock boundary

```python
# lineage/core/locking.py
LOCK_TIMEOUT_S: float = 1.0              # [CITED: seed locking]
def lock_exclusive(fd: int, timeout_s: float = LOCK_TIMEOUT_S) -> None: ...
def unlock(fd: int) -> None: ...

# lineage/core/journal.py

def resolve_home(home: str | Path | None = None) -> Path: ...
def snapshot(*, ctx: Context) -> Snapshot: ...
def transact(command: Command, prepare: Prepare, render: Render, *,
             ctx: Context) -> Committed: ...
def append(draft: EventDraft, *, command: Command, render: Render,
           ctx: Context) -> Committed: ...
def read(after: int = 0, *, limit: int = 100, wait_ms: int = 0,
         agent_id: str | None = None, kinds: Sequence[str] = (),
         ctx: Context) -> Cursor: ...
def verify(*, projections: bool = True, ctx: Context) -> Verification: ...
def fold(events: Sequence[Event], *, registry: "Registry") -> State: ...
```

transact owns this exact sequence: acquire ledger lock; read and verify the durable complete prefix; look up (actor,op_id); compare request digest and replay the original event prefix/result if found; check expected_head; fold the current prefix; call prepare with that snapshot; generate the event id/ts/Lamport and chain fields; validate its schema; invoke the registered kind validator and evidence checks; compute the candidate fold and render its bounded result; append exactly one canonical line and fsync; release lock; rebuild affected projections. No domain callback may acquire the same lock, dispatch another mutation, run a command or write an artifact during the locked callback. Lock timeout raises busy. Interrupted writes roll back to the original durable offset, including directory durability where a file is first created. No fallthrough exists after failed rollback.

append is a convenience wrapper around transact with prepare returning the supplied draft; it never bypasses validation, dedupe or locking. Evidence required from disk is opened safely under the permitted root and checked inside the transaction; any publish-before-commit immutable skill/reference content must already exist and match its digest, with no authoritative state change until the event commits. Callback result rendering must succeed before append so a renderer failure cannot leave an unacknowledgeable event. On replay, Render receives the snapshot ending at the original event; it cannot read later mutable state.

[K0 decision] One transact call appends one event. Compound bench execution uses deterministic child operations and can stop/recover between them. It never pretends a multi-line append is a crash-atomic transaction. Internal reference/skill bootstrap may use append for the corresponding event kinds before dependent creation; no transport read performs bootstrap. Bundled artifact pins may be verified directly for genesis even when no reference.pinned event has yet been materialized.

sha256 is over canonical event-without-sha256, with no LF; prev_sha256 is the SHA of the preceding raw line including LF (64 zeroes only at genesis). Lamport is prior maximum+1 and must be contiguous. A final non-LF suffix is a reported torn tail, ignored for reads and truncated under the next writer lock. Any complete malformed line or chain failure blocks mutation. verify returns `{valid,head,sha256,torn_tail_bytes,issues}` with relative path/line diagnostics; an absent, established empty prefix has head=0 and sha256=null. An I/O refusal is never reported as empty. The ledger_verify adapter turns valid=false into hash_mismatch while retaining a bounded diagnostic summary. No process signals or group manipulation are part of this API.

## Extension registry and dispatch

```python
# Every lineage/ext/<group>.py
TOOLS: tuple[ToolSpec, ...]
VALIDATORS: Mapping[str, Validator]        # one owner per event kind
FOLDS: Mapping[str, FoldSpec]              # one owner per namespaced fold key

# lineage/core/registry.py
class Registry:
    tools: Mapping[str, ToolSpec]
    validators: Mapping[str, Validator]
    folds: Mapping[str, FoldSpec]
    def descriptors(self) -> list[JSONObject]: ...
    def names(self) -> frozenset[str]: ...

def load(package: str = "lineage.ext") -> Registry: ...

# lineage/core/app.py

def list_tools(*, ctx: Context) -> list[JSONObject]: ...
def tool_names(*, ctx: Context) -> frozenset[str]: ...
def dispatch(name: str, args: JSONObject, *, ctx: Context) -> JSONObject: ...
```

[K0 decision] load discovers and imports extension modules in lexical module order. It builds a new immutable registry, failing atomically on duplicate tool name, kind validator, fold namespace, invalid descriptor or missing member. There is no shared hand-edited module list. Tool descriptors are `{name,description,inputSchema}`; handlers and effect stay internal. Tools sort by name across discovery surfaces. Modules may share pure helpers, but never import app or MCP while loading.

Fold order is ascending `(FoldSpec.order, namespace)`: references=10, skills=20, memory=30, agents=40, runs=50, arena=60, scorecards=70, tree=80, promotion=90. Every apply receives the full State and an immutable Event, changes only its owned namespace, and filters using kinds. Memory fold precedes agent version refresh. Promotion fold exposes effective retirement; agent getters combine immutable agent facts with promotion status. Inherited memory from agent.born is folded before the new agent materializes. Fold order cannot depend on filesystem iteration order.

Dispatch validates raw object/unknown tool, inserts explicit defaults from CONTRACT, validates the merged input schema and actor, creates an effective Context with actor=args.agent and authority=tool, then calls handler(args,effective_ctx). The operator ruling CLI calls the domain API directly with its separately constructed operator context; dispatch never preserves operator authority. Domain functions return inner data or Committed.value; the extension never adds untrusted. app returns exactly `{untrusted:data}` once, or error_payload(exc). Transport adapters do not wrap again. bad_args is discoverable as usage failure before dispatch; domain failures retain their fixed code. Unexpected exceptions become internal without traceback text. Runtime validates effect/transport authorization before handler execution. HTTP exports are authorization-sensitive writes despite registry effect=read on the authoritative state.

## References, constitution, skills and agents

```python
# lineage/domain/references.py

def get(ref_id: str, *, ctx: Context) -> JSONObject: ...
def verify(ref_id: str, *, ctx: Context) -> JSONObject: ...
def require_pins(pins: Sequence[JSONObject], *, ctx: Context) -> tuple[JSONObject, ...]: ...

# lineage/domain/constitution.py (pure after artifact reads)

def compile_constitution(*, workflow: str, language: str,
                         references: Sequence[JSONObject],
                         skills: Sequence[JSONObject], overlays: Sequence[str],
                         rule_registry: Mapping[str, JSONObject],
                         role_matrix: JSONObject, overlay_registry: JSONObject) -> bytes: ...

def validate_authority(text: bytes, *, workflow: str,
                       rule_registry: Mapping[str, JSONObject]) -> None: ...

# lineage/domain/skills.py

def package(files: Sequence[JSONObject]) -> tuple[bytes, str]: ...
def list_skills(*, include_retired: bool = False, ctx: Context) -> Data: ...
def get(skill_id: str, *, sha256: str | None = None, ctx: Context) -> Data: ...
def publish(skill_id: str, files: Sequence[JSONObject], *, command: Command,
            ctx: Context) -> Committed: ...
def retire(skill_id: str, sha256: str, reason: str, *, command: Command,
           ctx: Context) -> Committed: ...

# lineage/domain/version.py

def agent_version(constitution_sha256: str, skills: Sequence[JSONObject],
                  memory_gen: int) -> str: ...

# lineage/domain/agents.py

def create(agent_id: str, display_name: str, workflow: str, language: str,
           allowed_seats: Sequence[Seat], references: Sequence[JSONObject],
           skills: Sequence[JSONObject], *, overlays: Sequence[str] = (),
           command: Command, ctx: Context) -> Committed: ...
def get(agent_id: str, *, ctx: Context) -> Data: ...
def list_agents(*, workflow: str | None = None, language: str | None = None,
                status: str | None = None, include_retired: bool = False,
                after: str | None = None, limit: int = 100, ctx: Context) -> Data: ...
def materialize(agent_id: str, *, snapshot: Snapshot, ctx: Context) -> tuple[Path, ...]: ...

# lineage/domain/brief.py

def build(agent: Agent, units: Sequence[MemoryUnit], *,
          memory_arm: str = "own") -> bytes: ...
def get(agent_id: str, *, memory_arm: str = "own", ctx: Context) -> Data: ...
```

Reference files, data overlays and package bytes are immutable content inputs. Creation verifies both reference hashes, pinned skills, workflow authority and allowed seats before preparing agent.born. The event stores constitution text, overlay ids and cited rule ids; skill.published stores the canonical package files. Validators compare hashes to those immutable bytes, so deleting projections does not lose source content. Materialization writes canonical agent.json, LF constitution/brief text and derived files only after event commit. Parent/skill order normalizes before hashing. No absolute source coordinates, hostnames, private dispatch tools or private evidence locations enter published artifacts. Public references retain source rule ids/citations and hashes; missing gate texts remain AUSENTE until verified from their pinned artifact.

## Memory interfaces

```python
# lineage/domain/memory/schema.py

def validate_unit(unit: MemoryUnit, *, authority: Authority,
                  actor: str, ctx: Context) -> None: ...

# lineage/domain/memory/units.py

def put(agent_id: str, unit: MemoryUnit, *, run_id: str | None = None,
        command: Command, ctx: Context) -> Committed: ...
def get(agent_id: str, unit_id: str, *, ctx: Context) -> Data: ...
def history(agent_id: str, *, unit_id: str | None = None, after: int = 0,
            limit: int = 100, ctx: Context) -> Data: ...
def operator_ruling(agent_id: str, quote: bytes, *, command: Command,
                    ctx: Context) -> Committed: ...

# lineage/domain/memory/fold.py

def empty() -> JSONObject: ...
def apply(state: State, event: Event) -> None: ...
def units_for(state: State, agent_id: str, *, include_inactive: bool = False,
              include_private: bool = False) -> tuple[MemoryUnit, ...]: ...

# lineage/domain/memory/store.py

def generation_files(agent: Agent, units: Sequence[MemoryUnit],
                     events: Sequence[Event], *, token_count: TokenCounter | None) -> Mapping[str, bytes]: ...
def rebuild(agent_id: str, *, snapshot: Snapshot, ctx: Context) -> tuple[Path, ...]: ...
def verify_projection(agent_id: str, *, snapshot: Snapshot,
                      ctx: Context) -> tuple[JSONObject, ...]: ...

# lineage/domain/memory/entry.py

def build(agent: Agent, units: Sequence[MemoryUnit], *,
          token_count: TokenCounter | None, max_bytes: int = 6000,
          max_tokens: int = 4000) -> bytes: ...

# lineage/domain/memory/route.py

def route(agent_id: str, query: str, *, limit: int = 10, ctx: Context) -> Data: ...

# lineage/domain/memory/bootcheck.py

def expected(agent_id: str, *, snapshot: Snapshot, ctx: Context) -> JSONObject: ...
def check(agent_id: str, observed: JSONObject, *, ctx: Context) -> Data: ...
```

Unit type/body, level, receipts and the 6000-byte unit limit are checked before journal admission. An episode body run_id, provenance.run_id and tool run_id must agree; its seat/task/outcome/cost/parents_context must agree with the opened run and the requested closing outcome where applicable. Cross-agent memory cannot satisfy another agent's run. Supercession is resolved in the fold using the new unit's supersedes list, with hash-backed history and no cyclic/asymmetric state. Private units do not enter briefs, route output or inheritance. Observations and episodes never acquire hereditary status merely because they were written successfully.

Generation files are a relative filename→bytes mapping; no wall clock, inode, absolute path or receipt location affects content. A projection generation counter tracks each memory projection write independently of agent.memory_gen, which tracks brief-affecting changes only [K0 decision]. Journal events include the prefix necessary to identify that projection generation even when an episode does not bump agent_version. Every old generation is immutable; a fresh generation is fully written/fsynced before atomic CURRENT publication and directory fsync. No mutation edits an existing generation. Rebuilding a deleted projection reproduces its same filenames and bytes. Static memory entry is validated by byte and verified token ceilings before append; unavailable token_count fails memory_debt. Bootcheck compares all observed fields from CONTRACT and actual evidence hashes; no missing check returns SKIP.

## Runs and close gate

```python
# lineage/domain/runs.py

def open_run(run_id: str, agent_id: str, seat: Seat, task: JSONObject, *,
             parents_context: Sequence[JSONObject], memory_arm: str,
             command: Command, ctx: Context) -> Committed: ...
def beat(run_id: str, progress: str, *, command: Command,
         ctx: Context) -> Committed: ...
def close(run_id: str, outcome: Outcome, cost: Cost, *,
          evidence: Sequence[Evidence] = (), command: Command,
          ctx: Context) -> Committed: ...
def get(run_id: str, *, ctx: Context) -> Data: ...

# lineage/domain/gate_close.py

def check(snapshot: Snapshot, run_id: str, outcome: Outcome, cost: Cost, *,
          actor: str, ctx: Context) -> JSONObject: ...
```

The gate helper is called only inside run_close's registered validator/prepare path with the current locked snapshot. It returns `{passed:true,checks:[...],memory_receipts:[...]}` internally or raises memory_required/memory_debt/no_run/run_closed/conflict. The adapter constructs the event payload's gate and memory_receipts from that report; clients cannot pass it. The episode is after open, same owner and run, active, nonprivate, schema-valid and receipt-valid. Relevant post-open lessons and negatives are required for failure/repair outcomes as specified in CONTRACT. A run that closes successfully includes the memory unit ids, levels and gate_passed=true in lineage.run/v1. Episode cost nulls are preserved. Retire/close races serialize on the same ledger lock and cannot pass stale eligibility. No resume hook can bypass this function.

## Arena statistics, banks and execution

```python
# lineage/domain/arena/sprt.py

def thresholds(*, alpha: float, beta: float) -> tuple[float, float]: ...
def update(llr: float, outcome: str, *, p0: float, p1: float) -> float: ...
def decide(llr: float, n_tasks: int, *, p0: float, p1: float,
           alpha: float, beta: float, cap: int) -> str: ...

# lineage/domain/arena/score.py

def correctness(verdict: str) -> int: ...
def compare(candidate: JSONObject, baseline: JSONObject, *,
            cost_tiebreaker: bool) -> Literal["win", "loss", "tie"]: ...

# lineage/domain/arena/credit.py

def credit(candidate: Sequence[JSONObject], baseline: Sequence[JSONObject], *,
           rule: JSONObject) -> JSONObject: ...

# lineage/domain/arena/rating.py

def fold(events: Sequence[Event]) -> JSONObject: ...

# lineage/domain/arena/bank.py

def load(bank_id: str, *, ctx: Context) -> JSONObject: ...
def verify(bank: JSONObject, expected_sha256: str) -> None: ...
def tasks(bank: JSONObject, *, purpose: str) -> tuple[JSONObject, ...]: ...

# lineage/domain/arena/runner.py

def run_task(task: JSONObject, *, agent: Agent, seat: Seat, memory_arm: str,
             runner: JSONObject, ctx: Context) -> JSONObject: ...

# lineage/domain/arena/bench.py

def list_benches(*, after: str | None = None, limit: int = 100,
                 ctx: Context) -> Data: ...
def declare(declaration: BenchDeclared, *, command: Command,
            ctx: Context) -> Committed: ...
def run(bench_id: str, runner: JSONObject, *, command: Command,
        ctx: Context) -> Data: ...
def status(bench_id: str, *, ctx: Context) -> Data: ...
def verdict(bench_id: str, *, command: Command, ctx: Context) -> Committed: ...
def record_result(result: BenchResult, *, command: Command,
                  ctx: Context) -> Committed: ...
```

thresholds returns `(lower,upper)`; update accepts win/loss/tie. decide returns continue/superior/not_superior/inconclusive; the current llr already incorporates update. Distinct task count (including ties) drives cap; discordant task count drives statistical evidence. Repeated seeds/crossed cells of the same task are aggregated before one independent contribution. compare prioritizes correctness and uses known lower cost only when declared. Credit is the exact closed shape in CONTRACT; no cost-only win can satisfy a correctness credit requirement.

[K0 decision] A bank is canonical `{schema:"lineage.bank/v1",bank_id,tasks:[{id,split,kind,language,prompt,expected}]}`. id is Id, split is select/heldout, kind/language are the Task strings, prompt is bounded nonempty UTF-8 text, expected is `{baseline:Outcome,candidate:Outcome}` for the offline scripted bank. Files are `arena/banks/<bank_id>/bank.json` plus a SHA-256 manifest; bank_sha256 hashes canonical bank data, not its manifest. Additional bank fields are rejected. The demo is synthetic and supplies no evidence of real agent fitness. A declared benchmark snapshots versions from the ledger prefix at bench.declared, not mutable agent files.

[K0 decision] Runner output is exactly `{outcome:Outcome,cost:Cost,evidence:Evidence[],memory_units:MemoryUnit[]}`. Command stdin is one strict `{task,agent,seat,memory_arm}` JSON object; stdout is one strict runner object capped at 1048576 bytes; stderr is bounded evidence, never protocol text. Command argv is executed without a shell; timeout kills only the exact verified child PID owned by the runner and records error. No process-group API or broad kill operation is used. The fake runner supplies valid synthetic episode/failure memory with verifiable fixture receipts and the virtual clock; it never contacts a model or network.

bench.run opens each real run, executes outside all journal locks, validates runner memory and writes it through memory.put, closes via the same gate, then appends bench.result. Its deterministic child operation ids derive from the root op_id and task/agent/seat/arm/stage identity using a bounded digest. Each child Command retains the original validated bench_run tool/args for its request digest; stage identity is in the child op_id and EventDraft, not an extra caller field. Changing the root runner or other args then fails bad_op at the first retained stage. Internal run contexts use the subject agent as actor while the root benchmark actor remains in the result stages; no operator authority is granted. It verifies prior stages on recovery, so a crash after close but before result recovers rather than reruns. The final result's commit covers the operation's committed bench.result events; no synthetic terminal event kind is introduced. Replaying the same root operation uses its frozen result prefix. A distinct attempt cannot change the declared rule or use held-out selection data. Incomplete task/cell pairs cannot generate superior. Declaration and result validators freeze bank/version/seat/split admission under the lock.

## Inheritance, breeding and promotion

```python
# lineage/domain/breeding/inherit.py
@dataclass(frozen=True)
class InheritanceSelection:
    inherited: tuple[JSONObject, ...]
    rejected: tuple[JSONObject, ...]

def select(parents: Sequence[Agent], units: Mapping[str, Sequence[MemoryUnit]], *,
           workflow: str, language: str, selected_ids: Sequence[str] | None = None,
           ctx: Context) -> InheritanceSelection: ...

# lineage/domain/breeding/clone.py

def clone(parent_id: str, child_id: str, *, display_name: str | None = None,
          command: Command, ctx: Context) -> Committed: ...

# lineage/domain/breeding/distill.py

def distill(parent_id: str, child_id: str, *, display_name: str | None = None,
            unit_ids: Sequence[str] | None = None, command: Command,
            ctx: Context) -> Committed: ...

def retire(agent_id: str, reason: str, *, command: Command,
           ctx: Context) -> Committed: ...

# lineage/domain/breeding/cross.py

def cross(parent_ids: Sequence[str], child_id: str, *,
          display_name: str | None = None, command: Command,
          ctx: Context) -> Committed: ...

# lineage/domain/breeding/mutate.py

def mutate(parent_id: str, child_id: str, change: JSONObject, *,
           display_name: str | None = None, command: Command,
           ctx: Context) -> Committed: ...

# lineage/domain/breeding/specialize.py

def specialize(parent_id: str, child_id: str, language: str, *,
               display_name: str | None = None, command: Command,
               ctx: Context) -> Committed: ...

# lineage/domain/tree.py

def tree(*, root_id: str | None = None, include_retired: bool = True,
         ctx: Context) -> Data: ...

# lineage/domain/promotion.py

def evaluate(snapshot: Snapshot, agent_id: str, bench_id: str) -> JSONObject: ...
def promote(agent_id: str, bench_id: str, *, command: Command,
            ctx: Context) -> Committed: ...
```

select is the only inheritance policy implementation; all five operators call it with the locked source snapshot. It verifies source hashes/receipts and attaches inherited_from before child event creation. Source unit hash is over the canonical source unit before adding child provenance. Accepted/rejected output sorts by source agent then unit id; child ids are stable digests of child/source/unit identity [K0 decision], with Id-compatible encoding. Episodes, level 1, level 3, private/inactive/receiptless units and unpromoted workflows are excluded with explicit reasons. Duplicate claims resolve only when identical; contradictions name both units. No raw episodes or foreign project rulings are carried. Parent status/version are revalidated at commit, not assumed from a pre-read. Adoption of a unit never confers operator authority.

Clone preserves constitution/skills/memory_gen version inputs; other births set memory_gen to the accepted brief-affecting count and keep both reference pins. Draft→shadow and shadow→promoted gates are checked in promotion.evaluate inside a journal transaction. It returns `{from,to,reason,bench_id}` only when admitted, otherwise raises the fixed domain error. No arbitrary set_status API exists. Tree order is deterministic by generation then agent_id, with exact parent links and birth operator; each edge is available without SVG.

## Ledger, export and scorecard

```python
# lineage/core/events.py

def events(*, after: int = 0, limit: int = 100, wait_ms: int = 0,
           agent_id: str | None = None, kinds: Sequence[str] = (),
           ctx: Context) -> Data: ...

# lineage/core/export.py

def export(out: str, *, ctx: Context) -> Data: ...

# lineage/domain/scorecard.py

def fold(events: Sequence[Event]) -> JSONObject: ...
def get(agent_id: str, *, ctx: Context) -> Data: ...
```

Cursor shape and advancement are identical across events.read, ledger_events and HTTP events. Projection exports are beneath home exports and contain full canonical ledger, deterministic derived files and SHA manifest. No symlink or traversal target is admitted. scorecard folds immutable run.close records and groups by agent/seat/memory_arm; absent costs are counted as unknown and excluded from arithmetic. Export never mutates journal history.

## Transport adapters

```python
# lineage/core/envelope.py
class InvalidEnvelope(ValueError): ...

def decode(raw: bytes) -> JSONObject: ...             # cap 65536 bytes

def canonical(value: JSONValue) -> bytes: ...
def operation_id(value: JSONObject) -> str: ...
def digest(value: JSONObject) -> str: ...
def configuration(raw: bytes, endpoint: str) -> JSONObject: ...
def validate(raw: bytes, endpoint: str, filename_id: str | None = None) -> JSONObject: ...

# lineage/core/jsonlane.py

def dispatch(envelope: JSONObject, config: JSONObject, *, ctx: Context) -> JSONObject: ...
def main(argv: Sequence[str] | None = None) -> int: ...

# lineage/core/family.py
class Refusal(Exception): ...
class UnsafeEntry(Exception): ...
class RecoveryError(Exception): ...

class Mailbox:
    def __init__(self, endpoint: str, *, ctx: Context) -> None: ...
    def open(self) -> None: ...
    def check_tree(self) -> None: ...
    def release(self) -> None: ...
    def quarantine(self, name: str) -> None: ...
    def publish(self, identity: str, result: JSONObject,
                envelope: JSONObject | None = None) -> None: ...
    def retained(self, envelope: JSONObject) -> JSONObject | None: ...
    def dispatch(self, envelope: JSONObject) -> JSONObject: ...
    def consume(self, name: str) -> None: ...
    def sweep(self) -> int: ...

def main(argv: Sequence[str] | None = None) -> int: ...

# lineage/core/mcp.py

def main() -> int: ...

# lineage/core/cli.py; lineage/__main__.py re-exports main

def main(argv: Sequence[str] | None = None) -> int: ...
```

Mailbox mechanics preserve the seed's descriptor-safe, recipient-owned consumer lock, pending/complete retention and atomic durable publications. sweep returns number of consumed requests; it never decides completion from file presence without validating retained identity/digest and endpoint authorization. Its open acquires the single consumer lock; startup refusal is exit 2, no stale takeover. All paths are resolved under services.home. A symlinked request is quarantined rather than opened. No transport holds a mailbox journal snapshot lock while invoking a mutation. Operation identity and actor injection follow CONTRACT. One-shot json must read target configuration and obey the same source/tool admission before dispatch; no unrestricted bypass exists.

```python
# lineage/serve/session.py

def new_token() -> str: ...
def authorize(*, host: str, origin: str | None, token: str | None,
              expected_authority: str, expected_token: str,
              mutation: bool) -> None: ...

# lineage/serve/static.py

def resolve_asset(url_path: str, *, root: Path) -> Path: ...

# lineage/serve/http.py

def serve(*, ctx: Context, port: int = 0,
          fixtures: Path | None = None) -> None: ...
```

HTTP is a stdlib http.server adapter, loopback only, with the explicit route/auth/status table from CONTRACT. It never accepts authority from request JSON. Token generation and host/origin checks are process-local; fixture mode refuses every write and never opens the real ledger for mutation. UI readiness and selectors are owned by OPERABILITY, not an additional backend API.

```python
# lineage/bridge/openfresnel.py

def commands_dir(*, commands_dir: str | None = None,
                 contract_file: str | None = None) -> Path: ...
def parse_receipt(value: JSONObject, *, rid: str, op: str) -> JSONObject: ...
def probe(*, commands_dir: str | None = None, contract_file: str | None = None,
          timeout_ms: int = 20000, command: Command, ctx: Context) -> Data: ...
def spawn(mode: str, *, endpoint: str | None = None,
          envelope: JSONObject | None = None, commands_dir: str | None = None,
          contract_file: str | None = None, timeout_ms: int = 20000,
          command: Command, ctx: Context) -> Data: ...
```

Bridge parsing keeps compiler status and Deck ok/api_version separate. It validates echoed request identity/op, publishes atomically, retains rid across retry and returns launched rather than a completed application operation. Paths are explicitly configured or taken from the documented environment variable, never discovered via private metadata names. The extension delegates to this client only; no external project source is edited. Live terminal parity remains AUSENTE.

## Extension-to-domain map

| Extension | Tools / event validators / fold namespace |
|---|---|
| references.py | reference_get, reference_verify; reference.pinned; references |
| skills.py | skill_list, skill_get, skill_publish, skill_retire; skill.published, skill.retired; skills |
| agents.py | agent_create, agent_get, agent_list, agent_brief; agent.born, agent.status; agents |
| memory.py | memory_put, memory_get, memory_history; memory.put, memory.retire; memory |
| memory_resume.py | memory_route, memory_bootcheck; no duplicate validator/fold |
| runs.py | run_open, run_beat, run_close, run_get; run.open, run.beat, run.close; runs |
| arena.py | bench_list, bench_declare, bench_run, bench_status, bench_verdict; bench.declared, bench.result, bench.verdict; arena |
| lineage_ops.py | agent_clone, agent_distill, agent_retire, lineage_tree; uses agent validators; tree |
| breeding2.py | agent_cross, agent_mutate, agent_specialize; uses agent validators; no duplicate fold |
| promotion.py | agent_promote; uses agent.status validator; promotion |
| ledger.py | scorecard_get, ledger_events, ledger_export, ledger_verify; no validator; scorecards |
| openfresnel.py | openfresnel_probe, openfresnel_spawn; no application journal validator/fold |

[K0 decision] agent.born/status validation owns all breeding/promotion admission checks through pure domain helpers, so a caller using append cannot bypass those gates by choosing a different extension. Likewise run.close is always validated by gate_close. Empty registries in extensions are explicit empty mappings/tuples, never omitted.

## Preserved planning interfaces

Copied planning code remains under `lineage/core/plan/` with imports renamed mechanically. It is a compatibility subsystem, never the authority for memory or agent admission. Preserve the seed's public calling conventions (annotations below are descriptive):

```python
# fold.py
class PlanProjection(dict):
    def get(self, key, default=None): ...
def empty_projection(): ...
def apply_op_event(state, event, *, templates=None, last_by_agent=None): ...
def fold_plan(events, *, templates=None): ...

# ops.py
def validate_op_shape(op: object): ...
def is_valid_op_shape(op: object): ...

# template.py
def canonical_template_json(tpl): ...
def template_hash(tpl): ...
def validate_template(raw): ...
def load_template(path): ...
def resolve_template(template_id, templates): ...

# conformance.py
def check_conformance(projection, template): ...

# markdown.py
def render_plan_md(projection, template=None): ...
def render_memory_md(projection, template=None): ...

# errors.py
class PlanError(Exception):
    def __init__(self, code: str, message: str = ""): ...
```

Copied limits stay internal to that subsystem. Core journal imports no plan fold, conformance checker, legacy room policy, observer or hook. New public dispatch has no legacy aliases. The seed conventions preserved are sorted compact JSONL, exclusive locking, replay digest comparison, shared tool dispatch, untrusted wrapping, cursor shape and recipient-owned safe mailboxes; the event chain and domain gates are new requirements rather than claimed seed behavior.

## Verification obligations

| Gate | Acceptance | Rejecting contrast |
|---|---|---|
| Schema syntax | Every named JSON file passes python3 -m json.tool | Invalid JSON is rejected |
| Schema references/closure | All local refs resolve and each shaped object closes unknown keys | A missing schema target or unknown property is rejected |
| Tool inventory | Exactly the 38 contract names, identical on all transports | Duplicate name or absent descriptor blocks registry load |
| Gate atomicity | Domain validation and append share the journal lock | Removing run-close/ownership check makes frozen negative oracle fail |
| Replay | Same actor/op_id/content reconstructs original result prefix | Changed tool/content gives bad_op without append |
| Publishability | Relative public coordinates only; no local paths/private identifiers | Forbidden source path or secret-shaped fixture fails checker |
| Evidence honesty | Reports distinguish schema checks from runtime receipts | Syntax-green is never reported as implemented agent behavior |

These are requirements for later implementations; K0 itself writes no runtime implementation, launches no worker or external app, and changes no oracle. All mandates in this interface contract are scoped to the supplied campaign corpus and the K0 seed.

## Amendment A-K0 (orchestrator; binding)
See docs/CONTRACT.md "Amendment A-K0" items 1–8. Interface deltas: `Services.token_count` is always `None` in v1; `constitution.compile_constitution(..., rule_overrides: dict[str, str] | None = None)`; `promotion.evaluate(agent_id, bench_id, *, seat)` and `promotion.promote(agent_id, bench_id, *, seat, ...)`; `brief.build` byte layout as in item 2.
