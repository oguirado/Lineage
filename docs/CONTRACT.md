# Lineage K0 public contract

Frozen implementation target. This document defines required behavior; runtime verification receipts are AUSENTE. Requirements originate in the supplied North Star (NS1–NS6, P1–P8) and strategy §2. The companion is `docs/INTERFACES.md`; wire records are in `schemas/`. All numerical limits below are [TARGET] unless explicitly [CITED]. `[K0 decision]` marks a resolution of an unspecified detail. No new dependency is required.

## Common types and validation

All arguments and shaped results are closed objects. Missing required fields, extra fields at any depth, duplicate keys, non-finite values, escaped unpaired surrogates and invalid UTF-8 fail. JSON Schema lengths count Unicode characters; the additional byte limits below are runtime checks. A Boolean never satisfies an integer. Optional fields are omitted unless a default is stated; explicit null is accepted only where declared. Canonical JSON is sorted-key, compact, UTF-8, `ensure_ascii=False`, `allow_nan=False`, followed by LF only when stored as JSONL.

| Alias | Exact shape / bounds |
|---|---|
| AgentId | `[a-z][a-z0-9-]{2,63}`; `operator` and `system` are reserved actors, never creatable agent ids |
| Id | `[A-Za-z0-9_-]{8,64}` for runs, units, benches, requests and correlations |
| Endpoint | `[A-Za-z0-9][A-Za-z0-9_-]{0,63}` |
| Hash | Lowercase SHA-256, exactly 64 hexadecimal characters |
| OpId | `[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}`; required for every journal or external mutation |
| Seat | `{model:string[1..128], effort:string[1..32] matching [a-z0-9_-]+, mode:headless\|interactive}`; equality compares every field |
| Evidence | `{path:RelativePath, sha256:Hash}`; file must exist and match its hash when required by a gate |
| RelativePath | 1..512 characters; ASCII letters, digits, `_`, `.`, `/`, `-`; nonempty segments; no leading slash, backslash, `.` or `..` segments; resolve beneath the permitted root and refuse symlinks |
| SkillPin | `{skill_id:AgentId, sha256:Hash}` |
| ReferencePin | `{id:gold_s1\|memory_v21, sha256:Hash}`; exactly one of each in an agent |
| Task | `{id:Id, kind:string[1..64], language:string[1..64], bank_id?:AgentId, bench_id?:Id, split?:select\|heldout}`; benchmark fields are all present together |
| ParentContext | `{agent_id:AgentId, agent_version:Hash, run_id:Id}`; arrays have at most 64 unique members |
| Outcome | `{verdict:ADMIT\|HOLD\|red\|green\|error, repair_loops:int[0..1000000], findings:{confirmed:int[0..1000000],refuted:int[0..1000000]}}` |
| Cost | All required: `{tokens_in,tokens_out,tokens_cache,duration_ms,cost_micro_usd}`; each nonnegative integer or null; unknown remains null |
| Commit | `{event_ids:EventId[1..10000], head:int>=1, sha256:Hash}`; head and hash refer to this operation’s committed prefix, including on replay |
| Cursor | `{events:Event[0..1000],next_after:int>=0,head:int>=0,has_more:bool,resync:bool}` |
| BenchStatus | `{declaration:BenchDeclared,state:declared\|queued\|running\|stalled\|complete,results:BenchResult[],verdict:BenchVerdict\|null,head:int>=0}` |
| Inherited | `{unit:MemoryUnit,source_agent_id:AgentId,source_unit_id:Id,unit_sha256:Hash}` |
| Rejected | `{agent_id:AgentId,unit_id:Id,reason:episode\|level_one\|level_three\|private\|missing_receipt\|invalid_receipt\|not_promoted\|scope_mismatch\|not_selected\|inactive\|kind_not_inheritable}` |

[K0 decision] Safe integers are limited to 9007199254740991 for Python/TypeScript parity. Generic nonempty text bounds and collection ceilings are specified in the schemas. HTTP/MCP/CLI tool JSON is capped at 1048576 UTF-8 bytes, including delimiters; family requests retain the stricter 65536-byte cap [CITED: seed family envelope]. Memory units are capped at 6000 canonical UTF-8 bytes [CITED: reference memory entry budget]; static memory entries have the same byte ceiling. The reference’s 4000-token ceiling is preserved as a separate gate: a verified token counter must be injected; if unavailable, entry admission fails with `memory_debt`, never a byte/token estimate.

### Shared tool arguments, errors and surfaces

Every tool accepts optional `agent:AgentId` on reads (default `system`). Every journal or external mutation requires `agent:AgentId` and `op_id:OpId` in addition to the arguments listed below. Actor identity is caller-asserted within a same-user filesystem boundary. Only the dedicated operator CLI path may construct operator authority; an `agent:"operator"` tool argument grants no level-1 authority.

`stale_rev` is supported by optional `expected_head:int>=0` on journal mutations. The check runs under the journal lock after replay lookup. Transport discovery/argument errors are `bad_args`; every row additionally permits `internal`, and journal operations permit `busy`, `bad_op`, `stale_rev`. Results below are the inner data object: every successful dispatch returns exactly `{"untrusted":data}`. Failures are exactly `{"ok":false,"code":ErrorCode,"detail"?:string[1..2048]}`. Errors never leak exception traces, host paths or secrets.

All 38 tools are exposed through MCP `tools/call`, CLI `call`, JSON `call`, and HTTP `POST /api/call`, using the same registry and dispatch. Mailbox exposure is the intersection of this set and `config.tools`; capabilities report only that intersection. `[K0 decision]` probe/spawn are external mutations because they publish a command; both require an operation identity, although neither acknowledgement asserts a journal mutation. `ledger_export` writes only an export projection and does not require an op_id.

## Tool catalogue

`!` marks required tool-specific arguments. Field-level types and bounds in the following normative JSON schemas are also the exact discovery `inputSchema`. Shared arguments above are merged into them before publication. Each result schema describes inner `untrusted` data. Every row’s surfaces are MCP / CLI / JSON / HTTP.

| Tool | Effect / op_id | Additional error codes | Surfaces |
|---|---|---|---|
| `reference_get` | read / no | `hash_mismatch` | MCP / CLI / JSON / HTTP |
| `reference_verify` | read / no | `hash_mismatch` | MCP / CLI / JSON / HTTP |
| `skill_list` | read / no | — | MCP / CLI / JSON / HTTP |
| `skill_get` | read / no | `hash_mismatch` | MCP / CLI / JSON / HTTP |
| `skill_publish` | journal / required | `bad_op`, `hash_mismatch` | MCP / CLI / JSON / HTTP |
| `skill_retire` | journal / required | `bad_op`, `hash_mismatch` | MCP / CLI / JSON / HTTP |
| `agent_create` | journal / required | `conflict`, `hash_mismatch`, `seat_not_allowed`, `memory_debt` | MCP / CLI / JSON / HTTP |
| `agent_get` | read / no | `no_agent` | MCP / CLI / JSON / HTTP |
| `agent_list` | read / no | — | MCP / CLI / JSON / HTTP |
| `agent_brief` | read / no | `no_agent`, `hash_mismatch` | MCP / CLI / JSON / HTTP |
| `agent_clone` | journal / required | `no_agent`, `conflict`, `hash_mismatch`, `not_inheritable`, `memory_debt` | MCP / CLI / JSON / HTTP |
| `agent_distill` | journal / required | `no_agent`, `conflict`, `hash_mismatch`, `not_inheritable`, `memory_debt` | MCP / CLI / JSON / HTTP |
| `agent_cross` | journal / required | `no_agent`, `conflict`, `hash_mismatch`, `not_inheritable`, `memory_debt` | MCP / CLI / JSON / HTTP |
| `agent_mutate` | journal / required | `no_agent`, `conflict`, `hash_mismatch`, `not_inheritable`, `memory_debt` | MCP / CLI / JSON / HTTP |
| `agent_specialize` | journal / required | `no_agent`, `conflict`, `hash_mismatch`, `not_inheritable`, `memory_debt` | MCP / CLI / JSON / HTTP |
| `agent_retire` | journal / required | `no_agent`, `conflict` | MCP / CLI / JSON / HTTP |
| `lineage_tree` | read / no | `no_agent` | MCP / CLI / JSON / HTTP |
| `memory_put` | journal / required | `no_agent`, `no_run`, `run_closed`, `forbidden_level`, `hash_mismatch`, `conflict`, `bad_op`, `memory_debt` | MCP / CLI / JSON / HTTP |
| `memory_route` | read / no | `no_agent` | MCP / CLI / JSON / HTTP |
| `memory_get` | read / no | `no_agent` | MCP / CLI / JSON / HTTP |
| `memory_bootcheck` | read / no | `no_agent`, `bad_op`, `hash_mismatch` | MCP / CLI / JSON / HTTP |
| `memory_history` | read / no | `no_agent` | MCP / CLI / JSON / HTTP |
| `run_open` | journal / required | `no_agent`, `conflict`, `seat_not_allowed`, `hash_mismatch` | MCP / CLI / JSON / HTTP |
| `run_beat` | journal / required | `no_run`, `run_closed`, `conflict` | MCP / CLI / JSON / HTTP |
| `run_close` | journal / required | `no_agent`, `no_run`, `run_closed`, `memory_required`, `memory_debt`, `hash_mismatch`, `conflict` | MCP / CLI / JSON / HTTP |
| `run_get` | read / no | `no_run` | MCP / CLI / JSON / HTTP |
| `bench_list` | read / no | — | MCP / CLI / JSON / HTTP |
| `bench_declare` | journal / required | `no_agent`, `conflict`, `bad_op`, `hash_mismatch`, `heldout_forbidden`, `seat_not_allowed` | MCP / CLI / JSON / HTTP |
| `bench_run` | journal / required | `no_agent`, `no_run`, `run_closed`, `forbidden_level`, `no_benchmark`, `rule_not_declared`, `bad_op`, `heldout_forbidden`, `hash_mismatch`, `seat_not_allowed`, `memory_required`, `memory_debt`, `timeout`, `conflict` | MCP / CLI / JSON / HTTP |
| `bench_status` | read / no | `no_benchmark` | MCP / CLI / JSON / HTTP |
| `bench_verdict` | journal / required | `no_benchmark`, `rule_not_declared`, `conflict` | MCP / CLI / JSON / HTTP |
| `agent_promote` | journal / required | `no_agent`, `no_benchmark`, `heldout_forbidden`, `bad_op`, `conflict` | MCP / CLI / JSON / HTTP |
| `scorecard_get` | read / no | `no_agent` | MCP / CLI / JSON / HTTP |
| `ledger_events` | read / no | — | MCP / CLI / JSON / HTTP |
| `ledger_export` | read / no | `hash_mismatch` | MCP / CLI / JSON / HTTP |
| `ledger_verify` | read / no | `hash_mismatch` | MCP / CLI / JSON / HTTP |
| `openfresnel_probe` | external / required | `timeout`, `conflict`, `bad_op` | MCP / CLI / JSON / HTTP |
| `openfresnel_spawn` | external / required | `timeout`, `conflict`, `bad_op` | MCP / CLI / JSON / HTTP |

