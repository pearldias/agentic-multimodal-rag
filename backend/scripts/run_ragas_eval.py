"""CLI script to run offline Ragas evaluation on the RAG pipeline.

Evaluates:
- Faithfulness
- Answer Relevancy
- Context Precision (when reference is present)
- Context Recall (when reference is present)

Saves JSON and CSV reports to data/evaluation/reports/.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.evaluation import EvaluationSample, RagasEvaluator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_ragas_eval")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run offline Ragas evaluation against the existing RAG pipeline."
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(settings.DATA_DIR / "evaluation" / "benchmark_dataset.json"),
        help="Path to JSON benchmark dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(settings.DATA_DIR / "evaluation" / "reports"),
        help="Directory to save evaluation reports (JSON and CSV).",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=settings.RERANK_TOP_K,
        help="Top-k reranked documents to use for context generation.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of samples to evaluate (useful for smoke tests).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)

    print("=" * 70)
    print(" RAGAS EVALUATION RUNNER")
    print("=" * 70)
    print(f"Dataset path : {dataset_path}")
    print(f"Output dir   : {output_dir}")
    print(f"Rerank top-k : {args.k}")
    print(f"Sample limit : {args.limit or 'All'}")
    print("-" * 70)

    if not dataset_path.exists():
        logger.error("Dataset file not found: %s", dataset_path)
        return 1

    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        logger.error("Failed to load dataset: %s", e)
        return 1

    if not isinstance(raw_data, list):
        logger.error("Dataset must be a JSON array of objects.")
        return 1

    samples: list[EvaluationSample] = []
    for item in raw_data:
        q = item.get("question")
        if q and q.strip():
            samples.append(
                EvaluationSample(
                    question=q.strip(),
                    reference=item.get("reference"),
                    id=item.get("id"),
                )
            )

    if not samples:
        logger.error("No valid questions found in dataset.")
        return 1

    if args.limit and args.limit > 0:
        samples = samples[: args.limit]
        print(f"Evaluating first {len(samples)} sample(s) due to --limit flag.")
    else:
        print(f"Found {len(samples)} sample(s) to evaluate.")

    with_ref_count = sum(1 for s in samples if s.reference)
    without_ref_count = len(samples) - with_ref_count
    print(f"- Samples with ground-truth reference (4 metrics): {with_ref_count}")
    print(f"- Samples without reference (2 metrics)          : {without_ref_count}")
    print("-" * 70)

    evaluator = RagasEvaluator()
    report = evaluator.evaluate_samples(
        samples=samples,
        k=args.k,
        output_dir=output_dir,
    )

    print("\n" + "=" * 70)
    print(" EVALUATION RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total samples evaluated : {report.total_samples}")
    print(f"With reference (4 metrics): {report.samples_with_reference}")
    print(f"Without reference (2 met.): {report.samples_without_reference}")
    print("-" * 70)
    print("Aggregate Mean Scores:")
    for metric, score in report.mean_scores.items():
        print(f"  • {metric.replace('_', ' ').title():<22} : {score:.4f}")
    print("-" * 70)

    print("\nPer-sample Breakdown:")
    for idx, sample in enumerate(report.sample_results, start=1):
        sid = sample.get("id") or f"Sample {idx}"
        q = sample.get("question", "")[:60]
        f_score = sample.get("faithfulness")
        ar_score = sample.get("answer_relevancy")
        cp_score = sample.get("context_precision")
        mcp_score = sample.get("multihop_context_precision")
        cr_score = sample.get("context_recall")

        f_str = f"{f_score:.2f}" if f_score is not None else " N/A"
        ar_str = f"{ar_score:.2f}" if ar_score is not None else " N/A"
        cp_str = f"{cp_score:.2f}" if cp_score is not None else " N/A"
        mcp_str = f"{mcp_score:.2f}" if mcp_score is not None else " N/A"
        cr_str = f"{cr_score:.2f}" if cr_score is not None else " N/A"

        print(f"[{sid}] {q}...")
        print(f"      Faithfulness: {f_str} | Answer Rel: {ar_str} | Ctx Prec (atomic): {cp_str} | Multi-Hop Ctx Prec: {mcp_str} | Context Rec: {cr_str}")

    print("\n" + "=" * 70)
    print("Saved Reports:")
    print(f"  • JSON : {report.report_json_path}")
    print(f"  • CSV  : {report.report_csv_path}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
