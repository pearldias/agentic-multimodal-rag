import chromadb
from pathlib import Path


CHROMA_PATH = Path("data/chroma")


def main():
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    collections = client.list_collections()

    if not collections:
        print("No Chroma collections found.")
        return

    print("Collections found:")

    for collection in collections:
        print(f"\nCollection: {collection.name}")

        count = collection.count()
        print(f"Total chunks: {count}")

        if count == 0:
            print("This collection is empty.")
            continue

        results = collection.get(
            limit=count,
            include=["metadatas"],
        )

        metadatas = results.get("metadatas", [])

        source_counts = {}

        for metadata in metadatas:
            source = (
                metadata.get("source")
                or metadata.get("filename")
                or metadata.get("file_name")
                or "Unknown source"
            )

            source_counts[source] = source_counts.get(source, 0) + 1

        print("\nDocuments currently stored in Chroma:")

        for source, chunk_count in sorted(source_counts.items()):
            print(f"- {source}: {chunk_count} chunks")


if __name__ == "__main__":
    main()