### `reference_get`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "ref_id": {
      "enum": [
        "gold_s1",
        "memory_v21"
      ]
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "ref_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "reference": {
      "type": "object",
      "properties": {
        "id": {
          "enum": [
            "gold_s1",
            "memory_v21"
          ]
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        },
        "bytes": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "rules": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64
              },
              "section": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128
              },
              "text": {
                "type": "string",
                "minLength": 1,
                "maxLength": 16000
              }
            },
            "required": [
              "id",
              "section",
              "text"
            ],
            "additionalProperties": false
          },
          "minItems": 0,
          "maxItems": 256
        }
      },
      "required": [
        "id",
        "sha256",
        "bytes",
        "rules"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "reference"
  ],
  "additionalProperties": false
}
```

### `reference_verify`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "ref_id": {
      "enum": [
        "gold_s1",
        "memory_v21"
      ]
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "ref_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "ref_id": {
      "enum": [
        "gold_s1",
        "memory_v21"
      ]
    },
    "sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64,
      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
    },
    "bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 9007199254740991
    },
    "valid": {
      "const": true
    }
  },
  "required": [
    "ref_id",
    "sha256",
    "bytes",
    "valid"
  ],
  "additionalProperties": false
}
```

### `skill_list`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "include_retired": {
      "type": "boolean"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "skills": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "skill_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "sha256": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          },
          "retired": {
            "type": "boolean"
          }
        },
        "required": [
          "skill_id",
          "sha256",
          "retired"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 10000
    }
  },
  "required": [
    "skills"
  ],
  "additionalProperties": false
}
```

### `skill_get`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "skill_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64,
      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "skill_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "skill": {
      "type": "object",
      "properties": {
        "skill_id": {
          "type": "string",
          "minLength": 3,
          "maxLength": 64,
          "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        },
        "retired": {
          "type": "boolean"
        },
        "files": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "path": {
                "type": "string",
                "minLength": 1,
                "maxLength": 512,
                "pattern": "^(?!/)(?!.*(?:^|/)\\.{1,2}(?:/|$))(?!.*\\\\)[A-Za-z0-9._/-]+(?![\\s\\S])"
              },
              "content": {
                "type": "string",
                "minLength": 0,
                "maxLength": 65536
              }
            },
            "required": [
              "path",
              "content"
            ],
            "additionalProperties": false
          },
          "minItems": 1,
          "maxItems": 256
        }
      },
      "required": [
        "skill_id",
        "sha256",
        "retired",
        "files"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "skill"
  ],
  "additionalProperties": false
}
```

### `skill_publish`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "skill_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "files": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "minLength": 1,
            "maxLength": 512,
            "pattern": "^(?!/)(?!.*(?:^|/)\\.{1,2}(?:/|$))(?!.*\\\\)[A-Za-z0-9._/-]+(?![\\s\\S])"
          },
          "content": {
            "type": "string",
            "minLength": 0,
            "maxLength": 65536
          }
        },
        "required": [
          "path",
          "content"
        ],
        "additionalProperties": false
      },
      "minItems": 1,
      "maxItems": 256
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "skill_id",
    "files",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "skill": {
      "type": "object",
      "properties": {
        "skill_id": {
          "type": "string",
          "minLength": 3,
          "maxLength": 64,
          "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        },
        "retired": {
          "type": "boolean"
        },
        "files": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "path": {
                "type": "string",
                "minLength": 1,
                "maxLength": 512,
                "pattern": "^(?!/)(?!.*(?:^|/)\\.{1,2}(?:/|$))(?!.*\\\\)[A-Za-z0-9._/-]+(?![\\s\\S])"
              },
              "content": {
                "type": "string",
                "minLength": 0,
                "maxLength": 65536
              }
            },
            "required": [
              "path",
              "content"
            ],
            "additionalProperties": false
          },
          "minItems": 1,
          "maxItems": 256
        }
      },
      "required": [
        "skill_id",
        "sha256",
        "retired",
        "files"
      ],
      "additionalProperties": false
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "skill",
    "commit"
  ],
  "additionalProperties": false
}
```

### `skill_retire`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "skill_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64,
      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
    },
    "reason": {
      "type": "string",
      "minLength": 1,
      "maxLength": 2048
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "skill_id",
    "sha256",
    "reason",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "skill_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64,
      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
    },
    "retired": {
      "const": true
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "skill_id",
    "sha256",
    "retired",
    "commit"
  ],
  "additionalProperties": false
}
```

### `agent_create`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "display_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128
    },
    "workflow": {
      "enum": [
        "develop",
        "test",
        "review",
        "harden",
        "research",
        "orchestrate"
      ]
    },
    "language": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64
    },
    "allowed_seats": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "model": {
            "type": "string",
            "minLength": 1,
            "maxLength": 128
          },
          "effort": {
            "type": "string",
            "minLength": 1,
            "maxLength": 32,
            "pattern": "^[a-z0-9_-]+(?![\\s\\S])"
          },
          "mode": {
            "enum": [
              "headless",
              "interactive"
            ]
          }
        },
        "required": [
          "model",
          "effort",
          "mode"
        ],
        "additionalProperties": false
      },
      "minItems": 1,
      "maxItems": 16,
      "uniqueItems": true
    },
    "references": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "enum": [
              "gold_s1",
              "memory_v21"
            ]
          },
          "sha256": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          }
        },
        "required": [
          "id",
          "sha256"
        ],
        "additionalProperties": false
      },
      "minItems": 2,
      "maxItems": 2,
      "uniqueItems": true
    },
    "skills": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "skill_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "sha256": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          }
        },
        "required": [
          "skill_id",
          "sha256"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 256,
      "uniqueItems": true
    },
    "overlays": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1,
        "maxLength": 64
      },
      "minItems": 0,
      "maxItems": 64,
      "uniqueItems": true
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "agent_id",
    "display_name",
    "workflow",
    "language",
    "allowed_seats",
    "references",
    "skills",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "record": {
      "$ref": "agent.schema.json"
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "record",
    "commit"
  ],
  "additionalProperties": false
}
```

### `agent_get`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "agent_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "record": {
      "$ref": "agent.schema.json"
    }
  },
  "required": [
    "record"
  ],
  "additionalProperties": false
}
```

### `agent_list`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "workflow": {
      "enum": [
        "develop",
        "test",
        "review",
        "harden",
        "research",
        "orchestrate"
      ]
    },
    "language": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64
    },
    "status": {
      "enum": [
        "draft",
        "shadow",
        "promoted",
        "retired"
      ]
    },
    "include_retired": {
      "type": "boolean"
    },
    "after": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "agents": {
      "type": "array",
      "items": {
        "$ref": "agent.schema.json"
      },
      "minItems": 0,
      "maxItems": 1000
    },
    "next_after": {
      "anyOf": [
        {
          "type": "string",
          "minLength": 3,
          "maxLength": 64,
          "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
        },
        {
          "type": "null"
        }
      ]
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "agents",
    "next_after",
    "head"
  ],
  "additionalProperties": false
}
```

### `agent_brief`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "memory_arm": {
      "enum": [
        "none",
        "own",
        "inherited"
      ]
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "agent_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "agent_version": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64,
      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
    },
    "text": {
      "type": "string",
      "minLength": 0,
      "maxLength": 65536
    },
    "sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64,
      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
    },
    "memory_gen": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "agent_id",
    "agent_version",
    "text",
    "sha256",
    "memory_gen"
  ],
  "additionalProperties": false
}
```

### `agent_clone`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "parent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "child_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "display_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "parent_id",
    "child_id",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "record": {
      "$ref": "agent.schema.json"
    },
    "inherited_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "unit": {
            "$ref": "mem_unit.schema.json"
          },
          "source_agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "source_unit_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          },
          "unit_sha256": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          }
        },
        "required": [
          "unit",
          "source_agent_id",
          "source_unit_id",
          "unit_sha256"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 256
    },
    "rejected_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "unit_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          },
          "reason": {
            "enum": [
              "episode",
              "level_one",
              "level_three",
              "private",
              "missing_receipt",
              "invalid_receipt",
              "not_promoted",
              "scope_mismatch",
              "not_selected",
              "inactive",
              "kind_not_inheritable"
            ]
          }
        },
        "required": [
          "agent_id",
          "unit_id",
          "reason"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 10000
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "record",
    "inherited_units",
    "rejected_units",
    "commit"
  ],
  "additionalProperties": false
}
```

### `agent_distill`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "parent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "child_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "display_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128
    },
    "unit_ids": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 8,
        "maxLength": 64,
        "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
      },
      "minItems": 0,
      "maxItems": 256,
      "uniqueItems": true
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "parent_id",
    "child_id",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "record": {
      "$ref": "agent.schema.json"
    },
    "inherited_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "unit": {
            "$ref": "mem_unit.schema.json"
          },
          "source_agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "source_unit_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          },
          "unit_sha256": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          }
        },
        "required": [
          "unit",
          "source_agent_id",
          "source_unit_id",
          "unit_sha256"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 256
    },
    "rejected_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "unit_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          },
          "reason": {
            "enum": [
              "episode",
              "level_one",
              "level_three",
              "private",
              "missing_receipt",
              "invalid_receipt",
              "not_promoted",
              "scope_mismatch",
              "not_selected",
              "inactive",
              "kind_not_inheritable"
            ]
          }
        },
        "required": [
          "agent_id",
          "unit_id",
          "reason"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 10000
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "record",
    "inherited_units",
    "rejected_units",
    "commit"
  ],
  "additionalProperties": false
}
```

