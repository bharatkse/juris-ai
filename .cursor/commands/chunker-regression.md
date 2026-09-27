# Chunker regression (IndiaCode / Gazette)

PDFs or extra notes: $ARGUMENTS

There is **no** dedicated footnote unit test today (`tests/unit/rag/ingestion/test_chunker.py` only checks title propagation). Run the real chunker.

## Steps

1. PDFs (in order): `$ARGUMENTS` if given, else `sample_data/acts/*.pdf` and `server/tests/datasets/rag/raw_datasets/*.pdf`.
2. Drive the same pipeline as ingest: `FileParser` → sanitizer → validator → `TextChunker.chunk()` (`ingestion/pipeline.py` order). Prefer importing those types; do not reimplement split logic.
3. Report, with example chunk ids / first 200 chars:
   - Footnote **leakage**: lines matching `Subs.`, `Ins.`, `Omitted`/`omitted`, `Cl.`, `Sch.`, `Notifn.`, `ibid`, `AIR`, `w.e.f.` that are **not** omitted-section headers (`^\s*\d+[A-Za-z]?\.\s*\[`).
   - **Over-strip**: omitted sections (`20. [Title.] Omitted by ...`) missing from chunks.
   - **Wrap carry**: footnote starting at end of one PDF page/block and continuing on the next — `footnote_carry` in `chunker.py`.
   - Provision splits: `section` / `article` / numbered headers cut mid-sentence.
4. If you add a failing test, put it next to `test_chunker.py` using extracted fixture text (not a 10MB PDF in git) plus one smoke path on a real PDF.

Do not modify chunker regexes unless asked; this command is a report first.
