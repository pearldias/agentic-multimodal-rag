"""Unit tests for LexiRAG document ingestion, parsing, normalization, and validation."""

from pathlib import Path
import docx
import fitz
import openpyxl
import pytest
from backend.app.core.config import settings
from backend.app.core.exceptions import (
    CorruptedDocumentError,
    EmptyDocumentError,
    UnsupportedFileTypeError,
)
from backend.app.models.document import DocumentType, ParsedDocument
from backend.app.services.document_parser import (
    DocumentParserService,
    format_table_as_markdown,
    normalize_legal_text,
    normalize_unicode,
    repair_hyphenation,
)


# ============================================================================
# 1. Normalization & Structure Preservation Tests
# ============================================================================


class TestLegalTextNormalization:
    """Tests for text normalization and structure preservation."""

    def test_normalize_unicode_and_smart_quotes(self) -> None:
        raw = "“Section 124A” was challenged in ‘Kedar Nath’ case — AIR 1962 SC 955. Ligature: ﬁle."
        normalized = normalize_unicode(raw)
        assert '"Section 124A"' in normalized
        assert "'Kedar Nath'" in normalized
        assert "—" in normalized
        assert "file" in normalized  # ligature ﬁ unpacked

    def test_repair_hyphenation(self) -> None:
        broken_text = "The constitu-\ntional validity of the Act was upheld in juris-\ndiction."
        repaired = repair_hyphenation(broken_text)
        assert "constitutional" in repaired
        assert "jurisdiction" in repaired

    def test_preserves_legal_numbering_and_headings(self) -> None:
        legal_text = (
            "Section 9. Power to make rules.\n"
            "(1) The Central Government may, by notification, make rules.\n"
            "   (a) regulating the procedure of the committee;\n"
            "   (b) defining qualifications of members;\n"
            "   (i) five years of judicial experience;\n"
            "(2) Every rule shall be laid before Parliament."
        )
        normalized = normalize_legal_text(legal_text)

        # Ensure headings and line breaks between numbered clauses are preserved
        assert "Section 9. Power to make rules." in normalized
        assert "(1) The Central Government may" in normalized
        assert "(a) regulating" in normalized
        assert "(i) five years" in normalized
        # Verify lines are not aggressively merged into one paragraph
        lines = normalized.split("\n")
        assert len(lines) >= 6

    def test_collapses_excessive_newlines(self) -> None:
        spaced_text = "Heading\n\n\n\n\nParagraph 1.\n\n\n\nParagraph 2."
        normalized = normalize_legal_text(spaced_text)
        assert "\n\n\n" not in normalized
        assert "Heading\n\nParagraph 1.\n\nParagraph 2." == normalized

    def test_format_table_as_markdown(self) -> None:
        headers = ["Section", "Offence", "Punishment"]
        rows = [
            ["302", "Murder", "Death or Imprisonment for life"],
            ["378", "Theft", "Imprisonment up to 3 years"],
        ]
        md = format_table_as_markdown(headers, rows)
        assert "| Section | Offence | Punishment |" in md
        assert "| --- | --- | --- |" in md
        assert "| 302 | Murder | Death or Imprisonment for life |" in md


# ============================================================================
# 2. Validation & Edge Cases Tests
# ============================================================================


class TestParserValidation:
    """Tests for file validation, unsupported formats, and corruption handling."""

    @pytest.fixture
    def parser_service(self) -> DocumentParserService:
        return DocumentParserService()

    def test_missing_file_raises_file_not_found(self, parser_service: DocumentParserService, tmp_path: Path) -> None:
        non_existent = tmp_path / "does_not_exist.pdf"
        with pytest.raises(FileNotFoundError, match="File not found"):
            parser_service.parse_file(non_existent)

    def test_unsupported_file_extension(self, parser_service: DocumentParserService, tmp_path: Path) -> None:
        unsupported_file = tmp_path / "legal_brief.zip"
        unsupported_file.write_bytes(b"PK fake zip content")
        with pytest.raises(UnsupportedFileTypeError, match="Unsupported file type 'zip'"):
            parser_service.parse_file(unsupported_file)

    def test_empty_zero_byte_file(self, parser_service: DocumentParserService, tmp_path: Path) -> None:
        empty_txt = tmp_path / "empty_affidavit.txt"
        empty_txt.write_text("", encoding="utf-8")
        with pytest.raises(EmptyDocumentError, match="File is 0 bytes"):
            parser_service.parse_file(empty_txt)

    def test_whitespace_only_file(self, parser_service: DocumentParserService, tmp_path: Path) -> None:
        whitespace_txt = tmp_path / "blank_notice.txt"
        whitespace_txt.write_text("   \n\n\t  \n   ", encoding="utf-8")
        with pytest.raises(EmptyDocumentError, match="contains only whitespace or empty content"):
            parser_service.parse_file(whitespace_txt)

    def test_corrupted_pdf_raises_error(self, parser_service: DocumentParserService, tmp_path: Path) -> None:
        corrupted_pdf = tmp_path / "damaged_order.pdf"
        corrupted_pdf.write_bytes(b"%PDF-1.4 completely corrupted binary data trailing...")
        with pytest.raises(CorruptedDocumentError, match="Failed to parse corrupted document"):
            parser_service.parse_file(corrupted_pdf)

    def test_corrupted_docx_raises_error(self, parser_service: DocumentParserService, tmp_path: Path) -> None:
        corrupted_docx = tmp_path / "damaged_agreement.docx"
        corrupted_docx.write_bytes(b"Not a valid zip/docx archive")
        with pytest.raises(CorruptedDocumentError, match="Failed to parse corrupted document"):
            parser_service.parse_file(corrupted_docx)

    def test_corrupted_xlsx_raises_error(self, parser_service: DocumentParserService, tmp_path: Path) -> None:
        corrupted_xlsx = tmp_path / "damaged_table.xlsx"
        corrupted_xlsx.write_bytes(b"Not a valid zip/xlsx archive")
        with pytest.raises(CorruptedDocumentError, match="Failed to parse corrupted document"):
            parser_service.parse_file(corrupted_xlsx)


