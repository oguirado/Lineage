# Deterministic shell fixtures

`demo.json`, `empty.json` and `hostile.json` follow `schema.json`
(`lineage.ui.fixture/v1`). These are synthetic, read-only UI inputs. They neither
verify a real ledger nor establish benchmark quality or inherited-memory benefit.

Select `?fixture=demo`, `?fixture=empty` or `?fixture=hostile` before the hash route.
For example, `?fixture=demo#/agents`. An unknown or repeated selection fails with
`invalid_config`; service errors never select fixtures automatically.

The version-one baseline requires schema, id, clock_ms, tools, page, results and
panels. Presentation is fixed to `en-GB`, `UTC` and light theme when its optional
locale/timezone/theme fields are omitted. The fixed presentation epoch is
1700000000000 milliseconds [TARGET]. No host clock, random source, network,
storage record or previous theme determines the initial fixture view.

The demo includes every shell panel state, distinct agents with the same display
name, separate seat metadata and explicit null measurements. Empty includes an
authoritative empty cursor and distinct empty/no-match examples. Hostile contains
literal markup, Unicode, long unbroken text, a digest and selector punctuation.
These examples remain passive data, including markup-shaped content.

Only declared exact read arguments return data. Undeclared reads fail `bad_args`;
mutations, exports and external operations fail `fixture_readonly`, including
calls dishonestly marked read-only. Fixture transport never accesses the network
or writes authoritative storage. Readiness requires validated descriptors, a
complete event fold and acknowledged route rendering; an empty confirmed cursor
is distinct from missing evidence. Screen placeholders remain explicitly not built.

The original broader K0 dataset inventory is not an implemented fixture receipt.
Browser geometry, CDP AX, native AT-SPI, frame evidence and persona scores remain
AUSENTE — no inventar. This manifest covers only the supplied shell baseline.
