"""Ingest all documents from the raw data directory."""

from backend.app.services.ingestion import IngestionService


def main() -> None:
    service = IngestionService()

    result = service.ingest_directory()

    print(f"Directory: {result['directory']}")
    print(f"Total files: {result['total_files']}")
    print(f"Successful files: {result['successful_files']}")
    print(f"Failed files: {result['failed_files']}")

    for item in result["results"]:
        print(
            f"{item['filename']}: "
            f"{item['chunks']} chunks stored"
        )

    if result["failures"]:
        print("\nFailures:")

        for failure in result["failures"]:
            print(
                f"- {failure['filename']}: "
                f"{failure['error']}"
            )


if __name__ == "__main__":
    main()