### `agent_cross`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "parent_ids": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 3,
        "maxLength": 64,
        "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
      },
      "minItems": 2,
      "maxItems": 2,
      "uniqueItems": true
    },
    "child_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "display_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "parent_ids",
    "child_id",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "record": {
      "$ref": "agent.schema.json"
    },
    "inherited_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "unit": {
            "$ref": "mem_unit.schema.json"
          },
          "source_agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "source_unit_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          },
          "unit_sha256": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          }
        },
        "required": [
          "unit",
          "source_agent_id",
          "source_unit_id",
          "unit_sha256"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 256
    },
    "rejected_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "unit_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          },
          "reason": {
            "enum": [
              "episode",
              "level_one",
              "level_three",
              "private",
              "missing_receipt",
              "invalid_receipt",
              "not_promoted",
              "scope_mismatch",
              "not_selected",
              "inactive",
              "kind_not_inheritable"
            ]
          }
        },
        "required": [
          "agent_id",
          "unit_id",
          "reason"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 10000
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "record",
    "inherited_units",
    "rejected_units",
    "commit"
  ],
  "additionalProperties": false
}
```

### `agent_mutate`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "parent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "child_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "display_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128
    },
    "change": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "kind": {
              "const": "skill"
            },
            "skill_id": {
              "type": "string",
              "minLength": 3,
              "maxLength": 64,
              "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
            },
            "from_sha256": {
              "type": "string",
              "minLength": 64,
              "maxLength": 64,
              "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
            },
            "to": {
              "type": "object",
              "properties": {
                "skill_id": {
                  "type": "string",
                  "minLength": 3,
                  "maxLength": 64,
                  "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
                },
                "sha256": {
                  "type": "string",
                  "minLength": 64,
                  "maxLength": 64,
                  "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
                }
              },
              "required": [
                "skill_id",
                "sha256"
              ],
              "additionalProperties": false
            }
          },
          "required": [
            "kind",
            "skill_id",
            "from_sha256",
            "to"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "kind": {
              "const": "rule"
            },
            "rule_id": {
              "type": "string",
              "minLength": 1,
              "maxLength": 64
            },
            "text": {
              "type": "string",
              "minLength": 1,
              "maxLength": 16000
            }
          },
          "required": [
            "kind",
            "rule_id",
            "text"
          ],
          "additionalProperties": false
        }
      ]
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "parent_id",
    "child_id",
    "change",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "record": {
      "$ref": "agent.schema.json"
    },
    "inherited_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "unit": {
            "$ref": "mem_unit.schema.json"
          },
          "source_agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "source_unit_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          },
          "unit_sha256": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          }
        },
        "required": [
          "unit",
          "source_agent_id",
          "source_unit_id",
          "unit_sha256"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 256
    },
    "rejected_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "unit_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          },
          "reason": {
            "enum": [
              "episode",
              "level_one",
              "level_three",
              "private",
              "missing_receipt",
              "invalid_receipt",
              "not_promoted",
              "scope_mismatch",
              "not_selected",
              "inactive",
              "kind_not_inheritable"
            ]
          }
        },
        "required": [
          "agent_id",
          "unit_id",
          "reason"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 10000
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "record",
    "inherited_units",
    "rejected_units",
    "commit"
  ],
  "additionalProperties": false
}
```

### `agent_specialize`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "parent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "child_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "display_name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128
    },
    "language": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "parent_id",
    "child_id",
    "language",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "record": {
      "$ref": "agent.schema.json"
    },
    "inherited_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "unit": {
            "$ref": "mem_unit.schema.json"
          },
          "source_agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "source_unit_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          },
          "unit_sha256": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          }
        },
        "required": [
          "unit",
          "source_agent_id",
          "source_unit_id",
          "unit_sha256"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 256
    },
    "rejected_units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "unit_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          },
          "reason": {
            "enum": [
              "episode",
              "level_one",
              "level_three",
              "private",
              "missing_receipt",
              "invalid_receipt",
              "not_promoted",
              "scope_mismatch",
              "not_selected",
              "inactive",
              "kind_not_inheritable"
            ]
          }
        },
        "required": [
          "agent_id",
          "unit_id",
          "reason"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 10000
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "record",
    "inherited_units",
    "rejected_units",
    "commit"
  ],
  "additionalProperties": false
}
```

### `agent_retire`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "reason": {
      "type": "string",
      "minLength": 1,
      "maxLength": 2048
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "agent_id",
    "reason",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "record": {
      "$ref": "agent.schema.json"
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "record",
    "commit"
  ],
  "additionalProperties": false
}
```

### `lineage_tree`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "root_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "include_retired": {
      "type": "boolean"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "parents": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 3,
              "maxLength": 64,
              "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
            },
            "minItems": 0,
            "maxItems": 2
          },
          "generation": {
            "type": "integer",
            "minimum": 0,
            "maximum": 9007199254740991
          },
          "op": {
            "enum": [
              "genesis",
              "clone",
              "distill",
              "cross",
              "mutate",
              "specialize"
            ]
          },
          "status": {
            "enum": [
              "draft",
              "shadow",
              "promoted",
              "retired"
            ]
          }
        },
        "required": [
          "agent_id",
          "parents",
          "generation",
          "op",
          "status"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 1000000
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "nodes",
    "head"
  ],
  "additionalProperties": false
}
```

### `memory_put`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "unit": {
      "$ref": "mem_unit.schema.json"
    },
    "run_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "agent_id",
    "unit",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "unit": {
      "$ref": "mem_unit.schema.json"
    },
    "memory_gen": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "unit",
    "memory_gen",
    "commit"
  ],
  "additionalProperties": false
}
```

### `memory_route`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "query": {
      "type": "string",
      "minLength": 1,
      "maxLength": 512
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 50
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "agent_id",
    "query"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "units": {
      "type": "array",
      "items": {
        "$ref": "mem_unit.schema.json"
      },
      "minItems": 0,
      "maxItems": 50
    },
    "answer": {
      "type": "string",
      "minLength": 1,
      "maxLength": 65536
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "units",
    "answer",
    "head"
  ],
  "additionalProperties": false
}
```

### `memory_get`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "unit_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "agent_id",
    "unit_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "unit": {
      "$ref": "mem_unit.schema.json"
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "unit",
    "head"
  ],
  "additionalProperties": false
}
```

### `memory_bootcheck`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "observed": {
      "type": "object",
      "properties": {
        "agent_version": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        },
        "memory_gen": {
          "type": "integer",
          "minimum": 0,
          "maximum": 9007199254740991
        },
        "head": {
          "type": "integer",
          "minimum": 0,
          "maximum": 9007199254740991
        },
        "entry_sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "agent_version",
        "memory_gen",
        "head",
        "entry_sha256"
      ],
      "additionalProperties": false
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "agent_id",
    "observed"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "passed": {
      "const": true
    },
    "code": {
      "const": "OK"
    },
    "checks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string",
            "minLength": 1,
            "maxLength": 64
          },
          "passed": {
            "type": "boolean"
          },
          "detail": {
            "type": "string",
            "minLength": 0,
            "maxLength": 2048
          }
        },
        "required": [
          "id",
          "passed"
        ],
        "additionalProperties": false
      },
      "minItems": 1,
      "maxItems": 32
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "passed",
    "code",
    "checks",
    "head"
  ],
  "additionalProperties": false
}
```

### `memory_history`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "unit_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "after": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "agent_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "events": {
      "type": "array",
      "items": {
        "$ref": "event.schema.json"
      },
      "minItems": 0,
      "maxItems": 1000
    },
    "next_after": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "has_more": {
      "type": "boolean"
    },
    "resync": {
      "type": "boolean"
    }
  },
  "required": [
    "events",
    "next_after",
    "head",
    "has_more",
    "resync"
  ],
  "additionalProperties": false
}
```

### `run_open`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "run_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "seat": {
      "type": "object",
      "properties": {
        "model": {
          "type": "string",
          "minLength": 1,
          "maxLength": 128
        },
        "effort": {
          "type": "string",
          "minLength": 1,
          "maxLength": 32,
          "pattern": "^[a-z0-9_-]+(?![\\s\\S])"
        },
        "mode": {
          "enum": [
            "headless",
            "interactive"
          ]
        }
      },
      "required": [
        "model",
        "effort",
        "mode"
      ],
      "additionalProperties": false
    },
    "task": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "minLength": 8,
          "maxLength": 64,
          "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
        },
        "kind": {
          "type": "string",
          "minLength": 1,
          "maxLength": 64
        },
        "language": {
          "type": "string",
          "minLength": 1,
          "maxLength": 64
        },
        "bank_id": {
          "type": "string",
          "minLength": 3,
          "maxLength": 64,
          "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
        },
        "bench_id": {
          "type": "string",
          "minLength": 8,
          "maxLength": 64,
          "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
        },
        "split": {
          "enum": [
            "select",
            "heldout"
          ]
        }
      },
      "required": [
        "id",
        "kind",
        "language"
      ],
      "additionalProperties": false
    },
    "parents_context": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 64,
            "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
          },
          "agent_version": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          },
          "run_id": {
            "type": "string",
            "minLength": 8,
            "maxLength": 64,
            "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
          }
        },
        "required": [
          "agent_id",
          "agent_version",
          "run_id"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 64,
      "uniqueItems": true
    },
    "memory_arm": {
      "enum": [
        "none",
        "own",
        "inherited"
      ]
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "run_id",
    "agent_id",
    "seat",
    "task",
    "parents_context",
    "memory_arm",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "opened": {
      "$ref": "event.schema.json"
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "opened",
    "commit"
  ],
  "additionalProperties": false
}
```

### `run_beat`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "run_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "progress": {
      "type": "string",
      "minLength": 1,
      "maxLength": 2048
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "run_id",
    "progress",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "event": {
      "$ref": "event.schema.json"
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "event",
    "commit"
  ],
  "additionalProperties": false
}
```

