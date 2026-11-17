# Native harness capture

Identity is caller-asserted within Lineage's same-user filesystem boundary.
A harness type is a routing key, not an authenticated identity or a model.
Create the mapped Lineage agents and admit their complete seats before capture.
No command here invokes a model, reads transcripts, or invents task memory.

## Supervise a command

From the repository root, with `LINEAGE_HOME` selecting an existing private home:

```sh
python3 -m lineage run --agent build-agent --seat-model test-model --seat-effort medium --task-kind develop --task-language python --beat-s 30 -- python3 build.py
```

`--task-id`, `--task-kind`, `--task-language` and `--beat-s` are optional.
Task id defaults to the generated run id, kind to `command`, language to the
agent's language, and heartbeat interval to 30 seconds. The interval must be
finite and positive. Seat mode is `headless`; the complete seat must be allowed.
Everything after the required `--` is literal argv, including empty arguments,
spaces and shell punctuation. No shell expands or executes those characters.

The first flushed stdout line contains `run_id` and its opening `op_id`, before
`run_open` or process launch. Child output retains its normal streams; the final
stdout line is the JSON capture report. Opening, heartbeat and closing calls use
the shared dispatcher and unchanged operation ids `<run_id>/open`,
`<run_id>/beat/<sequence>` and `<run_id>/close`. The child receives
`LINEAGE_HOME`, `LINEAGE_AGENT_ID` and `LINEAGE_RUN_ID` in its environment.
Never use these environment variables as proof of external authentication.

Exit zero records `green`; a nonzero child exit records `red`; a child signal,
launch failure, or SIGTERM/SIGINT received by the supervisor records `error`.
`duration_ms` is measured with a monotonic clock. Token and monetary costs remain
null. The supervisor exits zero only after a successful child and accepted close;
argument errors exit 2 and task/capture/closing failures exit 3.
SIGTERM/SIGINT are forwarded only to the exact live child owned by the supervisor,
with PID greater than 1. No process group is signalled. Descendants are not
implicitly managed; a child that ignores the forwarded signal may keep running.
Handlers are restored when supervision finishes.

## Repair a refused close

The supervisor never synthesizes an episode, lesson or negative. A task can
finish while its Lineage run remains open. Parse the final JSON report, inspect
its exact `code` (`memory_required`, `memory_debt`, or another domain error), and
retain its `run_id` and `close_args`. A refusal is not successful completion.

1. Query `run_get` for that id and confirm `closed` is null.
2. The refusal report carries `episode_args`: a ready `memory_put` argument
   object already bound to the run (top-level `run_id`, the opened task and
   seat, the exact outcome and cost of `close_args`). Fill only `unit.id` and
   `unit.statement` and call `memory_put` with it. The top-level `run_id`
   argument is what binds the write to the run; an episode without it is not
   seen by the close gate. Otherwise, use `memory_put` as that run's agent, with fresh caller-owned operation ids,
   to write an active, nonprivate, same-run episode after `run_open`. Copy the
   opened task id, seat and parents context, and the report's exact outcome and
   cost into its episode body. In particular, copy measured `duration_ms` from
   `close_args`; unknown cost fields stay null. The integrated gate compares
   the episode outcome and cost exactly, so a pre-exit episode with unknown
   duration may need replacement using the documented supersession mechanism.
3. For `error` or `red`, also write a same-run lesson; for `red`, write a negative.
   Keep memory within the installed byte budget. No tokenizer is injected.
4. Retry `call run_close --json OBJECT`, using the complete unchanged
   `close_args` object from the report, including its agent and operation id.
   After acceptance, an exact retry replays the original committed prefix.
5. Inspect `run_get`, `ledger_events` or `snapshot` to verify completion.

A failed close appends no closing event and reserves no successful operation.
Never change a successful operation's content under the same id.

## Claude Code mapping

`lineage hook [--map FILE] [--verbose]` consumes exactly one strict hook JSON
object from stdin. It requires string `session_id`, `transcript_path`, `cwd` and
`hook_event_name`; additional harness fields are passive data. Subagent start and
stop additionally require `agent_id` and `agent_type`. Transcript paths and cwd
are never opened or persisted. `last_assistant_message` is never stored: only
its UTF-8 SHA-256 can appear in a `run_beat` progress record.

Save this example as `.claude/lineage-map.json` and replace ids/seats with agents
already created in your home:

```json
{
  "session": {
    "agent_id": "build-agent",
    "seat": {"model": "test-model", "effort": "medium", "mode": "headless"}
  },
  "sessions": {
    "a-specific-session-id": {
      "agent_id": "build-agent",
      "seat": {"model": "test-model", "effort": "medium", "mode": "headless"}
    }
  },
  "agent_types": {
    "reviewer": {
      "agent_id": "review-agent",
      "seat": {"model": "test-model", "effort": "medium", "mode": "headless"}
    }
  }
}
```

