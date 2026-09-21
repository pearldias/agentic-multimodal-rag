from backend.app.services.rag_service import RAGService


def main():
    service = RAGService()

    question = "What approvals are required before a production deployment?"

    result = service.ask(
        question=question,
        k=4,
    )

    print("\nQuestion:")
    print(result["question"])

    print("\nGenerated Answer:")
    print(result["answer"])

    print("\nSources:")
    for source in result["sources"]:
        print(
            f"- {source['filename']} "
            f"(Page {source['page_number']})"
        )

    print(
        f"\nRetrieved documents: "
        f"{result['retrieved_documents']}"
    )


if __name__ == "__main__":
    main()