### `run_close`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "run_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "outcome": {
      "type": "object",
      "properties": {
        "verdict": {
          "enum": [
            "ADMIT",
            "HOLD",
            "red",
            "green",
            "error"
          ]
        },
        "repair_loops": {
          "type": "integer",
          "minimum": 0,
          "maximum": 1000000
        },
        "findings": {
          "type": "object",
          "properties": {
            "confirmed": {
              "type": "integer",
              "minimum": 0,
              "maximum": 1000000
            },
            "refuted": {
              "type": "integer",
              "minimum": 0,
              "maximum": 1000000
            }
          },
          "required": [
            "confirmed",
            "refuted"
          ],
          "additionalProperties": false
        }
      },
      "required": [
        "verdict",
        "repair_loops",
        "findings"
      ],
      "additionalProperties": false
    },
    "cost": {
      "type": "object",
      "properties": {
        "tokens_in": {
          "anyOf": [
            {
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            },
            {
              "type": "null"
            }
          ]
        },
        "tokens_out": {
          "anyOf": [
            {
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            },
            {
              "type": "null"
            }
          ]
        },
        "tokens_cache": {
          "anyOf": [
            {
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            },
            {
              "type": "null"
            }
          ]
        },
        "duration_ms": {
          "anyOf": [
            {
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            },
            {
              "type": "null"
            }
          ]
        },
        "cost_micro_usd": {
          "anyOf": [
            {
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "tokens_in",
        "tokens_out",
        "tokens_cache",
        "duration_ms",
        "cost_micro_usd"
      ],
      "additionalProperties": false
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "minLength": 1,
            "maxLength": 512,
            "pattern": "^(?!/)(?!.*(?:^|/)\\.{1,2}(?:/|$))(?!.*\\\\)[A-Za-z0-9._/-]+(?![\\s\\S])"
          },
          "sha256": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          }
        },
        "required": [
          "path",
          "sha256"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 64,
      "uniqueItems": true
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "run_id",
    "outcome",
    "cost",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "run": {
      "$ref": "run.schema.json"
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "run",
    "commit"
  ],
  "additionalProperties": false
}
```

### `run_get`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "run_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "run_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "opened": {
      "$ref": "event.schema.json"
    },
    "closed": {
      "anyOf": [
        {
          "$ref": "run.schema.json"
        },
        {
          "type": "null"
        }
      ]
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "opened",
    "closed",
    "head"
  ],
  "additionalProperties": false
}
```

### `bench_list`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "after": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "benches": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "declaration": {
            "$ref": "bench_declared.schema.json"
          },
          "state": {
            "enum": [
              "declared",
              "queued",
              "running",
              "stalled",
              "complete"
            ]
          },
          "results": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "bench_id": {
                  "type": "string",
                  "minLength": 8,
                  "maxLength": 64,
                  "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
                },
                "task_id": {
                  "type": "string",
                  "minLength": 8,
                  "maxLength": 64,
                  "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
                },
                "agent_id": {
                  "type": "string",
                  "minLength": 3,
                  "maxLength": 64,
                  "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
                },
                "seat": {
                  "type": "object",
                  "properties": {
                    "model": {
                      "type": "string",
                      "minLength": 1,
                      "maxLength": 128
                    },
                    "effort": {
                      "type": "string",
                      "minLength": 1,
                      "maxLength": 32,
                      "pattern": "^[a-z0-9_-]+(?![\\s\\S])"
                    },
                    "mode": {
                      "enum": [
                        "headless",
                        "interactive"
                      ]
                    }
                  },
                  "required": [
                    "model",
                    "effort",
                    "mode"
                  ],
                  "additionalProperties": false
                },
                "memory_arm": {
                  "enum": [
                    "none",
                    "own",
                    "inherited"
                  ]
                },
                "run_id": {
                  "type": "string",
                  "minLength": 8,
                  "maxLength": 64,
                  "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
                },
                "verdict": {
                  "enum": [
                    "ADMIT",
                    "HOLD",
                    "red",
                    "green",
                    "error"
                  ]
                },
                "correctness": {
                  "enum": [
                    0,
                    1
                  ]
                },
                "cost": {
                  "type": "object",
                  "properties": {
                    "tokens_in": {
                      "anyOf": [
                        {
                          "type": "integer",
                          "minimum": 0,
                          "maximum": 9007199254740991
                        },
                        {
                          "type": "null"
                        }
                      ]
                    },
                    "tokens_out": {
                      "anyOf": [
                        {
                          "type": "integer",
                          "minimum": 0,
                          "maximum": 9007199254740991
                        },
                        {
                          "type": "null"
                        }
                      ]
                    },
                    "tokens_cache": {
                      "anyOf": [
                        {
                          "type": "integer",
                          "minimum": 0,
                          "maximum": 9007199254740991
                        },
                        {
                          "type": "null"
                        }
                      ]
                    },
                    "duration_ms": {
                      "anyOf": [
                        {
                          "type": "integer",
                          "minimum": 0,
                          "maximum": 9007199254740991
                        },
                        {
                          "type": "null"
                        }
                      ]
                    },
                    "cost_micro_usd": {
                      "anyOf": [
                        {
                          "type": "integer",
                          "minimum": 0,
                          "maximum": 9007199254740991
                        },
                        {
                          "type": "null"
                        }
                      ]
                    }
                  },
                  "required": [
                    "tokens_in",
                    "tokens_out",
                    "tokens_cache",
                    "duration_ms",
                    "cost_micro_usd"
                  ],
                  "additionalProperties": false
                }
              },
              "required": [
                "bench_id",
                "task_id",
                "agent_id",
                "seat",
                "memory_arm",
                "run_id",
                "verdict",
                "correctness",
                "cost"
              ],
              "additionalProperties": false
            },
            "minItems": 0,
            "maxItems": 1000000
          },
          "verdict": {
            "anyOf": [
              {
                "type": "object",
                "properties": {
                  "bench_id": {
                    "type": "string",
                    "minLength": 8,
                    "maxLength": 64,
                    "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
                  },
                  "decision": {
                    "enum": [
                      "superior",
                      "not_superior",
                      "inconclusive"
                    ]
                  },
                  "llr": {
                    "type": "number"
                  },
                  "n_discordant": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 9007199254740991
                  },
                  "credit": {
                    "type": "object",
                    "properties": {
                      "gain": {
                        "type": "number",
                        "minimum": -1,
                        "maximum": 1
                      },
                      "baseline_dispersion": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1
                      },
                      "minimum_reward": {
                        "type": "number",
                        "minimum": -1,
                        "maximum": 1
                      },
                      "credited": {
                        "type": "boolean"
                      }
                    },
                    "required": [
                      "gain",
                      "baseline_dispersion",
                      "minimum_reward",
                      "credited"
                    ],
                    "additionalProperties": false
                  }
                },
                "required": [
                  "bench_id",
                  "decision",
                  "llr",
                  "n_discordant",
                  "credit"
                ],
                "additionalProperties": false
              },
              {
                "type": "null"
              }
            ]
          },
          "head": {
            "type": "integer",
            "minimum": 0,
            "maximum": 9007199254740991
          }
        },
        "required": [
          "declaration",
          "state",
          "results",
          "verdict",
          "head"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 1000
    },
    "next_after": {
      "anyOf": [
        {
          "type": "string",
          "minLength": 8,
          "maxLength": 64,
          "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
        },
        {
          "type": "null"
        }
      ]
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "benches",
    "next_after",
    "head"
  ],
  "additionalProperties": false
}
```

### `bench_declare`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "declaration": {
      "$ref": "bench_declared.schema.json"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "declaration",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "bench": {
      "type": "object",
      "properties": {
        "declaration": {
          "$ref": "bench_declared.schema.json"
        },
        "state": {
          "enum": [
            "declared",
            "queued",
            "running",
            "stalled",
            "complete"
          ]
        },
        "results": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "bench_id": {
                "type": "string",
                "minLength": 8,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
              },
              "task_id": {
                "type": "string",
                "minLength": 8,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
              },
              "agent_id": {
                "type": "string",
                "minLength": 3,
                "maxLength": 64,
                "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
              },
              "seat": {
                "type": "object",
                "properties": {
                  "model": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 128
                  },
                  "effort": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 32,
                    "pattern": "^[a-z0-9_-]+(?![\\s\\S])"
                  },
                  "mode": {
                    "enum": [
                      "headless",
                      "interactive"
                    ]
                  }
                },
                "required": [
                  "model",
                  "effort",
                  "mode"
                ],
                "additionalProperties": false
              },
              "memory_arm": {
                "enum": [
                  "none",
                  "own",
                  "inherited"
                ]
              },
              "run_id": {
                "type": "string",
                "minLength": 8,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
              },
              "verdict": {
                "enum": [
                  "ADMIT",
                  "HOLD",
                  "red",
                  "green",
                  "error"
                ]
              },
              "correctness": {
                "enum": [
                  0,
                  1
                ]
              },
              "cost": {
                "type": "object",
                "properties": {
                  "tokens_in": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "tokens_out": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "tokens_cache": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "duration_ms": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "cost_micro_usd": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "tokens_in",
                  "tokens_out",
                  "tokens_cache",
                  "duration_ms",
                  "cost_micro_usd"
                ],
                "additionalProperties": false
              }
            },
            "required": [
              "bench_id",
              "task_id",
              "agent_id",
              "seat",
              "memory_arm",
              "run_id",
              "verdict",
              "correctness",
              "cost"
            ],
            "additionalProperties": false
          },
          "minItems": 0,
          "maxItems": 1000000
        },
        "verdict": {
          "anyOf": [
            {
              "type": "object",
              "properties": {
                "bench_id": {
                  "type": "string",
                  "minLength": 8,
                  "maxLength": 64,
                  "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
                },
                "decision": {
                  "enum": [
                    "superior",
                    "not_superior",
                    "inconclusive"
                  ]
                },
                "llr": {
                  "type": "number"
                },
                "n_discordant": {
                  "type": "integer",
                  "minimum": 0,
                  "maximum": 9007199254740991
                },
                "credit": {
                  "type": "object",
                  "properties": {
                    "gain": {
                      "type": "number",
                      "minimum": -1,
                      "maximum": 1
                    },
                    "baseline_dispersion": {
                      "type": "number",
                      "minimum": 0,
                      "maximum": 1
                    },
                    "minimum_reward": {
                      "type": "number",
                      "minimum": -1,
                      "maximum": 1
                    },
                    "credited": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "gain",
                    "baseline_dispersion",
                    "minimum_reward",
                    "credited"
                  ],
                  "additionalProperties": false
                }
              },
              "required": [
                "bench_id",
                "decision",
                "llr",
                "n_discordant",
                "credit"
              ],
              "additionalProperties": false
            },
            {
              "type": "null"
            }
          ]
        },
        "head": {
          "type": "integer",
          "minimum": 0,
          "maximum": 9007199254740991
        }
      },
      "required": [
        "declaration",
        "state",
        "results",
        "verdict",
        "head"
      ],
      "additionalProperties": false
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "bench",
    "commit"
  ],
  "additionalProperties": false
}
```

