"""Ragas evaluation module for offline assessment of the RAG pipeline.

Evaluates:
- Faithfulness (factual grounding against retrieved contexts)
- Answer Relevancy (semantic alignment of answer with user question)
- Context Precision (higher ranking of ground-truth relevant chunks, when reference is provided)
- Context Recall (retrieval coverage of ground-truth information, when reference is provided)

Execution is strictly single-pass per question to avoid running retrieval or LLM twice.
Does not touch or interfere with live chatbot endpoints.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from datasets import Dataset
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, Field
from ragas import evaluate
from ragas.embeddings.base import LangchainEmbeddingsWrapper
from ragas.llms.base import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from ragas.metrics.base import (
    MetricOutputType,
    MetricType,
    MetricWithLLM,
    SingleTurnMetric,
)
from ragas.prompt import PydanticPrompt
from ragas.run_config import RunConfig

from backend.app.core.config import settings
from backend.app.services.rag_service import RAGService

logger = logging.getLogger(__name__)


class MultiHopQAC(BaseModel):
    """Input payload for multi-hop chunk evaluation."""

    question: str = Field(..., description="User question")
    context: str = Field(..., description="Retrieved context chunk to evaluate")
    answer: str = Field(..., description="Reference answer")


class ChunkVerification(BaseModel):
    """Output verdict and justification for chunk utility."""

    reason: str = Field(
        ...,
        description="Reason explaining whether the context contains facts/information useful to any part of the answer",
    )
    verdict: int = Field(
        ...,
        description="1 if the chunk contains specific factual information supporting any part of the answer; 0 if irrelevant, merely topical, or redundant without specific evidence",
    )


class MultiHopContextPrecisionPrompt(PydanticPrompt[MultiHopQAC, ChunkVerification]):
    """Prompt for verifying chunk relevance in single-hop and multi-hop questions."""

    name: str = "multihop_context_precision"
    instruction: str = (
        "Given a question, reference answer, and a retrieved context chunk, verify if the context chunk "
        "provides meaningful, factual evidence useful in arriving at the reference answer.\n"
        "Guidelines:\n"
        "1. Questions may be multi-part or multi-hop, requiring complementary information from multiple sources.\n"
        "2. A chunk MUST be marked with verdict 1 if it directly provides specific facts, entities, data, metrics, or "
        "rules that support or contribute to ANY PART of the reference answer, even if other parts of the answer "
        "require information from other chunks.\n"
        "3. Merely topic-adjacent, related background, or redundant chunks that do NOT contain specific factual evidence "
        "needed to support any statement in the reference answer MUST be marked with verdict 0.\n"
        "4. A chunk from the same document or general topic that only discusses tangential policies or background concepts "
        "without providing the specific answers or facts required MUST be marked with verdict 0."
    )
    input_model = MultiHopQAC
    output_model = ChunkVerification
    examples = [
        (
            MultiHopQAC(
                question="What is the capital of France and what is its population?",
                context="Paris is the capital and most populous city of France.",
                answer="The capital of France is Paris and its population is over 2 million.",
            ),
            ChunkVerification(
                reason="The context confirms that Paris is the capital of France, which directly supports the first part of the reference answer, even though it does not provide the exact population figure.",
                verdict=1,
            ),
        ),
        (
            MultiHopQAC(
                question="What is the capital of France and what is its population?",
                context="The city of Paris had an estimated population of 2.1 million residents in 2023.",
                answer="The capital of France is Paris and its population is over 2 million.",
            ),
            ChunkVerification(
                reason="The context provides the population figure of Paris, which directly supports the second part of the reference answer, even though it does not explicitly state that Paris is the capital.",
                verdict=1,
            ),
        ),
        (
            MultiHopQAC(
                question="What is the capital of France and what is its population?",
                context="Lyon is a major city in southeastern France known for its historical and architectural landmarks.",
                answer="The capital of France is Paris and its population is over 2 million.",
            ),
            ChunkVerification(
                reason="The context discusses Lyon and does not contain any information about Paris, the capital of France, or its population.",
                verdict=0,
            ),
        ),
        (
            MultiHopQAC(
                question="What is the notice period for planned vacation leave?",
                context="Employees must notify their manager prior to standard start time when taking unplanned sick leave.",
                answer="Planned leave requests must be submitted at least 14 days in advance.",
            ),
            ChunkVerification(
                reason="The context discusses unplanned sick leave notice procedures, not planned vacation leave advance notice requirements. It does not support the reference answer.",
                verdict=0,
            ),
        ),
        (
            MultiHopQAC(
                question="What major project milestone lands on June 30, 2027 for the GreenPulse initiative?",
                context="McLaren GreenPulse is an enterprise-wide environmental sustainability and energy conservation program started in 2025.",
                answer="The major project milestone scheduled for June 30, 2027, is the Solar Installation.",
            ),
            ChunkVerification(
                reason="Although the context mentions the GreenPulse initiative, it contains only general program background and does not mention any milestones, dates, or the Solar Installation.",
                verdict=0,
            ),
        ),
    ]


@dataclass
class MultiHopContextPrecision(MetricWithLLM, SingleTurnMetric):
    """Evaluates context precision for single-hop and multi-hop queries where complementary

    chunks from multiple documents or sections contribute to a compound reference answer.
    Computes Average Precision (AP) across ranked chunks while identifying and penalizing irrelevant chunks.
    """

    name: str = "multihop_context_precision"
    _required_columns: dict[MetricType, set[str]] = field(
        default_factory=lambda: {
            MetricType.SINGLE_TURN: {
                "user_input",
                "retrieved_contexts",
                "reference",
            }
        }
    )
    output_type: MetricOutputType = MetricOutputType.CONTINUOUS
    prompt: PydanticPrompt = field(default_factory=MultiHopContextPrecisionPrompt)

    @staticmethod
    def calculate_average_precision(verdict_list: Sequence[int | bool]) -> float:
        """Calculate standard Average Precision (AP) for a binary-graded ranked list of chunks.

        Formula:
            AP = sum_{i=1}^K (Precision@i * rel_i) / sum_{i=1}^K rel_i

        Returns 0.0 if no relevant chunks are retrieved or if the list is empty.
        Penalizes lower ranking of relevant chunks and rank inversions.
        """
        if not verdict_list:
            return 0.0
        binary_verdicts = [1 if v else 0 for v in verdict_list]
        denom = sum(binary_verdicts)
        if denom == 0:
            return 0.0
        k = len(binary_verdicts)
        num = sum((sum(binary_verdicts[: i + 1]) / (i + 1)) * binary_verdicts[i] for i in range(k))
        return float(num / denom)

    async def _single_turn_ascore(self, sample: Any, callbacks: Any) -> float:
        # Extract attributes safely from SingleTurnSample or dict
        if isinstance(sample, dict):
            user_input = sample.get("user_input", "")
            retrieved_contexts = sample.get("retrieved_contexts") or []
            reference = sample.get("reference")
        else:
            user_input = getattr(sample, "user_input", "")
            retrieved_contexts = getattr(sample, "retrieved_contexts", [])
            reference = getattr(sample, "reference", None)

        if not retrieved_contexts:
            return 0.0
        if not reference or not str(reference).strip():
            return 0.0

        if self.llm is None:
            raise ValueError("LLM is not configured for MultiHopContextPrecision.")

        verdicts: list[int] = []
        errors_count = 0

        for ctx in retrieved_contexts:
            qac = MultiHopQAC(
                question=user_input,
                context=ctx,
                answer=str(reference),
            )
            try:
                res = await self.prompt.generate_multiple(data=qac, llm=self.llm, callbacks=callbacks)
                if res:
                    v = getattr(res[0], "verdict", None)
                    if v is None and isinstance(res[0], dict):
                        v = res[0].get("verdict")
                    verdicts.append(1 if (v == 1 or v is True) else 0)
                else:
                    verdicts.append(0)
            except Exception as e:
                errors_count += 1
                logger.warning("Error generating verdict for context chunk: %s", e)
                # If an API-level error occurred for all chunks, propagate so Ragas executor can retry/mark NaN
                if errors_count == len(retrieved_contexts):
                    raise e
                verdicts.append(0)

        return self.calculate_average_precision(verdicts)


multihop_context_precision = MultiHopContextPrecision()


@dataclass
class EvaluationSample:
    """Input sample definition for evaluation."""

    question: str
    reference: str | None = None
    id: str | None = None


@dataclass
class RAGPipelineResult:
    """Captured result of executing the RAG pipeline in a single pass."""

    sample_id: str | None
    question: str
    response: str
    retrieved_contexts: list[str]
    sources: list[dict[str, Any]]
    reference: str | None = None
    retrieved_documents_count: int = 0


@dataclass
class EvaluationReport:
    """Overall evaluation output containing per-sample scores and aggregate metrics."""

    timestamp: str
    total_samples: int
    samples_with_reference: int
    samples_without_reference: int
    metrics_evaluated: list[str]
    mean_scores: dict[str, float]
    sample_results: list[dict[str, Any]]
    report_json_path: str | None = None
    report_csv_path: str | None = None


class RagasEvaluator:
    """Evaluates the existing RAG pipeline using Ragas and Gemini judge models."""

    def __init__(
        self,
        rag_service: RAGService | None = None,
        llm_model: str | None = None,
        embedding_model: str | None = None,
    ):
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not configured in settings.")

        self.rag_service = rag_service or RAGService()

        self.eval_llm_model = llm_model or settings.GEMINI_LLM_MODEL
        self.eval_embedding_model = embedding_model or settings.GEMINI_EMBEDDING_MODEL

        # Wrap existing Google Gemini LLM & Embeddings for Ragas
        self.judge_llm = LangchainLLMWrapper(
            ChatGoogleGenerativeAI(
                model=self.eval_llm_model,
                google_api_key=settings.GOOGLE_API_KEY,
            )
        )
        self.judge_embeddings = LangchainEmbeddingsWrapper(
            GoogleGenerativeAIEmbeddings(
                model=self.eval_embedding_model,
                google_api_key=settings.GOOGLE_API_KEY,
            )
        )
        # Gemini does not support multiple completion candidates (n > 1); configure strictness = 1
        answer_relevancy.strictness = 1

    def execute_rag_pipeline_single_pass(
        self,
        question: str,
        k: int | None = None,
        reference: str | None = None,
        sample_id: str | None = None,
    ) -> RAGPipelineResult:
        """Run Chroma similarity search, Cohere reranking, and Gemini generation exactly once.

        Captures:
        1. User question
        2. Retrieved/reranked contexts (raw chunk texts for Ragas)
        3. Generated answer
        4. Sources and citations
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        clean_question = question.strip()
        effective_k = k if k is not None else settings.RERANK_TOP_K
        initial_k = max(effective_k * 3, settings.RERANK_INITIAL_K)

        # 1. Candidate Retrieval (Chroma)
        initial_documents = self.rag_service.vector_store.similarity_search(
            query=clean_question,
            k=initial_k,
        )

        # 2. Precision Reranking (Cohere)
        reranked_documents = self.rag_service.reranker.rerank(
            query=clean_question,
            documents=initial_documents,
            top_n=effective_k,
        )

        # 3. Format Context String & Structured Sources (identical to RAGService)
        sources: list[dict[str, Any]] = []
        context_parts: list[str] = []

        for index, document in enumerate(reranked_documents, start=1):
            metadata = document.metadata or {}
            source = {
                "source_id": index,
                "filename": metadata.get("filename", "Unknown"),
                "page": metadata.get("page_number"),
                "page_number": metadata.get("page_number"),
                "title": metadata.get("title", "Untitled document"),
            }
            sources.append(source)
            context_parts.append(
                f"[Source {index}]\n"
                f"Title: {source['title']}\n"
                f"Filename: {source['filename']}\n"
                f"Page: {source['page_number']}\n"
                f"Content:\n{document.page_content}"
            )

        context_str = "\n\n".join(context_parts)

        # 4. Answer Generation (Gemini LLM)
        answer = self.rag_service.llm_service.generate_answer(
            question=clean_question,
            context=context_str,
        )

        # Individual chunk contents for Ragas context evaluation
        chunk_texts = [doc.page_content for doc in reranked_documents]
        if not chunk_texts and context_str:
            chunk_texts = [context_str]

        return RAGPipelineResult(
            sample_id=sample_id,
            question=clean_question,
            response=answer,
            retrieved_contexts=chunk_texts,
            sources=sources,
            reference=reference.strip() if reference and reference.strip() else None,
            retrieved_documents_count=len(reranked_documents),
        )

    def evaluate_samples(
        self,
        samples: Sequence[EvaluationSample | dict[str, Any]],
        k: int | None = None,
        output_dir: str | Path | None = None,
    ) -> EvaluationReport:
        """Execute RAG pipeline on each sample in single pass, then run Ragas evaluations."""
        normalized_samples: list[EvaluationSample] = []
        for s in samples:
            if isinstance(s, EvaluationSample):
                normalized_samples.append(s)
            elif isinstance(s, dict):
                normalized_samples.append(
                    EvaluationSample(
                        question=s.get("question", ""),
                        reference=s.get("reference"),
                        id=s.get("id"),
                    )
                )

        if not normalized_samples:
            raise ValueError("No evaluation samples provided.")

        logger.info("Executing RAG pipeline for %d samples...", len(normalized_samples))
        pipeline_results: list[RAGPipelineResult] = []

        for idx, sample in enumerate(normalized_samples, start=1):
            sample_id = sample.id or f"sample_{idx:03d}"
            logger.info("[%d/%d] Running pipeline for question: %s", idx, len(normalized_samples), sample.question)
            res = self.execute_rag_pipeline_single_pass(
                question=sample.question,
                k=k,
                reference=sample.reference,
                sample_id=sample_id,
            )
            pipeline_results.append(res)

        # Split into samples with reference and without reference
        results_with_ref = [r for r in pipeline_results if r.reference]
        results_without_ref = [r for r in pipeline_results if not r.reference]

        score_records_by_id: dict[str, dict[str, Any]] = {}

        # Initialize base record structure for each sample
        for r in pipeline_results:
            key = r.sample_id or r.question
            score_records_by_id[key] = {
                "id": r.sample_id,
                "question": r.question,
                "reference": r.reference,
                "response": r.response,
                "retrieved_contexts_count": len(r.retrieved_contexts),
                "sources": r.sources,
                "faithfulness": None,
                "answer_relevancy": None,
                "context_precision": None,
                "multihop_context_precision": None,
                "context_recall": None,
            }

        # 1. Evaluate samples WITH reference: Faithfulness, Answer Relevancy, Context Precision, MultiHop Context Precision, Context Recall
        if results_with_ref:
            logger.info("Evaluating %d samples with reference (5 metrics)...", len(results_with_ref))
            ds_dict = {
                "user_input": [r.question for r in results_with_ref],
                "response": [r.response for r in results_with_ref],
                "retrieved_contexts": [r.retrieved_contexts for r in results_with_ref],
                "reference": [r.reference for r in results_with_ref],
            }
            ds_with_ref = Dataset.from_dict(ds_dict)
            metrics_5 = [faithfulness, answer_relevancy, context_precision, multihop_context_precision, context_recall]
            eval_run_config = RunConfig(
                max_workers=2,
                max_retries=10,
                max_wait=60,
            )
            eval_res_5 = evaluate(
                ds_with_ref,
                metrics=metrics_5,
                llm=self.judge_llm,
                embeddings=self.judge_embeddings,
                run_config=eval_run_config,
                raise_exceptions=False,
                show_progress=True,
            )

            # Ragas returns scores list of dicts corresponding to rows
            for idx, r in enumerate(results_with_ref):
                key = r.sample_id or r.question
                scores = eval_res_5.scores[idx] if idx < len(eval_res_5.scores) else {}
                score_records_by_id[key]["faithfulness"] = scores.get("faithfulness")
                score_records_by_id[key]["answer_relevancy"] = scores.get("answer_relevancy")
                score_records_by_id[key]["context_precision"] = scores.get("context_precision")
                score_records_by_id[key]["multihop_context_precision"] = scores.get("multihop_context_precision")
                score_records_by_id[key]["context_recall"] = scores.get("context_recall")

        # 2. Evaluate samples WITHOUT reference: Faithfulness, Answer Relevancy only
        if results_without_ref:
            logger.info("Evaluating %d samples without reference (2 metrics)...", len(results_without_ref))
            ds_dict_no_ref = {
                "user_input": [r.question for r in results_without_ref],
                "response": [r.response for r in results_without_ref],
                "retrieved_contexts": [r.retrieved_contexts for r in results_without_ref],
            }
            ds_no_ref = Dataset.from_dict(ds_dict_no_ref)
            metrics_2 = [faithfulness, answer_relevancy]
            eval_res_2 = evaluate(
                ds_no_ref,
                metrics=metrics_2,
                llm=self.judge_llm,
                embeddings=self.judge_embeddings,
                run_config=eval_run_config if results_with_ref else RunConfig(max_workers=2, max_retries=10, max_wait=60),
                raise_exceptions=False,
                show_progress=True,
            )

            for idx, r in enumerate(results_without_ref):
                key = r.sample_id or r.question
                scores = eval_res_2.scores[idx] if idx < len(eval_res_2.scores) else {}
                score_records_by_id[key]["faithfulness"] = scores.get("faithfulness")
                score_records_by_id[key]["answer_relevancy"] = scores.get("answer_relevancy")

        sample_results = list(score_records_by_id.values())

        # Calculate mean scores
        metric_names = [
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "multihop_context_precision",
            "context_recall",
        ]
        mean_scores: dict[str, float] = {}

        for m in metric_names:
            valid_vals = [
                s[m]
                for s in sample_results
                if s.get(m) is not None and not (isinstance(s[m], float) and (s[m] != s[m]))  # filter NaN
            ]
            if valid_vals:
                mean_scores[m] = round(sum(valid_vals) / len(valid_vals), 4)

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report = EvaluationReport(
            timestamp=timestamp_str,
            total_samples=len(pipeline_results),
            samples_with_reference=len(results_with_ref),
            samples_without_reference=len(results_without_ref),
            metrics_evaluated=list(mean_scores.keys()),
            mean_scores=mean_scores,
            sample_results=sample_results,
        )

        # Save reports if output directory is provided or default reports directory exists
        reports_dir = Path(output_dir or settings.DATA_DIR / "evaluation" / "reports")
        reports_dir.mkdir(parents=True, exist_ok=True)

        json_path = reports_dir / f"ragas_report_{timestamp_str}.json"
        csv_path = reports_dir / f"ragas_report_{timestamp_str}.csv"

        self._save_json(report, json_path)
        self._save_csv(sample_results, mean_scores, csv_path)

        report.report_json_path = str(json_path)
        report.report_csv_path = str(csv_path)

        logger.info("Evaluation report saved to:\n  JSON: %s\n  CSV: %s", json_path, csv_path)
        return report

    @staticmethod
    def _save_json(report: EvaluationReport, file_path: Path) -> None:
        """Save report data to JSON."""
        data = asdict(report)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _save_csv(
        sample_results: list[dict[str, Any]],
        mean_scores: dict[str, float],
        file_path: Path,
    ) -> None:
        """Save flat sample results and average summary to CSV."""
        fieldnames = [
            "id",
            "question",
            "reference",
            "response",
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "multihop_context_precision",
            "context_recall",
            "retrieved_contexts_count",
            "sources_summary",
        ]

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in sample_results:
                sources_str = "; ".join(
                    f"{s.get('filename')} (p.{s.get('page')})" for s in row.get("sources", [])
                )
                writer.writerow(
                    {
                        "id": row.get("id"),
                        "question": row.get("question"),
                        "reference": row.get("reference"),
                        "response": row.get("response"),
                        "faithfulness": row.get("faithfulness"),
                        "answer_relevancy": row.get("answer_relevancy"),
                        "context_precision": row.get("context_precision"),
                        "multihop_context_precision": row.get("multihop_context_precision"),
                        "context_recall": row.get("context_recall"),
                        "retrieved_contexts_count": row.get("retrieved_contexts_count"),
                        "sources_summary": sources_str,
                    }
                )

            # Append summary row
            writer.writerow(
                {
                    "id": "AVERAGE_MEAN",
                    "question": "AGGREGATE SUMMARY ACROSS SAMPLES",
                    "reference": "",
                    "response": "",
                    "faithfulness": mean_scores.get("faithfulness"),
                    "answer_relevancy": mean_scores.get("answer_relevancy"),
                    "context_precision": mean_scores.get("context_precision"),
                    "multihop_context_precision": mean_scores.get("multihop_context_precision"),
                    "context_recall": mean_scores.get("context_recall"),
                    "retrieved_contexts_count": "",
                    "sources_summary": "",
                }
            )
