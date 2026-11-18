"""Evaluate the code router on DEV card questions or a separate TEST bank."""

import argparse
import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import route as RT


def test_questions(path, routes):
    by_path = {route["path"]: ident for ident, route in routes.items()}
    with path.open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                query, answers = row["q"], row["answer"]
                if isinstance(answers, str):
                    answers = [answers]
                if (not isinstance(query, str) or not query.strip()
                        or not isinstance(answers, list) or not answers
                        or any(not isinstance(answer, str) for answer in answers)):
                    raise ValueError("expected q and a nonempty answer")
                gold = {answer if answer in routes else by_path[answer] for answer in answers}
            except (TypeError, KeyError, ValueError) as exc:
                raise ValueError(f"test_questions.jsonl:{number}: {exc}") from exc
            yield query, gold


def evaluate(index, questions):
    results = []
    for query, gold in questions:
        ids = [row[0] for row in RT.rank(index, query, C.K_MAX)["r"]]
        rr = next((1 / rank for rank, ident in enumerate(ids, 1) if ident in gold), 0)
        results.append({
            "q": query, "gold": sorted(gold), "top5": ids[:5], "rr": rr,
            "recall_at_1": len(gold.intersection(ids[:1])) / len(gold),
            "recall_at_5": len(gold.intersection(ids[:5])) / len(gold),
        })
    if not results:
        raise ValueError("evaluation split has no questions")
    means = {key: round(sum(row[key] for row in results) / len(results), 4)
             for key in ("rr", "recall_at_1", "recall_at_5")}
    means["mrr"] = means.pop("rr")
    return {"n": len(results), **means}, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", "--dev-card", action="store_true",
                        help="use the indexed card questions")
    args = parser.parse_args()
    bank = C.HERE / "eval" / "test_questions.jsonl"
    split = "DEV" if args.dev else "TEST"
    if not args.dev and not bank.is_file():
        print(C.dumps({"split": split, "status": "ABSENT", "path": "route/eval/test_questions.jsonl"}))
        return 4
    try:
        with C.output_lock():
            routes = C.load(C.HERE / "nodes" / "routes.json")
            if args.dev:
                questions = ((q, {ident}) for ident, route in sorted(routes.items())
                             for q in route["questions"])
            else:
                questions = test_questions(bank, routes)
            index = RT.engine.Index(os.fspath(C.HERE / "index"))
            summary, results = evaluate(index, questions)
    except (RT.engine.IndexError_, OSError, ValueError, KeyError) as exc:
        print(f"E_EVAL: {exc}", file=sys.stderr)
        return 3
    summary.update(split=split, index_sha256=index.ixid)
    print(C.dumps({"summary": summary, "per_query": results}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
