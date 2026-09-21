from backend.app.services.vector_store import VectorStoreService
from backend.app.services.llm_service import LLMService


class RAGService:
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.llm_service = LLMService()

    def answer_question(self, question: str, k: int = 4) -> dict:
        """
        Retrieve relevant document chunks and prepare grounded context.
        """

        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        documents = self.vector_store.similarity_search(
            question,
            k=k,
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
            "context": context,
            "sources": sources,
            "retrieved_documents": len(documents),
        }

    def ask(self, question: str, k: int = 4) -> dict:
        """
        Retrieve relevant chunks and generate a grounded answer.
        """

        retrieval_result = self.answer_question(
            question=question,
            k=k,
        )

        answer = self.llm_service.generate_answer(
            question=question,
            context=retrieval_result["context"],
        )

        return {
            "question": question,
            "answer": answer,
            "sources": retrieval_result["sources"],
            "retrieved_documents": retrieval_result["retrieved_documents"],
        }