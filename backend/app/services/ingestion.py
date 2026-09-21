"""Document ingestion service for parsing, chunking, and storing documents."""

import logging
from pathlib import Path
from typing import Any

from backend.app.core.config import settings
from backend.app.services.chunking import ChunkingService
from backend.app.services.document_parser.service import DocumentParserService
from backend.app.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)


class IngestionService:
    """Parse, chunk, and store documents from the raw data directory."""

    def __init__(
        self,
        parser_service=None,
        chunking_service=None,
        vector_store_service=None,
    ) -> None:
        self.parser_service = (
            parser_service or DocumentParserService()
        )

        self.chunking_service = (
            chunking_service or ChunkingService()
        )

        self.vector_store_service = (
            vector_store_service or VectorStoreService()
        )

    def ingest_file(
        self,
        file_path: str | Path,
        save: bool = True,
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        """Parse, chunk, and store one document."""

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document not found: {path}"
            )

        # Keep the original filename separately.
        # Do not modify parsed_document.filename because it is read-only.
        filename = original_filename or path.name

        parsed_document = self.parser_service.parse_file(
            file_path=path,
            save=save,
        )

        chunks = self.chunking_service.chunk_document(
            parsed_document
        )

        # Store the generated chunks in ChromaDB.
        stored_chunks = self.vector_store_service.add_chunks(
            chunks
        )

        logger.info(
            "Successfully ingested %s: %d chunks",
            filename,
            len(chunks),
        )

        return {
            "filename": filename,
            "file_type": parsed_document.file_type,
            "pages": parsed_document.total_pages,
            "chunks": chunks,
            "stored_chunks": stored_chunks,
            "processed": True,
        }

    def ingest_directory(
        self,
        directory: str | Path | None = None,
        save: bool = True,
    ) -> dict[str, Any]:
        """Parse, chunk, and store all supported files in a directory."""

        raw_directory = Path(
            directory or settings.RAW_DATA_DIR
        )

        if not raw_directory.exists():
            raise FileNotFoundError(
                f"Raw data directory not found: {raw_directory}"
            )

        supported_extensions = {
            f".{extension.lower()}"
            for extension in self.parser_service.supported_extensions
        }

        files = [
            path
            for path in raw_directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in supported_extensions
        ]

        results: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []

        for file_path in sorted(files):
            try:
                result = self.ingest_file(
                    file_path=file_path,
                    save=save,
                    original_filename=file_path.name,
                )

                results.append(
                    {
                        "filename": result["filename"],
                        "file_type": result["file_type"],
                        "pages": result["pages"],
                        "chunks": len(result["chunks"]),
                        "stored_chunks": result["stored_chunks"],
                        "processed": True,
                    }
                )

                logger.info(
                    "Successfully ingested %s: %d chunks",
                    file_path.name,
                    len(result["chunks"]),
                )

            except Exception as exc:
                logger.exception(
                    "Failed to ingest file: %s",
                    file_path.name,
                )

                failures.append(
                    {
                        "filename": file_path.name,
                        "error": str(exc),
                    }
                )

        return {
            "directory": str(raw_directory),
            "total_files": len(files),
            "successful_files": len(results),
            "failed_files": len(failures),
            "results": results,
            "failures": failures,
        }