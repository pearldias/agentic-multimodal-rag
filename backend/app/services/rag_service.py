from backend.app.core.config import settings
from backend.app.services.vector_store import VectorStoreService
from backend.app.services.llm_service import LLMService
from backend.app.services.reranker import CohereRerankerService
from backend.app.services.context_manager import ContextManager


class RAGService:
    def __init__(
        self,
        vector_store: VectorStoreService | None = None,
        llm_service: LLMService | None = None,
        reranker: CohereRerankerService | None = None,
        context_manager: ContextManager | None = None,
    ):
        self.vector_store = vector_store or VectorStoreService()
        self.llm_service = llm_service or LLMService()
        self.reranker = reranker or CohereRerankerService()
        self.context_manager = context_manager or ContextManager(
            llm_service=self.llm_service
        )

    def answer_question(
        self,
        question: str,
        k: int | None = None,
        conversation_id: str | None = None,
    ) -> dict:
        """
        Retrieve candidate chunks, rerank with Cohere, and prepare grounded context.
        Uses short-term conversation context for follow-up question contextualization.
        """

        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        effective_k = k if k is not None else settings.RERANK_TOP_K
        initial_k = max(effective_k * 3, settings.RERANK_INITIAL_K)

        history_msgs = []
        if conversation_id:
            history_msgs = self.context_manager.get_context_window(
                conversation_id=conversation_id,
                limit=settings.MEMORY_WINDOW_MESSAGES,
            )

        search_query = self.context_manager.contextualize_query(
            question=question,
            history=history_msgs,
        )

        initial_documents = self.vector_store.similarity_search(
            search_query,
            k=initial_k,
        )

        documents = self.reranker.rerank(
            query=search_query,
            documents=initial_documents,
            top_n=effective_k,
        )

        sources = []
        context_parts = []

        for index, document in enumerate(documents, start=1):
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

        context = "\n\n".join(context_parts)

        return {
            "question": question,
            "search_query": search_query,
            "context": context,
            "sources": sources,
            "retrieved_documents": len(documents),
            "history": self.context_manager.format_history_for_llm(history_msgs),
        }

    def ask(
        self,
        question: str,
        k: int | None = None,
        conversation_id: str | None = None,
    ) -> dict:
        """
        Retrieve relevant chunks and generate a grounded answer.
        """

        retrieval_result = self.answer_question(
            question=question,
            k=k,
            conversation_id=conversation_id,
        )

        answer = self.llm_service.generate_answer(
            question=question,
            context=retrieval_result["context"],
            chat_history=retrieval_result.get("history"),
        )

        return {
            "question": question,
            "answer": answer,
            "sources": retrieval_result["sources"],
            "retrieved_documents": retrieval_result["retrieved_documents"],
            "search_query": retrieval_result.get("search_query", question),
        }

    def ask_stream(
        self,
        question: str,
        k: int | None = None,
        conversation_id: str | None = None,
    ):
        """
        Retrieve candidate chunks, rerank, and return metadata with token generator.
        """
        retrieval_result = self.answer_question(
            question=question,
            k=k,
            conversation_id=conversation_id,
        )

        metadata = {
            "question": question,
            "search_query": retrieval_result.get("search_query", question),
            "sources": retrieval_result["sources"],
            "retrieved_documents": retrieval_result["retrieved_documents"],
        }

        token_stream = self.llm_service.generate_answer_stream(
            question=question,
            context=retrieval_result["context"],
            chat_history=retrieval_result.get("history"),
        )

        return metadata, token_stream