All map keys are optional; binding objects are closed and require both fields.
For main-session events, an exact `sessions[session_id]` binding overrides
`session`. Subagents use only `agent_types[agent_type]`; they never inherit the
main-session binding. Select a map with `--map`, then `LINEAGE_HOOK_MAP`; with
neither, all identities are unmapped. Missing or invalid explicit files exit 2.

`SessionStart` and `SubagentStart` open runs. `Stop`, `SubagentStop` and
`SessionEnd` close green; `StopFailure` closes error. Operation identities derive
from session id and harness subagent id (or the main-session discriminator), not
free text, paths, timestamps or message contents. Duplicates replay. All main
stops/end events share one session run; this captures session lifetime rather
than assigning separate runs to each conversational turn. Resume/compact starts
with the same session id replay that opening. Use `lineage run` for separate
assignments within a persistent session. Changed message hashes under the same
stop identity produce `bad_op`, not an additional execution.

Success and unmapped/unsupported events exit zero with empty stdout. Ignored
events produce one fixed stderr line only with `--verbose`. Malformed input
exits 2. Domain refusals exit 3 with the exact error code and run id on stderr.
The closing memory gate still applies; a hook does not certify a task as done.
Asynchronous delivery can arrive out of order: a stop before its opening returns
`no_run`; replay the original stop after the opening and required memory exist.

## Claude Code settings and headless mode

Merge this hooks block into `.claude/settings.json`. Run Claude Code from the
repository root with Lineage importable and `LINEAGE_HOME` set to the same
private home for every hook. Each command receives the native hook object on
stdin; it emits no control JSON or assistant instructions.

```json
{
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "command": "python3 -m lineage hook --map .claude/lineage-map.json", "async": true}]}],
    "SessionEnd": [{"hooks": [{"type": "command", "command": "python3 -m lineage hook --map .claude/lineage-map.json", "async": true}]}],
    "SubagentStart": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 -m lineage hook --map .claude/lineage-map.json", "async": true}]}],
    "SubagentStop": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 -m lineage hook --map .claude/lineage-map.json", "async": true}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "python3 -m lineage hook --map .claude/lineage-map.json", "async": true}]}],
    "StopFailure": [{"hooks": [{"type": "command", "command": "python3 -m lineage hook --map .claude/lineage-map.json", "async": true}]}]
  }
}
```

The equivalent headless invocation uses the same native hooks settings:

```sh
claude -p 'Perform the assignment' --output-format stream-json --verbose --settings .claude/settings.json
```

The stream output and hook stdin are different protocols. Do not pipe raw
stream-json messages into `lineage hook`. Stream subagent messages carry
`parent_tool_use_id`; that value alone does not establish the native hook's
session/subagent identity. The configured native hooks perform capture even
when the primary conversation uses stream-json. A supervisor wrapper can capture
the outer process too, but does not replace native subagent events.

SIGKILL/crash delivery is not asserted. Hooks are observational; stderr must be
collected by the harness and open runs reconciled before claiming completion.

## Compact orchestration state

`python3 -m lineage snapshot [--json]` and MCP resource `lineage://snapshot`
return the same `{untrusted: {head, sha256, agents, truncated}}` projection.
MCP `resources/list` is paged: follow `nextCursor` by passing it as `cursor`
until it is absent. This preserves the existing first resource page while
making `lineage://snapshot` discoverable on the following page.
Both CLI forms emit compact canonical JSON. One verified snapshot is folded
once through the installed registry; agent files and subsequent tool calls are
not consulted. The SHA is the complete persisted head-line hash (including LF),
not the head event's `sha256` field. An established empty runtime has head zero
and null SHA. An unavailable home, corruption or fold failure returns an
explicit error, never an empty healthy state.

Agents sort by id, include retired agents, and are capped at 200 with
`truncated:true` when more exist. Each row contains `agent_id`, `workflow`,
`language`, `status`, `generation`, the first 12 characters of `agent_version`,
`memory_gen`, `open_runs`, `last_run_verdict` (null before any close),
`runs_closed`, and `promoted_seat` when present. Full ids and full seat fields
are preserved; only the documented version display is abbreviated. The
truncation indicator is not a pagination cursor. Use ordinary tools for details.

The synthetic 50-agent acceptance test records UTF-8 wire bytes and enforces
10,000 bytes [TARGET], the portable approximation to the 2,500-token target.
The fixture response measured 9,637 bytes [MEASURED].
It does not inject or estimate an exact runtime token count. Long agent ids,
languages or seats can increase other snapshots' sizes; only agent count is
hard-capped. Process acceptance tests run under
`unshare --user --pid --fork --kill-child --mount-proc` and signal only verified
owned children.

Integration follows the installed API: CLI dispatch accepts `context` and
`registry` and returns `DispatchResult`; the shared snapshot facade exposes
`sha256`, whereas `docs/INTERFACES.md` names that field `raw_head_sha256`.
No alternate folds or per-agent filesystem layouts are introduced.

These capture guarantees are scoped to the supplied campaign corpus and the
integrated Lineage implementation.
