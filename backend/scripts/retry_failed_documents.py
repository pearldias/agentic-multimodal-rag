"""Retry documents that failed during ingestion."""

import time
from pathlib import Path

from backend.app.core.config import settings
from backend.app.services.ingestion import IngestionService


FAILED_FILES = [
    "SYN_010_Deployment_Release_Management.pdf",
    "SYN_011_Proposal_RFP_Guidelines.docx",
    "SYN_012_Solution_Architecture_Guidelines.pdf",
    "SYN_013_Technology_Capability_Catalogue.pdf",
    "SYN_014_Cybersecurity_Policy_Secure_Dev.pdf",
    "SYN_014_Employee_Skills_Directory.xlsx",
    "SYN_015_Data_Protection_Privacy.pdf",
    "SYN_016_AI_RAG_Development_Guide.pdf",
    "SYN_017_Training_Upskilling_Catalogue.pdf",
    "SYN_018_Training_Course_Catalogue.xlsx",
    "SYN_019_Project_POC_Catalogue.xlsx",
    "SYN_020_Tech_Service_Mapping.xlsx",
]


def main() -> None:
    """Retry ingestion for previously failed documents."""

    service = IngestionService()

    for filename in FAILED_FILES:
        file_path = Path(settings.RAW_DATA_DIR) / filename

        print(f"\nRetrying: {filename}")

        if not file_path.is_file():
            print(f"File not found: {file_path}")
            continue

        try:
            result = service.ingest_file(
                file_path=file_path,
                save=True,
                original_filename=filename,
            )

            print(
                f"Success: {filename} - "
                f"{len(result['chunks'])} chunks stored"
            )

        except Exception as exc:
            print(f"Failed: {filename}")
            print(exc)

        # Prevent immediately sending another embedding request.
        time.sleep(15)


if __name__ == "__main__":
    main()