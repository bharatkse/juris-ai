---
name: indian-legal-chunking
description: Debug and change TextChunker for IndiaCode/Gazette PDFs (amendment footnotes, omitted sections, page-wrapped notes). Use when chunking legal acts, footnote leakage, or ingesting sample_data PDFs.
---

# Indian legal chunking

Code: `server/src/rag/ingestion/chunker.py`. Instance is stateless; `_ChunkState` is per `chunk()` call. Pipeline: parse → sanitize → validate → chunk (`ingestion/pipeline.py`).

## Quirks (encoded in regexes)

| Signal | Regex / flag | Meaning |
|---|---|---|
| Footnote line start | `_FOOTNOTE_LINE_START` `^\s*\d+\.\s+` | Numbered note at left margin |
| Vocab | `_FOOTNOTE_VOCABULARY` `Subs` `Ins` `Omitted` `Cl` `Sch` `Notifn` `ibid` `AIR` `w.e.f.` | Amendment notes, not body |
| Close | `_FOOTNOTE_CLOSING` `(w.e.f....).` or `AIR 20xx...` | End of a note |
| **Keep** omitted section | `_OMITTED_SECTION_HEADER` `^\s*\d+[A-Za-z]?\.\s*\[` | `20. [Controller…] Omitted by …` is **body** |
| Carry | `footnote_carry` / `carry_in_footnote` | Note wrapped across PDF page/block |

True layout-aware footnotes are out of scope; this is gazette-vocab filtering after pypdf flatten.

## Debug workflow

1. Reproduce with `/chunker-regression` and real PDFs: `sample_data/acts/it_act_2000.pdf`, `reservation-1985.pdf`, `server/tests/datasets/rag/raw_datasets/`.
2. Dump blocks from `FileParser` before chunking if the leak is extraction, not split.
3. If a footnote leaks: check whether the line starts with `N.` **and** vocab; wrapped notes need carry `True` at block end.
4. If an omitted **section** disappeared: it likely matched footnote vocab without the `[` header guard — fix `_OMITTED_SECTION_HEADER` or the strip loop, not a general `Omitted` ban.
5. Unit tests should use short fixture strings (IT Act omitted s.20 style). Do not commit huge PDFs; smoke ingest uses `raw_datasets/`.

## Do not

- Put document-sized lists on `TextChunker`.
- Strip mid-sentence `1[electronic signature]` markers in `evidence_in_text()` — eval docs say fix the golden string instead.
- Scope retrieval by `conversation_id` here (not implemented on `HybridRetriever`).
