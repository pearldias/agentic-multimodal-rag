import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.core.config import settings
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


@router.get("")
def list_documents():
    """
    List all indexed documents from the data directory.
    """
    if not settings.RAW_DATA_DIR.exists():
        return []

    docs = []
    for file_path in sorted(settings.RAW_DATA_DIR.iterdir()):
        if file_path.is_file() and file_path.name != ".gitkeep":
            ext = file_path.suffix.lower()
            if ext in ALLOWED_EXTENSIONS:
                file_type = ext.lstrip(".").upper()
                stem_clean = file_path.stem.replace("_", " ").lower()
                category = "General"
                if "overview" in stem_clean or "company" in stem_clean:
                    category = "Company Overview"
                elif "handbook" in stem_clean or "leave" in stem_clean or "onboarding" in stem_clean or "policy" in stem_clean:
                    category = "HR Policy"
                elif "it" in stem_clean or "support" in stem_clean:
                    category = "IT Support"
                elif "engineering" in stem_clean or "standards" in stem_clean or "software" in stem_clean:
                    category = "Engineering"
                elif "cybersecurity" in stem_clean or "security" in stem_clean:
                    category = "Security"
                elif "architecture" in stem_clean:
                    category = "Architecture"
                elif "testing" in stem_clean or "quality" in stem_clean:
                    category = "Quality Assurance"
                elif "deployment" in stem_clean or "devops" in stem_clean:
                    category = "DevOps"
                elif "training" in stem_clean or "course" in stem_clean or "skills" in stem_clean:
                    category = "Learning"
                elif "project" in stem_clean or "poc" in stem_clean or "sop" in stem_clean:
                    category = "Operations"

                docs.append({
                    "name": file_path.name,
                    "type": file_type,
                    "category": category,
                    "status": "Indexed & Active",
                    "source": "data/raw",
                    "size_bytes": file_path.stat().st_size,
                })
    return docs


@router.post("")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and ingest one supported document (PDF, DOCX, XLSX, TXT) into ChromaDB.
    """

    if not file.filename or not file.filename.strip():
        raise HTTPException(
            status_code=400,
            detail="Filename is missing or empty.",
        )

    original_filename = Path(file.filename.strip()).name
    file_extension = Path(original_filename).suffix.lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{file_extension}'. "
                f"Allowed types: PDF, DOCX, TXT, XLSX"
            ),
        )

    settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    destination_path = settings.RAW_DATA_DIR / original_filename

    try:
        total_size = 0
        with destination_path.open("wb") as buffer_file:
            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="File size cannot exceed 10 MB",
                    )
                buffer_file.write(chunk)

        if total_size == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty (0 bytes).",
            )

        # Parse, chunk, embed, and store in ChromaDB
        result = ingestion_service.ingest_file(
            file_path=destination_path,
            save=True,
            original_filename=original_filename,
        )

        return {
            "message": f"Document '{original_filename}' uploaded and ingested successfully",
            "filename": original_filename,
            "file_type": result["file_type"],
            "pages": result["pages"],
            "chunks_created": len(result["chunks"]),
            "chunks_stored": result["stored_chunks"],
            "processed": result["processed"],
        }

    except HTTPException:
        if destination_path.exists():
            destination_path.unlink(missing_ok=True)
        raise

    except Exception as error:
        if destination_path.exists():
            destination_path.unlink(missing_ok=True)
        logger.exception(
            "Failed to upload and ingest file: %s",
            original_filename,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {error}",
        ) from error

    finally:
        await file.close()