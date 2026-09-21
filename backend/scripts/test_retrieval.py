from backend.app.services.vector_store import VectorStoreService


def main():
    service = VectorStoreService()

    query = "What is the deployment and release management process?"

    results = service.similarity_search(query, k=3)

    print(f"\nQuery: {query}")
    print(f"Results found: {len(results)}\n")

    for index, result in enumerate(results, start=1):
        print(f"--- Result {index} ---")
        print("Content:", result.page_content[:500])
        print("Metadata:", result.metadata)
        print()


if __name__ == "__main__":
    main()