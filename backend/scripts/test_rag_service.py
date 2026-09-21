from backend.app.services.rag_service import RAGService


def main():
    service = RAGService()

    question = "What approvals are required before a production deployment?"

    result = service.answer_question(question, k=4)

    print("\nQuestion:")
    print(result["question"])

    print("\nRetrieved documents:")
    print(result["retrieved_documents"])

    print("\nContext:")
    print(result["context"][:3000])

    print("\nSources:")
    for source in result["sources"]:
        print(source)


if __name__ == "__main__":
    main()