# ============================================================================
# 3. Document Format Parsers Tests (TXT, PDF, DOCX, XLSX)
# ============================================================================


class TestDocumentParsers:
    """Tests for parsing concrete document types with synthetic file generators."""

    @pytest.fixture
    def parser_service(self) -> DocumentParserService:
        return DocumentParserService()

    def test_parse_txt_file(self, parser_service: DocumentParserService, tmp_path: Path) -> None:
        txt_path = tmp_path / "kesavananda_bharati_summary.txt"
        content = (
            "IN THE SUPREME COURT OF INDIA\n\n"
            "Kesavananda Bharati v. State of Kerala (1973) 4 SCC 225\n\n"
            "Held: Parliament cannot alter the basic structure of the Constitution."
        )
        txt_path.write_text(content, encoding="utf-8")

        result = parser_service.parse_file(
            txt_path,
            source_url="https://indiankanoon.org/doc/257876/",
            title="Kesavananda Bharati Case Summary",
        )

        assert isinstance(result, ParsedDocument)
        assert result.metadata.filename == "kesavananda_bharati_summary.txt"
        assert result.metadata.file_type == DocumentType.TXT.value
        assert result.metadata.title == "Kesavananda Bharati Case Summary"
        assert result.metadata.source_url == "https://indiankanoon.org/doc/257876/"
        assert result.metadata.total_pages == 1
        assert len(result.pages) == 1
        assert "basic structure of the Constitution" in result.pages[0].text
        assert result.pages[0].page_number == 1

    def test_parse_multi_page_pdf(self, parser_service: DocumentParserService, tmp_path: Path) -> None:
        pdf_path = tmp_path / "supreme_court_judgment.pdf"

        # Generate a 3-page synthetic PDF using PyMuPDF (fitz)
        doc = fitz.open()
        p1 = doc.new_page()
        p1.insert_text((50, 72), "SUPREME COURT OF INDIA\nWrit Petition (Civil) No. 494 of 2012\nJustice K.S. Puttaswamy")
        p2 = doc.new_page()
        p2.insert_text((50, 72), "Section 21: Right to Life and Personal Liberty includes the right to privacy.")
        p3 = doc.new_page()
        p3.insert_text((50, 72), "ORDER:\nThe reference is answered accordingly. Privacy is a fundamental right.")
        doc.set_metadata({"title": "Puttaswamy Privacy Judgment", "author": "Supreme Court Registry"})
        doc.save(str(pdf_path))
        doc.close()

        result = parser_service.parse_file(pdf_path)

        assert result.metadata.filename == "supreme_court_judgment.pdf"
        assert result.metadata.file_type == DocumentType.PDF.value
        assert result.metadata.title == "Puttaswamy Privacy Judgment"
        assert result.metadata.total_pages == 3
        assert len(result.pages) == 3

        # Verify page number tracking (1-indexed)
        assert result.pages[0].page_number == 1
        assert "Justice K.S. Puttaswamy" in result.pages[0].text
        assert result.pages[1].page_number == 2
        assert "Right to Life" in result.pages[1].text
        assert result.pages[2].page_number == 3
        assert "Privacy is a fundamental right" in result.pages[2].text

    def test_parse_docx_with_reading_order_and_tables(
        self, parser_service: DocumentParserService, tmp_path: Path
    ) -> None:
        docx_path = tmp_path / "arbitration_agreement.docx"

        # Create synthetic DOCX with alternating paragraphs and tables
        doc = docx.Document()
        doc.core_properties.title = "Arbitration and Conciliation Agreement"
        doc.add_paragraph("Clause 1. Definitions and Interpretation.")

        table = doc.add_table(rows=2, cols=3)
        row_0 = table.rows[0].cells
        row_0[0].text = "Term"
        row_0[1].text = "Definition"
        row_0[2].text = "Governing Law"

        row_1 = table.rows[1].cells
        row_1[0].text = "Tribunal"
        row_1[1].text = "Arbitral Tribunal of three arbitrators"
        row_1[2].text = "Arbitration Act 1996"

        doc.add_paragraph("Clause 2. Seat of Arbitration shall be New Delhi, India.")
        doc.save(str(docx_path))

        result = parser_service.parse_file(docx_path)

        assert result.metadata.filename == "arbitration_agreement.docx"
        assert result.metadata.file_type == DocumentType.DOCX.value
        assert result.metadata.title == "Arbitration and Conciliation Agreement"
        assert result.metadata.total_pages == 1

        # Check preserved sequential reading order: Clause 1 -> Table -> Clause 2
        text = result.raw_text
        c1_pos = text.find("Clause 1. Definitions")
        tbl_pos = text.find("| Term | Definition | Governing Law |")
        c2_pos = text.find("Clause 2. Seat of Arbitration")

        assert c1_pos != -1
        assert tbl_pos != -1
        assert c2_pos != -1
        assert c1_pos < tbl_pos < c2_pos

    def test_parse_xlsx_multi_sheet(self, parser_service: DocumentParserService, tmp_path: Path) -> None:
        xlsx_path = tmp_path / "court_schedule_2024.xlsx"

        # Create multi-sheet workbook with openpyxl
        wb = openpyxl.Workbook()
        ws1 = wb.active
        ws1.title = "Court_Roster"
        ws1.append(["Court No.", "Presiding Judge", "Bench Type"])
        ws1.append(["Court 1", "Chief Justice of India", "Constitution Bench"])
        ws1.append(["Court 2", "Justice Sanjiv Khanna", "Division Bench"])

        ws2 = wb.create_sheet(title="Statutory_Fees")
        ws2.append(["Item No.", "Petition Type", "Fee in INR"])
        ws2.append(["1", "Special Leave Petition", "5000"])
        ws2.append(["2", "Review Petition", "2500"])

        # Create a 3rd sheet that is completely empty (should be skipped)
        wb.create_sheet(title="Empty_Notes")

        wb.save(str(xlsx_path))
        wb.close()

        result = parser_service.parse_file(xlsx_path, title="Supreme Court Schedule and Fees")

        assert result.metadata.filename == "court_schedule_2024.xlsx"
        assert result.metadata.file_type == DocumentType.XLSX.value
        assert result.metadata.title == "Supreme Court Schedule and Fees"
        # Only the 2 populated sheets should produce pages
        assert len(result.pages) == 2
        assert result.pages[0].sheet_name == "Court_Roster"
        assert "| Court No. | Presiding Judge | Bench Type |" in result.pages[0].text
        assert "Constitution Bench" in result.pages[0].text

        assert result.pages[1].sheet_name == "Statutory_Fees"
        assert "| Item No. | Petition Type | Fee in INR |" in result.pages[1].text
        assert "5000" in result.pages[1].text