### `bench_run`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "bench_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "runner": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "kind": {
              "const": "fake"
            },
            "seed": {
              "type": "integer",
              "minimum": 0,
              "maximum": 4294967295
            }
          },
          "required": [
            "kind",
            "seed"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "kind": {
              "const": "command"
            },
            "argv": {
              "type": "array",
              "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 4096
              },
              "minItems": 1,
              "maxItems": 128
            },
            "timeout_ms": {
              "type": "integer",
              "minimum": 1,
              "maximum": 3600000
            }
          },
          "required": [
            "kind",
            "argv",
            "timeout_ms"
          ],
          "additionalProperties": false
        }
      ]
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "bench_id",
    "runner",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "bench": {
      "type": "object",
      "properties": {
        "declaration": {
          "$ref": "bench_declared.schema.json"
        },
        "state": {
          "enum": [
            "declared",
            "queued",
            "running",
            "stalled",
            "complete"
          ]
        },
        "results": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "bench_id": {
                "type": "string",
                "minLength": 8,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
              },
              "task_id": {
                "type": "string",
                "minLength": 8,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
              },
              "agent_id": {
                "type": "string",
                "minLength": 3,
                "maxLength": 64,
                "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
              },
              "seat": {
                "type": "object",
                "properties": {
                  "model": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 128
                  },
                  "effort": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 32,
                    "pattern": "^[a-z0-9_-]+(?![\\s\\S])"
                  },
                  "mode": {
                    "enum": [
                      "headless",
                      "interactive"
                    ]
                  }
                },
                "required": [
                  "model",
                  "effort",
                  "mode"
                ],
                "additionalProperties": false
              },
              "memory_arm": {
                "enum": [
                  "none",
                  "own",
                  "inherited"
                ]
              },
              "run_id": {
                "type": "string",
                "minLength": 8,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
              },
              "verdict": {
                "enum": [
                  "ADMIT",
                  "HOLD",
                  "red",
                  "green",
                  "error"
                ]
              },
              "correctness": {
                "enum": [
                  0,
                  1
                ]
              },
              "cost": {
                "type": "object",
                "properties": {
                  "tokens_in": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "tokens_out": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "tokens_cache": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "duration_ms": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "cost_micro_usd": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "tokens_in",
                  "tokens_out",
                  "tokens_cache",
                  "duration_ms",
                  "cost_micro_usd"
                ],
                "additionalProperties": false
              }
            },
            "required": [
              "bench_id",
              "task_id",
              "agent_id",
              "seat",
              "memory_arm",
              "run_id",
              "verdict",
              "correctness",
              "cost"
            ],
            "additionalProperties": false
          },
          "minItems": 0,
          "maxItems": 1000000
        },
        "verdict": {
          "anyOf": [
            {
              "type": "object",
              "properties": {
                "bench_id": {
                  "type": "string",
                  "minLength": 8,
                  "maxLength": 64,
                  "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
                },
                "decision": {
                  "enum": [
                    "superior",
                    "not_superior",
                    "inconclusive"
                  ]
                },
                "llr": {
                  "type": "number"
                },
                "n_discordant": {
                  "type": "integer",
                  "minimum": 0,
                  "maximum": 9007199254740991
                },
                "credit": {
                  "type": "object",
                  "properties": {
                    "gain": {
                      "type": "number",
                      "minimum": -1,
                      "maximum": 1
                    },
                    "baseline_dispersion": {
                      "type": "number",
                      "minimum": 0,
                      "maximum": 1
                    },
                    "minimum_reward": {
                      "type": "number",
                      "minimum": -1,
                      "maximum": 1
                    },
                    "credited": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "gain",
                    "baseline_dispersion",
                    "minimum_reward",
                    "credited"
                  ],
                  "additionalProperties": false
                }
              },
              "required": [
                "bench_id",
                "decision",
                "llr",
                "n_discordant",
                "credit"
              ],
              "additionalProperties": false
            },
            {
              "type": "null"
            }
          ]
        },
        "head": {
          "type": "integer",
          "minimum": 0,
          "maximum": 9007199254740991
        }
      },
      "required": [
        "declaration",
        "state",
        "results",
        "verdict",
        "head"
      ],
      "additionalProperties": false
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "bench",
    "commit"
  ],
  "additionalProperties": false
}
```

### `bench_status`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "bench_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "bench_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "bench": {
      "type": "object",
      "properties": {
        "declaration": {
          "$ref": "bench_declared.schema.json"
        },
        "state": {
          "enum": [
            "declared",
            "queued",
            "running",
            "stalled",
            "complete"
          ]
        },
        "results": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "bench_id": {
                "type": "string",
                "minLength": 8,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
              },
              "task_id": {
                "type": "string",
                "minLength": 8,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
              },
              "agent_id": {
                "type": "string",
                "minLength": 3,
                "maxLength": 64,
                "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
              },
              "seat": {
                "type": "object",
                "properties": {
                  "model": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 128
                  },
                  "effort": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 32,
                    "pattern": "^[a-z0-9_-]+(?![\\s\\S])"
                  },
                  "mode": {
                    "enum": [
                      "headless",
                      "interactive"
                    ]
                  }
                },
                "required": [
                  "model",
                  "effort",
                  "mode"
                ],
                "additionalProperties": false
              },
              "memory_arm": {
                "enum": [
                  "none",
                  "own",
                  "inherited"
                ]
              },
              "run_id": {
                "type": "string",
                "minLength": 8,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
              },
              "verdict": {
                "enum": [
                  "ADMIT",
                  "HOLD",
                  "red",
                  "green",
                  "error"
                ]
              },
              "correctness": {
                "enum": [
                  0,
                  1
                ]
              },
              "cost": {
                "type": "object",
                "properties": {
                  "tokens_in": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "tokens_out": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "tokens_cache": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "duration_ms": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  },
                  "cost_micro_usd": {
                    "anyOf": [
                      {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 9007199254740991
                      },
                      {
                        "type": "null"
                      }
                    ]
                  }
                },
                "required": [
                  "tokens_in",
                  "tokens_out",
                  "tokens_cache",
                  "duration_ms",
                  "cost_micro_usd"
                ],
                "additionalProperties": false
              }
            },
            "required": [
              "bench_id",
              "task_id",
              "agent_id",
              "seat",
              "memory_arm",
              "run_id",
              "verdict",
              "correctness",
              "cost"
            ],
            "additionalProperties": false
          },
          "minItems": 0,
          "maxItems": 1000000
        },
        "verdict": {
          "anyOf": [
            {
              "type": "object",
              "properties": {
                "bench_id": {
                  "type": "string",
                  "minLength": 8,
                  "maxLength": 64,
                  "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
                },
                "decision": {
                  "enum": [
                    "superior",
                    "not_superior",
                    "inconclusive"
                  ]
                },
                "llr": {
                  "type": "number"
                },
                "n_discordant": {
                  "type": "integer",
                  "minimum": 0,
                  "maximum": 9007199254740991
                },
                "credit": {
                  "type": "object",
                  "properties": {
                    "gain": {
                      "type": "number",
                      "minimum": -1,
                      "maximum": 1
                    },
                    "baseline_dispersion": {
                      "type": "number",
                      "minimum": 0,
                      "maximum": 1
                    },
                    "minimum_reward": {
                      "type": "number",
                      "minimum": -1,
                      "maximum": 1
                    },
                    "credited": {
                      "type": "boolean"
                    }
                  },
                  "required": [
                    "gain",
                    "baseline_dispersion",
                    "minimum_reward",
                    "credited"
                  ],
                  "additionalProperties": false
                }
              },
              "required": [
                "bench_id",
                "decision",
                "llr",
                "n_discordant",
                "credit"
              ],
              "additionalProperties": false
            },
            {
              "type": "null"
            }
          ]
        },
        "head": {
          "type": "integer",
          "minimum": 0,
          "maximum": 9007199254740991
        }
      },
      "required": [
        "declaration",
        "state",
        "results",
        "verdict",
        "head"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "bench"
  ],
  "additionalProperties": false
}
```

### `bench_verdict`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "bench_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "bench_id",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "verdict": {
      "type": "object",
      "properties": {
        "bench_id": {
          "type": "string",
          "minLength": 8,
          "maxLength": 64,
          "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
        },
        "decision": {
          "enum": [
            "superior",
            "not_superior",
            "inconclusive"
          ]
        },
        "llr": {
          "type": "number"
        },
        "n_discordant": {
          "type": "integer",
          "minimum": 0,
          "maximum": 9007199254740991
        },
        "credit": {
          "type": "object",
          "properties": {
            "gain": {
              "type": "number",
              "minimum": -1,
              "maximum": 1
            },
            "baseline_dispersion": {
              "type": "number",
              "minimum": 0,
              "maximum": 1
            },
            "minimum_reward": {
              "type": "number",
              "minimum": -1,
              "maximum": 1
            },
            "credited": {
              "type": "boolean"
            }
          },
          "required": [
            "gain",
            "baseline_dispersion",
            "minimum_reward",
            "credited"
          ],
          "additionalProperties": false
        }
      },
      "required": [
        "bench_id",
        "decision",
        "llr",
        "n_discordant",
        "credit"
      ],
      "additionalProperties": false
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "verdict",
    "commit"
  ],
  "additionalProperties": false
}
```

### `agent_promote`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "bench_id": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    },
    "expected_head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "agent_id",
    "bench_id",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "record": {
      "$ref": "agent.schema.json"
    },
    "commit": {
      "type": "object",
      "properties": {
        "event_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 18,
            "maxLength": 18,
            "pattern": "^e-[0-9a-f]{16}(?![\\s\\S])"
          },
          "minItems": 1,
          "maxItems": 10000
        },
        "head": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "sha256": {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        }
      },
      "required": [
        "event_ids",
        "head",
        "sha256"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "record",
    "commit"
  ],
  "additionalProperties": false
}
```

### `scorecard_get`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "agent_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "groups": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "seat": {
            "type": "object",
            "properties": {
              "model": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128
              },
              "effort": {
                "type": "string",
                "minLength": 1,
                "maxLength": 32,
                "pattern": "^[a-z0-9_-]+(?![\\s\\S])"
              },
              "mode": {
                "enum": [
                  "headless",
                  "interactive"
                ]
              }
            },
            "required": [
              "model",
              "effort",
              "mode"
            ],
            "additionalProperties": false
          },
          "memory_arm": {
            "enum": [
              "none",
              "own",
              "inherited"
            ]
          },
          "runs": {
            "type": "integer",
            "minimum": 0,
            "maximum": 9007199254740991
          },
          "successes": {
            "type": "integer",
            "minimum": 0,
            "maximum": 9007199254740991
          },
          "unknown_costs": {
            "type": "integer",
            "minimum": 0,
            "maximum": 9007199254740991
          },
          "mean_cost_micro_usd": {
            "anyOf": [
              {
                "type": "number",
                "minimum": 0
              },
              {
                "type": "null"
              }
            ]
          },
          "mean_duration_ms": {
            "anyOf": [
              {
                "type": "number",
                "minimum": 0
              },
              {
                "type": "null"
              }
            ]
          }
        },
        "required": [
          "seat",
          "memory_arm",
          "runs",
          "successes",
          "unknown_costs",
          "mean_cost_micro_usd",
          "mean_duration_ms"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 256
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    }
  },
  "required": [
    "agent_id",
    "groups",
    "head"
  ],
  "additionalProperties": false
}
```

### `ledger_events`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "after": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "wait_ms": {
      "type": "integer",
      "minimum": 0,
      "maximum": 30000
    },
    "agent_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "kinds": {
      "type": "array",
      "items": {
        "enum": [
          "reference.pinned",
          "skill.published",
          "skill.retired",
          "agent.born",
          "agent.status",
          "memory.put",
          "memory.retire",
          "run.open",
          "run.beat",
          "run.close",
          "bench.declared",
          "bench.result",
          "bench.verdict"
        ]
      },
      "minItems": 0,
      "maxItems": 13,
      "uniqueItems": true
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "events": {
      "type": "array",
      "items": {
        "$ref": "event.schema.json"
      },
      "minItems": 0,
      "maxItems": 1000
    },
    "next_after": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "has_more": {
      "type": "boolean"
    },
    "resync": {
      "type": "boolean"
    }
  },
  "required": [
    "events",
    "next_after",
    "head",
    "has_more",
    "resync"
  ],
  "additionalProperties": false
}
```

