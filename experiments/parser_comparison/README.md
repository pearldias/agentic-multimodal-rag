# Parser Comparison Experiment: Custom Parsers vs LangChain Document Loaders

This isolated experiment compares our custom document parsers against standard LangChain document loaders using the representative documents in `data/raw`.

## Target Loaders Compared
- **PDF**: Custom `PdfParser` vs `PyMuPDFLoader`
- **DOCX**: Custom `DocxParser` vs `Docx2txtLoader`
- **XLSX**: Custom `XlsxParser` vs `UnstructuredExcelLoader`
- **TXT**: Custom `TxtParser` vs `TextLoader`

## Evaluation Dimensions
1. **Parsing time** (execution latency in milliseconds)
2. **Number of documents/elements returned** (cardinality and hierarchy)
3. **Extracted text quality** (Unicode NFKC, hyphenation repair, whitespace)
4. **Metadata** (schema completeness, consistency, typed Pydantic models)
5. **Page boundaries** (1-based vs 0-based indexing, worksheet separation)
6. **Tables / structured content** (Markdown table preservation vs flattened tokens)
7. **Headers / footers** (handling and noise reduction)
8. **Errors / failures** (empty files, corrupted files, missing files)
9. **Dependencies** (transitive overhead, package bloat, deprecation warnings)
10. **Integration complexity** (compatibility with `ChunkingService` and `IngestionService`)

## How to Run

From the project root:

```bash
.\venv\Scripts\python.exe experiments/parser_comparison/benchmark.py
```

## Generated Artifacts
- `results.json`: Full machine-readable benchmark outputs, timing, metadata schemas, and preview samples.
- `results_summary.md`: Comprehensive report and feature matrix ready to present to your mentor.