# ============================================================================
# 4. Storage & Service Facade Tests
# ============================================================================


class TestServiceStorageAndMetadata:
    """Tests for document persistence, explicit directory creation, and metadata preservation."""

    def test_explicit_directory_creation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        custom_data_dir = tmp_path / "test_data"
        monkeypatch.setattr(settings, "DATA_DIR", custom_data_dir)
        monkeypatch.setattr(settings, "RAW_DATA_DIR", custom_data_dir / "raw")
        monkeypatch.setattr(settings, "PROCESSED_DATA_DIR", custom_data_dir / "processed")
        monkeypatch.setattr(settings, "METADATA_DIR", custom_data_dir / "metadata")

        assert not settings.RAW_DATA_DIR.exists()
        assert not settings.PROCESSED_DATA_DIR.exists()
        assert not settings.METADATA_DIR.exists()

        DocumentParserService.ensure_data_directories()

        assert settings.RAW_DATA_DIR.exists()
        assert settings.PROCESSED_DATA_DIR.exists()
        assert settings.METADATA_DIR.exists()

    def test_save_parsed_document(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        custom_data_dir = tmp_path / "storage_test"
        monkeypatch.setattr(settings, "DATA_DIR", custom_data_dir)
        monkeypatch.setattr(settings, "RAW_DATA_DIR", custom_data_dir / "raw")
        monkeypatch.setattr(settings, "PROCESSED_DATA_DIR", custom_data_dir / "processed")
        monkeypatch.setattr(settings, "METADATA_DIR", custom_data_dir / "metadata")

        service = DocumentParserService()
        sample_file = tmp_path / "act_notification.txt"
        sample_file.write_text(
            "MINISTRY OF LAW AND JUSTICE\nNotification dated 1st January 2024\nRepealing Act 2023.",
            encoding="utf-8",
        )

        parsed_doc = service.parse_file(sample_file, save=True)

        # Verify files were persisted to the configured directories
        processed_files = list(settings.PROCESSED_DATA_DIR.glob("*.json"))
        metadata_files = list(settings.METADATA_DIR.glob("*.json"))

        assert len(processed_files) == 1
        assert len(metadata_files) == 1
        assert parsed_doc.metadata.filename == "act_notification.txt"