### `ledger_export`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "out": {
      "type": "string",
      "minLength": 1,
      "maxLength": 512,
      "pattern": "^(?!/)(?!.*(?:^|/)\\.{1,2}(?:/|$))(?!.*\\\\)[A-Za-z0-9._/-]+(?![\\s\\S])"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [
    "out"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "out": {
      "type": "string",
      "minLength": 1,
      "maxLength": 512,
      "pattern": "^(?!/)(?!.*(?:^|/)\\.{1,2}(?:/|$))(?!.*\\\\)[A-Za-z0-9._/-]+(?![\\s\\S])"
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "manifest": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "minLength": 1,
            "maxLength": 512,
            "pattern": "^(?!/)(?!.*(?:^|/)\\.{1,2}(?:/|$))(?!.*\\\\)[A-Za-z0-9._/-]+(?![\\s\\S])"
          },
          "sha256": {
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
          }
        },
        "required": [
          "path",
          "sha256"
        ],
        "additionalProperties": false
      },
      "minItems": 1,
      "maxItems": 1000000
    }
  },
  "required": [
    "out",
    "head",
    "manifest"
  ],
  "additionalProperties": false
}
```

### `ledger_verify`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    }
  },
  "required": [],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "valid": {
      "const": true
    },
    "head": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "sha256": {
      "anyOf": [
        {
          "type": "string",
          "minLength": 64,
          "maxLength": 64,
          "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
        },
        {
          "type": "null"
        }
      ]
    },
    "torn_tail_bytes": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "issues": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "path": {
            "type": "string",
            "minLength": 1,
            "maxLength": 512,
            "pattern": "^(?!/)(?!.*(?:^|/)\\.{1,2}(?:/|$))(?!.*\\\\)[A-Za-z0-9._/-]+(?![\\s\\S])"
          },
          "line": {
            "anyOf": [
              {
                "type": "integer",
                "minimum": 1,
                "maximum": 9007199254740991
              },
              {
                "type": "null"
              }
            ]
          },
          "code": {
            "enum": [
              "hash_mismatch",
              "bad_args",
              "projection_drift",
              "torn_tail"
            ]
          },
          "detail": {
            "type": "string",
            "minLength": 1,
            "maxLength": 2048
          }
        },
        "required": [
          "path",
          "line",
          "code",
          "detail"
        ],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 1000000
    }
  },
  "required": [
    "valid",
    "head",
    "sha256",
    "torn_tail_bytes",
    "issues"
  ],
  "additionalProperties": false
}
```

