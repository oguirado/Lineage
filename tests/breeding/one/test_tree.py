"""Tree gates over real journal prefixes containing explicitly pure fixtures."""
from dataclasses import replace
from copy import deepcopy

from lineage.domain.tree import tree
from .helpers import OracleCase, agent, canonical


class TreeOracle(OracleCase):
    def graph(self):
        records = [
            agent("root-one", memory_gen=0), agent("root-two", memory_gen=0),
            agent("child-one", parents=["root-one"], op="clone", generation=1),
            agent("child-two", parents=["root-one"], op="distill", generation=1),
            agent("cross-one", parents=["child-two", "root-two"], op="cross", generation=2),
            agent("mutant-one", parents=["child-one"], op="mutate", generation=2),
            agent("special-one", parents=["cross-one"], op="specialize", generation=3),
        ]
        for record in records:
            self.seed(record)
        return records

    def expected(self, records):
        return sorted([{"agent_id": r["agent_id"], "parents": r["parents"],
                        "generation": r["generation"], "op": r["born"]["op"],
                        "status": r["status"]} for r in records],
                      key=lambda n: (n["generation"], n["agent_id"]))

    def test_a24_complete_tree_all_operators_exact_nodes_and_consistent_head(self):
        """Gate: full ordered relation data; contrast: drawing-only/invented edges."""
        records = self.graph()
        result = tree(ctx=self.ctx)
        self.assertEqual(result, {"nodes": self.expected(records), "head": len(records)})
        self.assertEqual(set(result), {"nodes", "head"})
        self.assertEqual(len({node["op"] for node in result["nodes"]}), 6)

    def test_a24_independent_root_insertion_order_cannot_change_nodes(self):
        roots = [agent("root-two"), agent("root-one")]
        for record in roots:
            self.seed(record)
        first = tree(ctx=self.ctx)
        other = self.base / "other-home"
        other.mkdir()
        self.home = other
        self.ctx = replace(self.ctx, home=other)
        for record in reversed(roots):
            self.seed(record)
        self.assertEqual(tree(ctx=self.ctx), first)

    def test_a25_root_descendant_closure_preserves_an_outside_parent(self):
        records = self.graph()
        result = tree(root_id="child-two", ctx=self.ctx)
        expected = [r for r in records if r["agent_id"] in {"child-two", "cross-one", "special-one"}]
        self.assertEqual(result, {"nodes": self.expected(expected), "head": len(records)})
        self.assertEqual(result["nodes"][1]["parents"], ["child-two", "root-two"])

    def test_a25_unknown_root_is_no_agent(self):
        self.graph()
        self.refused("no_agent", lambda: tree(root_id="missing-one", ctx=self.ctx))

    def test_a25_known_empty_journal_has_empty_nodes_and_zero_head(self):
        before = sorted(self.home.rglob("*"))
        self.assertEqual(tree(ctx=self.ctx), {"nodes": [], "head": 0})
        self.assertEqual(sorted(self.home.rglob("*")), before, "Tree read created a projection")

    def test_a26_retired_intermediates_are_traversed_before_filtering(self):
        """Gate: only retired nodes disappear; contrast: prune their descendants."""
        records = [agent("root-one", status="retired"),
                   agent("middle-one", parents=["root-one"], op="clone", generation=1, status="retired"),
                   agent("leaf-one", parents=["middle-one"], op="distill", generation=2)]
        for record in records:
            self.seed(record)
        self.assertEqual(tree(ctx=self.ctx), tree(include_retired=True, ctx=self.ctx))
        self.assertEqual(tree(root_id="root-one", include_retired=False, ctx=self.ctx),
                         {"nodes": self.expected(records[-1:]), "head": 3})

    def test_a26_retired_leaf_as_hidden_root_is_empty_success(self):
        self.seed(agent("retired-one", status="retired"))
        self.assertEqual(tree(root_id="retired-one", include_retired=False, ctx=self.ctx),
                         {"nodes": [], "head": 1})

    def test_a27_missing_parent_is_internal_without_graph_repair(self):
        self.seed(agent("child-one", parents=["missing-one"], op="clone", generation=1))
        self.refused("internal", lambda: tree(ctx=self.ctx))

    def test_a27_cycle_is_internal_without_synthetic_root(self):
        self.seed(agent("child-one", parents=["child-two"], op="clone", generation=1))
        self.seed(agent("child-two", parents=["child-one"], op="clone", generation=2))
        self.refused("internal", lambda: tree(ctx=self.ctx))

    def test_a27_self_parent_is_internal(self):
        self.seed(agent("child-one", parents=["child-one"], op="clone", generation=1))
        self.refused("internal", lambda: tree(ctx=self.ctx))

    def test_a27_duplicate_parents_are_internal(self):
        self.seed(agent("root-one"))
        self.seed(agent("child-one", parents=["root-one", "root-one"], op="cross", generation=1))
        self.refused("internal", lambda: tree(ctx=self.ctx))

    def test_a27_inconsistent_generation_is_internal(self):
        self.seed(agent("root-one"))
        self.seed(agent("child-one", parents=["root-one"], op="clone", generation=7))
        self.refused("internal", lambda: tree(ctx=self.ctx))

    def test_a27_unavailable_authority_is_not_empty_success(self):
        ledger = self.home / "ledger" / "main"
        ledger.mkdir(parents=True)
        (ledger / "events.jsonl").mkdir()
        from lineage.core.errors import LineageError
        from lineage.core.app import ToolError
        with self.assertRaises((LineageError, ToolError)) as caught:
            tree(ctx=self.ctx)
        self.assertEqual(caught.exception.code, "internal")
        self.assertTrue((ledger / "events.jsonl").is_dir())

    def test_a27_hash_corruption_preserves_shared_hash_mismatch(self):
        self.seed(agent("root-one"))
        path = self.home / "ledger" / "main" / "events.jsonl"
        path.write_bytes(path.read_bytes().replace(b'Fixture parent', b'Fixture tamper', 1))
        self.refused("hash_mismatch", lambda: tree(ctx=self.ctx))

    def test_a28_materialized_tree_tamper_has_no_authority(self):
        records = self.graph()
        original = tree(ctx=self.ctx)
        disposable = self.home / "tree.json"
        disposable.write_bytes(canonical({"nodes": [{"agent_id": "forged-one"}], "head": 999}))
        self.assertEqual(tree(ctx=self.ctx), original)
        disposable.unlink()
        self.assertEqual(tree(ctx=self.ctx), {"nodes": self.expected(records), "head": len(records)})

    def test_a34_read_is_observational_and_return_values_do_not_alias(self):
        self.graph()
        before = self.ledger_bytes()
        result = tree(ctx=self.ctx)
        expected = deepcopy(result)
        result["nodes"][0]["parents"].append("fake-parent")
        self.assertEqual(tree(ctx=self.ctx), expected)
        self.assertEqual(self.ledger_bytes(), before)


def _bad_generation(self):
    self.seed(agent("root-one", generation=True))
    self.refused("internal", lambda: tree(ctx=self.ctx))
TreeOracle.test_a27_boolean_generation_is_not_an_integer = _bad_generation
