import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.services.ingestion import IngestionService


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/upload",
    tags=["Upload"],
)

ingestion_service = IngestionService()

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".xlsx",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and ingest one supported document.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is missing",
        )

    original_filename = file.filename
    file_extension = Path(original_filename).suffix.lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Allowed types: PDF, DOCX, TXT, XLSX"
            ),
        )

    temporary_path: Path | None = None

    try:
        # Save uploaded file temporarily.
        with NamedTemporaryFile(
            delete=False,
            suffix=file_extension,
        ) as temporary_file:

            temporary_path = Path(temporary_file.name)
            total_size = 0

            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="File size cannot exceed 10 MB",
                    )

                temporary_file.write(chunk)

        # Parse, chunk, embed, and store the document.
        result = ingestion_service.ingest_file(
            file_path=temporary_path,
            save=False,
            original_filename=original_filename,
        )

        return {
            "message": "Document uploaded and ingested successfully",
            "filename": original_filename,
            "file_type": result["file_type"],
            "pages": result["pages"],
            "chunks_created": len(result["chunks"]),
            "chunks_stored": result["stored_chunks"],
            "processed": result["processed"],
        }

    except HTTPException:
        raise

    except Exception as error:
        logger.exception(
            "Failed to upload and ingest file: %s",
            original_filename,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {error}",
        ) from error

    finally:
        # Delete temporary file after processing.
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)

        await file.close()