### `openfresnel_probe`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "commands_dir": {
      "type": "string",
      "minLength": 1,
      "maxLength": 4096
    },
    "contract_file": {
      "type": "string",
      "minLength": 1,
      "maxLength": 4096
    },
    "timeout_ms": {
      "type": "integer",
      "minimum": 1,
      "maximum": 60000
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    }
  },
  "required": [
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "rid": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "available": {
      "const": true
    },
    "verbs": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1,
        "maxLength": 64
      },
      "minItems": 0,
      "maxItems": 256
    },
    "receipt_family": {
      "enum": [
        "compiler",
        "deck"
      ]
    }
  },
  "required": [
    "rid",
    "available",
    "verbs",
    "receipt_family"
  ],
  "additionalProperties": false
}
```

### `openfresnel_spawn`

Arguments:

```json
{
  "type": "object",
  "properties": {
    "commands_dir": {
      "type": "string",
      "minLength": 1,
      "maxLength": 4096
    },
    "contract_file": {
      "type": "string",
      "minLength": 1,
      "maxLength": 4096
    },
    "timeout_ms": {
      "type": "integer",
      "minimum": 1,
      "maximum": 60000
    },
    "mode": {
      "enum": [
        "json",
        "drain"
      ]
    },
    "endpoint": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{0,63}(?![\\s\\S])"
    },
    "envelope": {
      "$ref": "family_envelope.schema.json"
    },
    "agent": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]{2,63}(?![\\s\\S])"
    },
    "op_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128,
      "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}(?![\\s\\S])"
    }
  },
  "required": [
    "mode",
    "agent",
    "op_id"
  ],
  "additionalProperties": false
}
```

Result data:

```json
{
  "type": "object",
  "properties": {
    "rid": {
      "type": "string",
      "minLength": 8,
      "maxLength": 64,
      "pattern": "^[A-Za-z0-9_-]{8,64}(?![\\s\\S])"
    },
    "state": {
      "const": "launched"
    },
    "terminal_id": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128
    },
    "pane_id": {
      "anyOf": [
        {
          "type": "string",
          "minLength": 1,
          "maxLength": 128
        },
        {
          "type": "null"
        }
      ]
    },
    "screen_id": {
      "anyOf": [
        {
          "type": "string",
          "minLength": 1,
          "maxLength": 128
        },
        {
          "type": "null"
        }
      ]
    },
    "receipt_family": {
      "enum": [
        "compiler",
        "deck"
      ]
    }
  },
  "required": [
    "rid",
    "state",
    "terminal_id",
    "pane_id",
    "screen_id",
    "receipt_family"
  ],
  "additionalProperties": false
}
```

## Normative domain behavior

### References, constitutions, skills and agents

`reference_get` and `reference_verify` read the bundled `references/MANIFEST.sha256` and the corresponding `references/gold_s1/` or `references/memory_v21/` artifacts; absent or changed pins fail `hash_mismatch`. Both references must be verified before genesis. The GOLD registry contains D1–D8, L1–L8, the source-verified gates from G-PACK through G-MEM; the complete gate-id list is AUSENTE from this pack and must be read from the pinned artifact, never invented. The registry must contain exactly 13 source-verified gates [CITED], I1–I28 and A1–A35, each with id, section and text. Reference publication uses scrubbed extracts and a rule registry; full private sources are not copied.

[K0 decision] Agent records use the explicit fields in `agent.schema.json`; the concept’s complete field listing is AUSENTE from the supplied pack. Constitution compilation takes verified references, workflow, language, skill pins and overlay ids. Overlay ids must resolve in bundled data; unknown, contradictory or authority-expanding overlays fail `bad_args` or `conflict`. Compilation is deterministic LF text with a final newline, no clock, and resolvable `[GOLD-S1/PM-1001.1/<id>; §<section>]` citations. Roles never gain write authority through composition; non-Python historical gate legs are excluded. `agent_version = sha256(canonical({constitution_sha256,skills,memory_gen}))`, with skills sorted by skill_id then hash.

Skill packages are sorted relative paths plus UTF-8 contents, hashed as canonical JSON of the `files` array (LF contents are preserved, not rewritten). Exactly one `SKILL.md` is required. Duplicate paths, escapes, symlinks, packages over 1048576 bytes and missing pins fail `bad_args` or `hash_mismatch`. Repeated content under the same operation replays; changed content under that operation fails `bad_op`. A distinct operation may publish a new hash for the same skill id. Retirement preserves historical resolution. Missing skills/units have no dedicated error in the fixed vocabulary and return `bad_args`.

Defaults: skill_list.include_retired=false; agent_list.include_retired=false; agent_list.limit=100; agent_brief.memory_arm=own; lineage_tree.include_retired=true; memory_route.limit=10; cursor limits=100, after=0, wait_ms=0; overlays and optional evidence=[]; child display_name inherits its parent’s display_name. Agent and bench lists sort lexically by id with exclusive `after` and null `next_after` at the end. An explicit status=retired overrides the default retirement filter. Public names can contain up to 128 characters; control names must follow the separate operability byte bound.

### Memory and run close

`mem_unit.schema.json` closes all seven kind bodies. Only operator ruling may write level 1; every tool attempt fails `forbidden_level`. Level 2 always needs at least one hash-valid receipt, and only active public/internal level-2 lesson or negative units, or promoted workflows, are inheritable. No level 1, level 3, episode, decision, open_item, private unit or foreign-project ruling is inherited. Own briefs may use active public/internal units; private units are excluded from briefs, routing and inheritance. Explicit memory_get/history retain same-user inspection access. Unit bytes, receipt checks, actor/run identity, scope, supersession symmetry and acyclicity are checked before append. A replacement names its predecessors in `supersedes`; the fold establishes their reciprocal superseded_by/status at the same event. Conflicting multiple replacements fail `conflict`.

`memory_gen` changes only for ruling, lesson, negative or workflow changes affecting the brief. Episodes never increment it. Projection generations and old files are immutable after CURRENT flips. Projection rebuild from the ledger produces identical bytes. Static entry content is bounded before accepting a write; insufficient byte or verified token capacity gives `memory_debt` with cuts in detail and appends nothing. `memory_route` ranks casefolded term coverage descending, then unit id ascending, within scope; no match returns units=[] and answer="NOT IN MEMORY". No LLM or embedding is required.

[K0 decision] Bootcheck failure uses the fixed tool error code `bad_op` and detail prefixed `E_BOOTCHECK`; missing observed fields are `bad_args` with the same diagnostic prefix. A successful bootcheck returns passed=true/code=OK only after comparing all observed values and evidence; SKIP is never a result.

run_open freezes version, seat, task, parents_context and memory_arm. `none` removes recalled context, `own` includes the agent’s non-inherited eligible context, and `inherited` includes the same own context plus eligible inherited context, so the own/inherited comparison isolates the added hereditary context [K0 decision]. The arm never waives mandatory memory writes on task close. Only the run’s agent may beat or close it. run_close accepts no client-computed gate or memory receipt list: it finds same-agent active nonprivate valid episodes for that run with lamport greater than run.open; checks schema, level, receipts and privacy; requires a post-open same-run lesson for an error/HOLD/red outcome or repair_loops>0, and a negative for HOLD/red. A failed task can close with valid failure memory. Missing episode gives `memory_required`; missing lesson/negative or invalid required memory gives `memory_debt`. A successful task lacking memory remains open. Retirement and run close are serialized under the same lock; retired agents cannot start or close runs. Exact retries replay before checking current state.

### Arena, credit, breeding and promotion

BenchDeclared is `bench_declared.schema.json`. Agents[0] is baseline, agents[1] candidate; `p0<p1` is a runtime constraint. p0/p1/alpha/beta are strictly between zero and one. `paired` compares both agents on matched task/seat/arm; `crossed` executes the declared agent × seat × arm cells. Bank manifest and split membership are verified before any task. Select never consumes held-out tasks. All arms use the same declared task order. A declaration is immutable; changing it after any result fails `bad_op`, and no run may precede bench.declared (`rule_not_declared`).

[K0 decision] correctness_first maps ADMIT/green to correctness=1, other outcomes to 0; correctness precedes cost. Gain is candidate mean correctness minus baseline mean correctness. Credit requires gain strictly greater than both baseline population standard deviation and minimum_gain; unknown costs never break ties. Repeats of a task do not add independent evidence. Paired ties add no SPRT evidence. A win adds log(p1/p0); a loss adds log((1-p1)/(1-p0)); upper threshold=log((1-beta)/alpha), lower=log(beta/(1-alpha)). Thresholds are tested before cap termination; hitting the distinct-task cap without crossing gives inconclusive. `not_superior` is the lower-threshold decision. Rewards use candidate correctness minus baseline correctness.

bench_run uses the bank’s scripted fake runner or an explicit argv command without a shell. Timeouts record an error run through the failure-memory closing gate; infrastructure inability to produce valid failure memory gives memory_debt, leaving the run open. The fake runner uses seed and injected virtual clock. Compound benchmark suboperations use deterministic operation identities and replay; no lock is held during command execution. bench_verdict records its decision, never changes the declaration, and cannot fabricate missing paired cells.

Clone, distill, cross, mutate and specialize record accepted and rejected units with source hashes and inherited_from provenance. Clone copies constitution, skills and memory_gen version inputs while filtering inheritable units; birth itself does not increment a captured parent generation counter. New non-clone branches start memory_gen at the count of accepted brief-affecting units [K0 decision]. Child generation=max(parent generations)+1. [K0 decision] Cross requires identical workflows; languages are compatible only when equal or one is general, and the child takes the non-general language (or general if both are general). Contradictory concrete languages fail bad_args. Parent order is preserved in the birth record and the first parent supplies the default child display name. Conflicting overlapping claims name both unit ids in `conflict`. Mutate changes exactly one skill pin or rule and never authority rules I20–I22; rule diff is recoverable by comparing parent/child constitution artifacts. Specialize retains general units and matching target-language units and rejects other language scopes. Parents and source memory stay immutable.

Promotion is folded, never set through an arbitrary status tool. Draft→shadow requires a completed select verdict superior, nonnegative minimum per-task reward and credited aggregate win. Shadow→promoted requires the declaration’s n_shadow_runs clean post-shadow runs and a separate held-out confirm benchmark whose bank tasks did not participate in selection. The benchmark must include the exact candidate version and seat being promoted; inferred unmeasured fitness is forbidden. Three consecutive error/HOLD/red outcomes retire the agent through the deterministic fold trigger [CITED: strategy]; no extra event is fabricated by a read. Explicit promotion/retire writes agent.status.

### Journal, cursors and export

Only `ledger/main/events.jsonl` is authoritative. Agent files, memory generations, scorecards and tree are folds. Every event matches `event.schema.json`. [K0 decision] payload names `record`, `unit`, `inherited_units` and `rejected_units` are explicit schema wrappers. agent.born also stores `{constitution:{text,overlays,rule_ids}}`; skill.published stores its canonical `files` array. These immutable bytes make rebuild possible after deleting projections. Their hashes must match the record/pin, and rule_ids must match parsed constitution citations. A kind-specific validator executes with the complete committed prefix under the exclusive ledger lock before append. Rejection appends no bytes. A 1.0-second lock timeout [CITED: seed locking] gives `busy`. fsync failure truncates back to the prior durable boundary; a failed rollback is `internal` and blocks subsequent mutation until verification succeeds. Complete malformed lines or changed history are never silently skipped. A torn final line is reported and ignored for reads; the next locked append truncates only that uncommitted suffix.

[K0 decision] event.sha256 hashes canonical(event without sha256), excluding LF. event.prev_sha256 hashes the complete preceding persisted line including LF; the genesis predecessor is 64 zero characters. Therefore predecessor hashes generally differ from the preceding event’s sha256 field. Verification checks both digests, raw canonical bytes, sequential Lamport order, unique event ids and operation replay consistency. Deletion, reordering or one-byte tamper fails with a relative file and line coordinate.

Idempotency is `(agent,op_id)` plus request_sha256, with canonical validated tool name and effective args excluding op_id and expected_head (defaults inserted before hashing). Changed tool/content fails bad_op. The same op_id on an exact replay yields the original wrapped data and commit prefix; no replay flag or fresh timestamp is added. Results are reconstructed from the original event prefix, never from mutable projections. For single-event transactions the journal owns event ids/timestamps; validators may not write files or dispatch nested calls. Multi-step benchmark operations are explicit deterministic suboperations, not an implicit multi-event transaction.

Cursor `after` is an exclusive Lamport cursor. If after>head, return events=[],next_after=0,has_more=false,resync=true. Filters advance next_after over scanned committed events (including nonmatching records); has_more indicates unscanned events. Empty ledger has a measured empty prefix head=0; an unreadable ledger is internal, never empty. wait_ms waits for head advancement up to the bound and then returns a fresh cursor. The library verifier returns valid=false/issues for structural or projection failures; ledger_verify converts that into hash_mismatch with a bounded relative-coordinate diagnostic (CLI exit 3). Its successful data always has valid=true [K0 decision]. Unchanged torn-tail warnings are reported but do not assert history corruption.

ledger_export out must be beneath the runtime exports directory, relative to home, with no symlink at any component. It writes the full ledger, rebuilt projections and a relative-path SHA manifest; scorecards are grouped by (agent,seat,memory_arm). Unknown costs increment unknown_costs and are excluded from means; an entirely unknown group mean is null. No scorecard writer tool exists.

## CLI

Entry points are `python3 -m lineage` and `bin/lineage`. Global `--home` precedes the verb; resolution is explicit --home, then nonempty LINEAGE_HOME, then the user-home `.lineage` directory. stdout contains only canonical result JSON for machine verbs; diagnostics go to stderr. No legacy read verb or exit 4 exists.

| Verb | Options and result |
|---|---|
| tools | No args; JSON array of the registry descriptors |
| call <tool> --json <object> | Strict object; emit dispatch wrapper or tool error |
| export --out <dir> | Same args/result as ledger_export; output stays beneath home exports |
| mcp | Line-delimited JSON-RPC on stdio |
| json | One family envelope read to EOF, one family receipt plus LF emitted |
| drain --endpoint <name> [--poll-ms N] | Endpoint config is mandatory; poll-ms integer 1..60000, default 25 [K0 decision] |
| serve [--port N] [--fixtures DIR] | Loopback only; port integer 0..65535, default 0 (ephemeral) [K0 decision]; startup JSON to stderr includes port; process token is never logged |
| verify | Same verification report as ledger_verify; invalid report exits 3 |
| operator ruling --agent <id> --quote-file <file> | Only level-1 writer; quote is read locally, hashed and preserved in the ruling evidence; required operator assertion is held out of tool args. [K0 decision] Generates a ruling-only operation id from agent id and quote hash and a stable unit id; retries replay. Targets workflow/language come from the agent; statement and how_to_apply are the exact quote. |

| Exit | Meaning |
|---|---|
| 0 | Success, including a completed failed task with valid memory |
| 2 | Argument/JSON/schema/discovery/configuration error; missing endpoint, bridge config, malformed input; second mailbox consumer |
| 3 | Domain/internal/I/O failure, rejected closing gate, hash failure or invalid verification report |

Configuration refusals keep code=bad_args and exit 2. Domain bad_op/conflict/memory_debt etc exit 3. No command consumes a model or downloads dependencies.

## MCP stdio

Protocol `2024-11-05` [CITED: seed MCP]; serverInfo.name=`lineage`, version=`1.0.0` [K0 decision]. Framing is one UTF-8 JSON-RPC object per LF; no Content-Length headers. Requests require jsonrpc=2.0, id string/integer/null and method string; arrays/batches are refused. Notifications have no response; notifications/initialized is accepted.

| Method | Parameters / result |
|---|---|
| initialize | Standard protocolVersion/capabilities/clientInfo; advertises tools/resources/prompts; incompatible protocol fails -32602 |
| ping | Empty object → {} |
| tools/list | Empty object → {tools:[{name,description,inputSchema}]} in lexical name order |
| tools/call | {name,arguments:object} → {content:[{type:text,text:<serialized dispatch result>}],isError:boolean} |
| resources/list | Empty object → the two resources below |
| resources/read | {uri} → {contents:[{uri,mimeType:text/markdown,text}]} |
| resources/templates/list | Empty object → {resourceTemplates:[]} |
| prompts/list | Empty object → the three prompts below and their arguments |
| prompts/get | {name,arguments?:object} → {description,messages:[{role:user,content:{type:text,text}}]}; prompts render guidance only and never execute tools |

| Resource | File |
|---|---|
| lineage://contract | docs/CONTRACT.md; descriptor name=Lineage contract, mimeType=text/markdown [K0 decision] |
| lineage://guide/headless | docs/HEADLESS.md; descriptor name=Headless guide, mimeType=text/markdown [K0 decision] |

| Prompt | Required / optional string arguments [K0 decision] |
|---|---|
| create_agent_from_spec | spec required (1..16000 characters), agent_id optional |
| breed_from_best | parent_id and child_id required, op optional (clone/distill/mutate/specialize) |
| run_benchmark | bench_id required |

RPC -32700=parse/UTF-8 failure; -32600=invalid JSON-RPC shape; -32601=unknown method; -32602=invalid params, unknown tool/resource/prompt or tool argument schema violation; -32603=uncaught server failure [CITED: seed error path]. A dispatched domain error is a successful JSON-RPC result containing the tool error with isError=true, never a second RPC error. Only protocol validation uses RPC errors; all successful extension data stays under untrusted.

## HTTP and local UI host

The server binds only 127.0.0.1. Each process generates a cryptographically random session token; bootstrap injects it into the served index document as `<meta name="lineage-session-token" content="…">` [K0 decision], accessible only through the loopback page. Static assets never embed a checked-in token; token-bearing HTML and API responses use Cache-Control:no-store. Every route serving index.html performs the same injection, including a direct index.html request. All requests validate Host against the exact bound authority; foreign Host fails 403. No CORS grants are emitted. Any supplied Origin must exactly equal the served loopback origin. Mutating POST calls additionally require Origin, Content-Type:application/json, and X-Lineage-Session matching the process token. Read-only POST calls may omit Origin/token but still fail a supplied foreign Origin. Export and bridge publication are treated as mutating HTTP operations despite export not appending an event.

| Route | Body/query and result |
|---|---|
| GET / | ui/dist/index.html; missing build returns 503 named error |
| GET /<asset> | Static ui/dist only; decode once, confine path, refuse symlink/traversal with 404 |
| GET /api/health | {ok:true,protocol:lineage.family/1,head:int,fixtures:bool}; unavailable journal gives 503 |
| GET /api/tools | {tools:[registry descriptors]} |
| POST /api/call | Strict {tool:string,args:object}; JSON dispatch wrapper/error |
| GET /api/events?after=N&wait_ms=M | after default 0, wait_ms default 0 (0..30000); equivalent ledger_events with limit=100 |

| Status | Meaning |
|---|---|
| 200 | Successful route/tool/cursor, including resync=true |
| 400 | Malformed JSON/query/args, unknown tool, missing bridge configuration |
| 403 | Host/Origin/token refusal, forbidden_level, fixture_readonly |
| 404 | Unknown route/static file; no_agent/no_run/no_benchmark domain lookup |
| 405 | Unsupported HTTP method; include Allow |
| 409 | bad_op/stale_rev/conflict/run_closed/memory_required/memory_debt/not_inheritable/rule_not_declared/heldout_forbidden/seat_not_allowed/hash_mismatch |
| 413 | Oversize body |
| 415 | Non-JSON POST content type |
| 500 | internal or unhandled I/O |
| 503 | busy/unavailable runtime or missing UI build |
| 504 | timeout |

Fixture mode reads only deterministic fixture data and refuses all journal/external mutations and exports with fixture_readonly. It exposes no token-bearing capability that can mutate the real home. UI routes are #/agents, #/agents/<agent_id>, #/lineage, #/arena, #/arena/<bench_id>, #/ledger. The selector/keyboard/O1–O14 contract belongs to docs/OPERABILITY.md; K0a does not assign selector names. UI mutations call documented tools and verify ledger postconditions.

## JSON lane

Requests and receipts match family_envelope.schema.json and family_receipt.schema.json. Required request fields are schema,id,source,target,kind,agent,payload; optional run_id,correlation_id,after. schema is lineage.family/1. kind=capabilities requires payload={} and no after; events.read requires after and payload matching ledger_events filters except after; call requires payload={tool,args} and no after. The id invalid0 is reserved for malformed-input receipts and is refused on every request. A non-call run_id is correlation context; on run-scoped calls it must match the effective args.run_id if present.

Operation identity is `lin-` + first 44 hex of sha256(UTF-8(source + NUL + target + NUL + id)). The envelope’s agent is injected into tool args; supplied payload agent/op_id fields are rejected, not silently overwritten. Journal mutations receive computed op_id; external commands derive their remote request id deterministically. Allowlist checks run before retained-result lookup and before dispatch. stdio uses the same recipient-owned endpoint config as drain; target must resolve to an existing config and source/tools must be admitted [K0 decision]. Read envelopes also obey source authorization.

capabilities returns {untrusted:{protocol:lineage.family/1,kinds:[capabilities,events.read,call],tools:[allowed descriptors],health:ready}}. events.read returns the regular wrapped cursor. call returns dispatch unchanged. Receipt is {schema:lineage.family/1,id,result,correlation_id?}; a success result has exactly untrusted, an error has exactly ok=false/code/detail?. Malformed input with a recoverable valid id returns bad_args in a receipt. [K0 decision] If no valid id can be recovered, stdio uses the reserved valid receipt id `invalid0` and exits 2; no request with this id is admitted for mutation. One-shot produces exactly one JSON receipt, diagnostics on stderr.

Endpoint config is exactly {endpoint:Endpoint,sources:Endpoint[],tools:ToolName[]}; absent/empty sources or tools authorize nothing. Layout is family/<endpoint>/{config.json,consumer.lock,spool,state,dedup}. A request name must match its id; output name is <id>.result.json. All persistent request/state/result publications use same-directory temporary, fsync, atomic rename, and directory fsync. The exclusive consumer lock has no stale takeover; a second consumer exits 2. No symlinks are followed; unsafe requests are quarantined with no dispatch.

Retained dedup state is {identity,digest,op_id,phase:pending|complete,result?}; digest binds canonical envelope bytes. Redelivery with changed payload/source/actor fails bad_op. Recovering a pending journal mutation queries (agent,op_id) and reconstructs its original result instead of appending again. Receipt publication alone never proves a mutation; a matching journal witness is required. External acknowledgements are tracked separately from application completion. Endpoint permissions are rechecked on every delivery/replay.

## OpenFresnel bridge

Configuration precedence is explicit commands_dir, then LINEAGE_OPENFRESNEL_COMMANDS_DIR, then paths.commands_dir from an explicitly supplied contract_file. No workspace metadata directory or host path is assumed. An explicitly invalid higher-priority source fails instead of falling through. probe publishes capabilities; spawn publishes spawn_terminal to launch the current Python executable with `-m lineage json` or `-m lineage drain --endpoint <name>`; argv is an array, never shell text. json mode requires envelope and forbids endpoint; drain mode requires endpoint and forbids envelope. The bridge verifies that the commands directory is real and not symlinked. Missing configuration is bad_args/configuration (CLI exit 2).

Command publication is <rid>.tmp→<rid>.json; result is <rid>.result.json. [K0 decision] rid is the first 32 lowercase hex characters of sha256(canonical({agent,op_id})), giving a valid Id. Timeout defaults to 20000 ms [CITED: supplied channel contract]; retry preserves rid. Compiler receipts use status=ok|accepted|error; Deck receipts use ok and api_version=2 [CITED]. They are parsed separately and must echo the request identity and operation. Error statuses map to bad_args/conflict/internal according to their documented payload; unavailable/unrecognized receipt shapes fail internal. probe requires capabilities data; spawn requires terminal identity and returns state=launched only. Launch acknowledgement does not create a run, close memory, prove a ledger mutation or claim live interoperability. Fake-consumer coverage is required; live interoperability and headless terminal parity remain AUSENTE.

[K0 decision] An agent is an entity; a seat is its model/effort/mode tool. No benchmark or scorecard collapses those identities. New born records include reference pins directly or through verified parents; no artifact inherits model weights.

## Schema files and semantic checks

| File | Record |
|---|---|
| `schemas/event.schema.json` | `lineage.event/v1` |
| `schemas/agent.schema.json` | `lineage.agent/v1` |
| `schemas/run.schema.json` | `lineage.run/v1` |
| `schemas/mem_unit.schema.json` | `lineage.mem.unit/v1` |
| `schemas/family_envelope.schema.json` | `lineage.family/1 request` |
| `schemas/family_receipt.schema.json` | `lineage.family/1 receipt` |
| `schemas/bench_declared.schema.json` | `lineage.bench.declared/v1` |
| `schemas/tool_error.schema.json` | `tool error` |

All schemas declare draft 2020-12 and close shaped objects with additionalProperties=false. Relative $ref values resolve only among these bundled schemas; network schema resolution is forbidden. Recursive descriptor/JSON-value maps in the receipt schema are explicitly patternProperties-bounded, with additionalProperties=false; arbitrary result keys are not accepted. The mini-validator subset and the semantic checks are frozen in INTERFACES.md. JSON syntax validation is necessary but does not establish implemented domain behavior.

Runtime checks supplement JSON Schema: byte limits, ownership, reference uniqueness by id, model/seat admission, reference/source existence, digest correctness, timestamps ordered open≤close, workflow stats successes≤runs, p0<p1, supersession graph integrity, no foreign rulings, scope conflicts, SPRT credit, promotion and receipt-backed close. Unknown evidence is not zero and never passes a gate.

All mandates in this contract are scoped to the supplied campaign corpus and the K0 seed.

## Amendment A-K0 (orchestrator, after cross-family review; binding, wins over earlier text)

1. **Token counting.** v1 has no tokenizer. Every entry point injects `Services.token_count = None`. Budgets are enforced in UTF-8 bytes only (static entry 6,000 B). A missing token counter never causes `memory_debt`, never blocks `memory_put` or `run_close`; reports state the token ceiling as "not measured".
2. **Brief bytes.** `brief_head_sha256 = sha256(brief.build(agent, units, memory_arm="own"))`. `brief.build` output: UTF-8, LF line ends, final newline, no timestamps; sections in this order: identity (agent_id, workflow, language, agent_version inputs), constitution sha256 and rule ids, skills sorted by `id`, then eligible memory units (status active, level 1 or 2, privacy not private, kinds ruling/lesson/negative/workflow) sorted by `(kind, id)`. Identical inputs give identical bytes.
3. **Benchmark identity.** The candidate identity of a benchmark is the agent version recorded in `bench.declared` (`constitution_sha256`, `skills`, `memory_gen` at declaration). Memory written by benchmark runs (required by the close gate) is recorded normally and may raise `memory_gen`; it does not invalidate the benchmark. `agent_promote` matches the declared snapshot, not the current version.
4. **Promotion seat (P1).** A benchmark used for promotion declares exactly one seat; otherwise `agent_promote` returns `bad_args`. The `agent.status` event records that seat; the agent fold exposes it as `promoted_seat`.
5. **Evidence root.** `Evidence.path` is relative to the Lineage home and must resolve inside it after symlink resolution, excluding `ledger/` and `family/` (refused with `bad_args`). `operator ruling --quote-file` takes any readable file; Lineage stores a copy under `home/rulings/<sha256>.txt` and records the sha256.
6. **Mutate and cross.** `compile_constitution(..., rule_overrides=None)` accepts `{rule_id: "add"|"remove"}`; the agent record carries `rule_overrides` (optional). `agent_cross`: `allowed_seats` = intersection of the parents' (empty → `bad_args`); `skills` = union by id (same id with different sha256 → `conflict`); `rule_overrides` = union (contradictory values → `conflict`).
7. **Crossed and repeated cells.** Per bank task, each agent's score is the mean correctness over all its cells (seat × memory arm × seed) for that task. Per-task reward = candidate mean − baseline mean: win if > 0, loss if < 0, tie if = 0. One task contributes at most one SPRT observation.
8. **Actor binding and op_id.** With `ctx.authority == "tool"`, `memory_put` requires `ctx.actor == agent_id` (else `bad_args`, detail `actor_mismatch`); the same holds for `run_open`, `run_beat` and `run_close`. The JSON lane computes `op_id` for every mutating tool, `effect="journal"` and `effect="external"` alike.
9. **Integrated code is the API authority (A-K0-9).** For modules already integrated, the integrated source is authoritative for its own API where it differs from docs/INTERFACES.md; later units adapt and record the deviation. docs/INTERFACES.md is reconciled to the integrated code at the end of the night.
