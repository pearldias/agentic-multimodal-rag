"""Legal text normalization utilities for LexiRAG.

Preserves legal document structure:
- Section headings
- Numbered sections and clauses (e.g. 1., (a), (i))
- Paragraph breaks
- Tables
- Avoids aggressive collapsing of meaningful newlines
"""

import re
import unicodedata


def normalize_unicode(text: str) -> str:
    """Normalize unicode characters using NFKC and standardize typographic symbols."""
    if not text:
        return ""

    # Unicode NFKC normalization
    text = unicodedata.normalize("NFKC", text)

    # Replace invisible and non-breaking spaces
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")  # Byte order mark

    # Normalize smart quotes and dashes to standard ASCII/Unicode equivalents
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("—", " — ")  # Em-dash with padding
    text = text.replace("–", "-")    # En-dash to standard hyphen

    return text


def repair_hyphenation(text: str) -> str:
    """Repair hyphenated words split across line breaks (common in multi-column court judgments).

    Example: 'constitu-\\ntional' -> 'constitutional'
    Does not affect bullet points (- Item) or legal citations.
    """
    if not text:
        return ""
    # Matches a lowercase word fragment ending with hyphen and newline, followed by lowercase fragment
    return re.sub(r"([a-zA-Z])- *\n *([a-zA-Z])", r"\1\2", text)


def normalize_legal_text(text: str) -> str:
    """Normalize raw extracted legal text while strictly preserving structure.

    Rules:
    1. Normalize Unicode and line endings.
    2. Strip trailing whitespace per line while preserving indentation for sub-clauses.
    3. Collapse 3 or more consecutive newlines to 2 newlines (retaining paragraph breaks).
    4. Preserve section headings, numbered sections (e.g. '1.', '(a)', '(i)', 'Section 9'),
       and markdown tables without flattening lines into a single run-on block.
    """
    if not text:
        return ""

    text = normalize_unicode(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = repair_hyphenation(text)

    # Strip trailing whitespace on each line, keep leading indentation (important for legal hierarchies)
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Collapse excessive blank lines: 3 or more newlines become 2 newlines (standard paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def format_table_as_markdown(headers: list[str], rows: list[list[str]]) -> str:
    """Format structured table rows as a clean Markdown table.

    Ensures column alignment so that downstream chunking and retrieval retain
    associative context between headers and cell values.
    """
    if not headers and not rows:
        return ""

    col_count = max(len(headers), max((len(r) for r in rows), default=0))
    if col_count == 0:
        return ""

    # Pad headers if needed
    padded_headers = [str(h).strip() if h is not None else "" for h in headers]
    if len(padded_headers) < col_count:
        padded_headers.extend([f"Column {i + 1}" for i in range(len(padded_headers), col_count)])

    header_line = "| " + " | ".join(padded_headers) + " |"
    separator_line = "| " + " | ".join(["---"] * col_count) + " |"

    row_lines = []
    for row in rows:
        padded_row = [str(cell).strip() if cell is not None else "" for cell in row]
        if len(padded_row) < col_count:
            padded_row.extend([""] * (col_count - len(padded_row)))
        row_lines.append("| " + " | ".join(padded_row) + " |")

    return "\n".join([header_line, separator_line] + row_lines)
