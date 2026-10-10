"""Unit tests for the Ragas evaluation module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.documents import Document

from backend.app.evaluation.ragas_evaluator import (
    EvaluationReport,
    EvaluationSample,
    MultiHopContextPrecision,
    RAGPipelineResult,
    RagasEvaluator,
)


def test_evaluation_sample_dataclass() -> None:
    sample = EvaluationSample(
        question="What is the leave policy?",
        reference="20 days annual leave",
        id="eval_001",
    )
    assert sample.question == "What is the leave policy?"
    assert sample.reference == "20 days annual leave"
    assert sample.id == "eval_001"


def test_rag_pipeline_result_dataclass() -> None:
    result = RAGPipelineResult(
        sample_id="eval_001",
        question="What is leave policy?",
        response="Employees receive 20 days.",
        retrieved_contexts=["Policy section 1", "Policy section 2"],
        sources=[{"source_id": 1, "filename": "policy.pdf"}],
        reference="20 days per year",
        retrieved_documents_count=2,
    )
    assert result.sample_id == "eval_001"
    assert len(result.retrieved_contexts) == 2
    assert len(result.sources) == 1
    assert result.response == "Employees receive 20 days."


def test_execute_rag_pipeline_single_pass_validation() -> None:
    evaluator = RagasEvaluator.__new__(RagasEvaluator)
    evaluator.rag_service = MagicMock()

    with pytest.raises(ValueError, match="Question cannot be empty"):
        evaluator.execute_rag_pipeline_single_pass("")

    with pytest.raises(ValueError, match="Question cannot be empty"):
        evaluator.execute_rag_pipeline_single_pass("   ")


def test_execute_rag_pipeline_single_pass_mock() -> None:
    """Verify single-pass execution calls vector search, rerank, and LLM exactly once."""
    mock_vector_store = MagicMock()
    candidate_docs = [
        Document(page_content="Leave policy chunk 1", metadata={"filename": "leave.pdf", "page_number": 1, "title": "Leave Policy"}),
        Document(page_content="Leave policy chunk 2", metadata={"filename": "leave.pdf", "page_number": 2, "title": "Leave Policy"}),
    ]
    mock_vector_store.similarity_search.return_value = candidate_docs

    mock_reranker = MagicMock()
    reranked_docs = [
        Document(page_content="Leave policy chunk 1", metadata={"filename": "leave.pdf", "page_number": 1, "title": "Leave Policy"}),
    ]
    mock_reranker.rerank.return_value = reranked_docs

    mock_llm = MagicMock()
    mock_llm.generate_answer.return_value = "Employees receive leave as detailed in [Source 1]."

    mock_rag_service = MagicMock()
    mock_rag_service.vector_store = mock_vector_store
    mock_rag_service.reranker = mock_reranker
    mock_rag_service.llm_service = mock_llm

    evaluator = RagasEvaluator.__new__(RagasEvaluator)
    evaluator.rag_service = mock_rag_service

    result = evaluator.execute_rag_pipeline_single_pass(
        question="What is the leave policy?",
        k=2,
        reference="20 days annual leave",
        sample_id="test_01",
    )

    # 1. Similarity search called exactly ONCE
    mock_vector_store.similarity_search.assert_called_once()

    # 2. Reranker called exactly ONCE
    mock_reranker.rerank.assert_called_once_with(
        query="What is the leave policy?",
        documents=candidate_docs,
        top_n=2,
    )

    # 3. LLM answer generation called exactly ONCE
    mock_llm.generate_answer.assert_called_once()
    llm_call_args = mock_llm.generate_answer.call_args
    assert "Leave policy chunk 1" in llm_call_args.kwargs["context"]

    # 4. Captured outputs
    assert result.sample_id == "test_01"
    assert result.question == "What is the leave policy?"
    assert result.response == "Employees receive leave as detailed in [Source 1]."
    assert result.retrieved_contexts == ["Leave policy chunk 1"]
    assert result.reference == "20 days annual leave"
    assert len(result.sources) == 1
    assert result.sources[0]["filename"] == "leave.pdf"


def test_save_json_and_csv(tmp_path: Path) -> None:
    report = EvaluationReport(
        timestamp="20261007_120000",
        total_samples=1,
        samples_with_reference=1,
        samples_without_reference=0,
        metrics_evaluated=["faithfulness", "answer_relevancy"],
        mean_scores={"faithfulness": 0.95, "answer_relevancy": 0.88},
        sample_results=[
            {
                "id": "sample_1",
                "question": "What is leave?",
                "reference": "20 days",
                "response": "20 days of leave",
                "faithfulness": 0.95,
                "answer_relevancy": 0.88,
                "context_precision": None,
                "context_recall": None,
                "retrieved_contexts_count": 2,
                "sources": [{"filename": "leave.pdf", "page": 1}],
            }
        ],
    )

    json_path = tmp_path / "report.json"
    csv_path = tmp_path / "report.csv"

    RagasEvaluator._save_json(report, json_path)
    RagasEvaluator._save_csv(report.sample_results, report.mean_scores, csv_path)

    assert json_path.exists()
    assert csv_path.exists()

    json_text = json_path.read_text(encoding="utf-8")
    assert "20261007_120000" in json_text
    assert "sample_1" in json_text

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "sample_1" in csv_text
    assert "AVERAGE_MEAN" in csv_text
    assert "0.95" in csv_text
    assert "multihop_context_precision" in csv_text


def test_multihop_context_precision_ap_calculation() -> None:
    """Validate Average Precision math for complementary and irrelevant chunk permutations."""
    calc = MultiHopContextPrecision.calculate_average_precision

    # 1. Complementary chunks both at top ranks: AP = 1.0
    assert calc([1, 1, 0, 0, 0]) == 1.0

    # 2. Single relevant chunk at rank 1: AP = 1.0
    assert calc([1, 0, 0, 0, 0]) == 1.0

    # 3. All irrelevant chunks: AP = 0.0
    assert calc([0, 0, 0, 0, 0]) == 0.0
    assert calc([]) == 0.0

    # 4. Irrelevant chunk ranked before complementary chunks penalizes precision:
    # rank 1: 0, rank 2: 1 (p@2=0.5), rank 3: 1 (p@3=2/3) => (0.5 + 2/3) / 2 = 7/12 ~ 0.5833
    ap_penalized = calc([0, 1, 1, 0, 0])
    assert abs(ap_penalized - 0.5833) < 0.001

    # 5. Irrelevant chunk interspersed between complementary chunks:
    # rank 1: 1 (p@1=1.0), rank 2: 0, rank 3: 1 (p@3=2/3) => (1.0 + 2/3) / 2 = 5/6 ~ 0.8333
    ap_interspersed = calc([1, 0, 1, 0, 0])
    assert abs(ap_interspersed - 0.8333) < 0.001


@pytest.mark.anyio
async def test_multihop_context_precision_evaluation_mock() -> None:
    """Verify complementary chunks receive verdict 1 and contribute jointly to AP."""
    from backend.app.evaluation.ragas_evaluator import ChunkVerification, MultiHopContextPrecision

    metric = MultiHopContextPrecision()
    mock_prompt = MagicMock()

    # Scenario 1: Complementary chunks: Chunk 1 (part 1), Chunk 2 (part 2), Chunk 3 (irrelevant)
    mock_prompt.generate_multiple = AsyncMock(
        side_effect=[
            [ChunkVerification(reason="Provides project milestone", verdict=1)],
            [ChunkVerification(reason="Provides HR leave policy notice period", verdict=1)],
            [ChunkVerification(reason="Unrelated employee handbook rules", verdict=0)],
        ]
    )
    metric.prompt = mock_prompt
    metric.llm = MagicMock()

    sample = MagicMock()
    sample.user_input = "What is the milestone and leave notice period?"
    sample.reference = "The milestone is Solar Installation and leave notice is 14 days."
    sample.retrieved_contexts = [
        "Milestone: Solar Installation on June 30, 2027.",
        "HR Notice: Leave requests must be submitted at least 14 days in advance.",
        "Dress code: Business casual.",
    ]

    score = await metric._single_turn_ascore(sample, callbacks=None)
    assert score == 1.0
    assert mock_prompt.generate_multiple.call_count == 3


@pytest.mark.anyio
async def test_multihop_context_precision_irrelevant_penalized_mock() -> None:
    """Verify irrelevant chunk at rank 1 correctly penalizes the multi-hop precision score."""
    from backend.app.evaluation.ragas_evaluator import ChunkVerification, MultiHopContextPrecision

    metric = MultiHopContextPrecision()
    mock_prompt = MagicMock()

    # Scenario 2: Irrelevant chunk at rank 1, complementary chunks at ranks 2 and 3
    mock_prompt.generate_multiple = AsyncMock(
        side_effect=[
            [ChunkVerification(reason="Unrelated dress code rule", verdict=0)],
            [ChunkVerification(reason="Provides project milestone", verdict=1)],
            [ChunkVerification(reason="Provides HR notice period", verdict=1)],
        ]
    )
    metric.prompt = mock_prompt
    metric.llm = MagicMock()

    sample = MagicMock()
    sample.user_input = "What is the milestone and leave notice period?"
    sample.reference = "The milestone is Solar Installation and leave notice is 14 days."
    sample.retrieved_contexts = [
        "Dress code: Business casual.",
        "Milestone: Solar Installation on June 30, 2027.",
        "HR Notice: Leave requests must be submitted at least 14 days in advance.",
    ]

    score = await metric._single_turn_ascore(sample, callbacks=None)
    assert abs(score - 0.5833) < 0.001


