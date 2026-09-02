# Juris-AI RAG Pipeline

## Purpose

The `rag/` package owns the **RAG data plane** for Juris-AI.

It transforms the legal-document corpus into searchable representations
and retrieves relevant chunks for agents. It is intentionally separate
from the **LLM/Agent intelligence plane**.

``` text
RAG DATA PLANE

Legal Corpus
    ↓
Ingestion
    ↓
Chunks
    ↓
Indexing
    ├──→ Embeddings → PGVector
    └──→ BM25
    ↓
Hybrid Retrieval
    ├──→ Vector Query
    └──→ Keyword Query
          ↓
         RRF
          ↓
      Reranking
          ↓
   RetrievalResult[]
```

The intelligence plane consumes the retrieval results:

``` text
INTELLIGENCE PLANE

User Query
    ↓
Agent
    ↓
RAG / Tools / MCP
    ↓
RetrievalResult[]
    ↓
LLM
    ↓
Answer / Action
```

RAG does **not** own agent execution, LLM orchestration, MCP execution,
conversation management, or application workflow control.

------------------------------------------------------------------------

## Directory Structure

``` text
rag/
├── __init__.py
├── models.py
├── embeddings.py
├── indexer.py
├── hybrid_retriever.py
├── pgvector_store.py
├── keyword_store.py
├── reranker.py
│
├── protocols/
│   ├── __init__.py
│   ├── embedding_provider.py
│   ├── vector_store.py
│   ├── keyword_store.py
│   └── reranker.py
│
├── ingestion/
│   ├── __init__.py
│   ├── exceptions.py
│   ├── models.py
│   ├── pipeline.py
│   ├── sanitizer.py
│   ├── validator.py
│   ├── text_chunker.py
│   ├── ingest_offline.py
│   ├── readers/
│   │   ├── __init__.py
│   │   └── file_reader.py
│   └── parsers/
│       ├── __init__.py
│       ├── protocol.py
│       ├── file.py
│       └── text.py
│
└── evaluation/
    ├── __init__.py
    ├── evaluator.py
    ├── online_sampler.py
    ├── ragas_offline.py
    ├── datasets/
    ├── metrics/
    └── models/
```

  Component               Responsibility
  ----------------------- -------------------------------------------------------
  `models.py`             Canonical RAG domain models
  `embeddings.py`         Concrete embedding-provider implementation
  `indexer.py`            Chunk → embedding → indexing orchestration
  `hybrid_retriever.py`   Vector + keyword retrieval, RRF, reranking
  `pgvector_store.py`     PostgreSQL/pgvector adapter
  `keyword_store.py`      PostgreSQL keyword/BM25 adapter
  `reranker.py`           Cross-encoder reranking implementation
  `protocols/`            RAG capability contracts
  `ingestion/`            Document preprocessing and streaming chunk production
  `evaluation/`           RAG quality evaluation

------------------------------------------------------------------------

## Capability Contracts

RAG orchestration depends on capability protocols:

``` text
EmbeddingProviderProtocol
    ├── embed()
    └── embed_one()

VectorStoreProtocol
    ├── upsert()
    └── query()

KeywordStoreProtocol
    ├── upsert()
    └── query()

RerankerProtocol
    └── rerank()
```

Concrete implementations are injected into the RAG components.

This keeps RAG orchestration independent from specific models,
databases, and infrastructure implementations.

------------------------------------------------------------------------

# Ingestion and Indexing

## Ingestion Flow

The ingestion package transforms local legal source documents into
validated, security-screened chunks.

``` mermaid
flowchart TD
    A[Legal Source Directory] --> B[ingest_offline.py]
    B --> C[FileParser]
    C --> D[SecuritySanitizer]
    D --> E[ContentValidator]
    E --> F[TextChunker]
    F --> G[Iterator[Chunk]]
```

The pipeline is lazy and streaming:

``` text
Source
  ↓
Parser
  ↓
Security Sanitizer
  ↓
Content Validator
  ↓
Streaming Chunker
  ↓
Iterator[Chunk]
```

The ingestion flow does not intentionally accumulate complete documents,
parsed-block collections, or chunk collections.

Consume the stream one chunk at a time.

## Offline Ingestion

Supported source formats:

``` text
.pdf
.docx
.txt
.md
.html
.htm
```

Python entry point:

``` bash
python -m rag.ingestion.ingest_offline <source-directory>
```

Preferred shell interface:

``` bash
./scripts/ingest_offline.sh <source-directory>
```

The shell script is only a launcher and contains no ingestion business
logic.

## Indexing Flow

After ingestion produces chunks, indexing creates searchable
representations.

``` mermaid
flowchart TD
    A[Chunk] --> B[Indexer]
    B --> C[EmbeddingProvider.embed]
    C --> D[VectorStore.upsert]
    D --> E[PGVector]

    A --> F[KeywordStore.upsert]
    F --> G[BM25 / PostgreSQL Full Text]
```

The indexing path is:

``` text
Chunk
 │
 ├──→ EmbeddingProvider.embed()
 │           ↓
 │     VectorStore.upsert()
 │           ↓
 │        PGVector
 │
 └──→ KeywordStore.upsert()
             ↓
        BM25 / PostgreSQL
```

`EmbeddingRepresentation` records the model name, dimension, and vector
so representations from different embedding models remain
distinguishable.

------------------------------------------------------------------------

# Retrieval

## Vector Retrieval

`VectorStoreProtocol` owns both:

``` text
upsert()
query()
```

Therefore:

``` text
Indexing
    ↓
VectorStore.upsert()
    ↓
PGVector

Retrieval
    ↓
VectorStore.query()
    ↓
PGVector
```

`PgVectorStore` is the infrastructure adapter. PostgreSQL, pgvector,
SQLAlchemy, persistence repositories, and transactions remain outside
the RAG domain orchestration.

## Keyword / BM25 Retrieval

`KeywordStoreProtocol` owns:

``` text
upsert()
query()
```

The keyword path is:

``` text
Chunk
  ↓
KeywordStore.upsert()
  ↓
BM25 / PostgreSQL Full Text

Query
  ↓
KeywordStore.query()
  ↓
Keyword candidates
```

Keyword retrieval is independent of vector similarity.

## Hybrid Retrieval

`HybridRetriever` combines dense and keyword retrieval.

``` mermaid
flowchart TD
    A[Query] --> B[EmbeddingProvider.embed_one]
    B --> C[VectorStore.query]
    A --> D[KeywordStore.query]
    C --> E[Reciprocal Rank Fusion]
    D --> E
    E --> F[Candidate Pool]
    F --> G[CrossEncoderReranker]
    G --> H[RetrievalResult[]]
```

Vector and keyword retrieval run concurrently after the query embedding
is generated.

``` text
Query
  │
  ├──→ embed_one()
  │
  ├──→ VectorStore.query()
  │
  └──→ KeywordStore.query()
             │
             ↓
            RRF
             ↓
       Candidate Pool
             ↓
          Reranker
             ↓
     RetrievalResult[]
```

------------------------------------------------------------------------

## Reciprocal Rank Fusion

RRF combines independently ranked vector and keyword candidate lists.

``` text
RRF score = Σ 1 / (k + rank)
```

RRF combines rankings without requiring vector and keyword scores to
share the same numeric scale.

A chunk supported by both retrieval strategies receives contributions
from both rankings.

RRF determines candidate ordering before second-stage reranking.

The original `RetrievalResult` representation is preserved during
fusion.

## Cross-Encoder Reranking

The cross-encoder is the second-stage retrieval model.

``` text
Vector candidates
               → RRF → Candidate Pool → CrossEncoderReranker → Final Results
       /
Keyword candidates
```

The reranker evaluates:

``` text
(query, candidate.chunk.text)
```

jointly.

It changes the relevance score while preserving:

``` text
Chunk
EmbeddingRepresentation[]
```

It does not generate document embeddings, perform vector/keyword
retrieval, perform RRF, persist data, call the generation LLM, or
execute agents.

------------------------------------------------------------------------

# Complete RAG Data Plane

``` mermaid
flowchart TD
    A[Legal Corpus] --> B[Offline Ingestion]
    B --> C[Parser]
    C --> D[Sanitizer]
    D --> E[Validator]
    E --> F[Streaming Chunker]
    F --> G[Chunk]

    G --> H[Indexer]
    H --> I[EmbeddingProvider]
    I --> J[VectorStore.upsert]
    J --> K[PGVector]

    G --> L[KeywordStore.upsert]
    L --> M[BM25 / PostgreSQL]

    N[Query] --> O[EmbeddingProvider.embed_one]
    O --> P[VectorStore.query]
    N --> Q[KeywordStore.query]
    P --> R[RRF]
    Q --> R
    R --> S[CrossEncoderReranker]
    S --> T[RetrievalResult[]]
```

------------------------------------------------------------------------

# RAG and Agent / LLM Separation

RAG is a knowledge-retrieval capability available to the intelligence
plane.

``` mermaid
flowchart TD
    A[User Request] --> B[Agent]
    B --> C[RAG Capability]
    C --> D[HybridRetriever]
    D --> E[RetrievalResult[]]
    E --> B
    B --> F[Tools / MCP]
    B --> G[LLM]
    G --> H[Answer / Action]
```

  RAG Data Plane            Agent / LLM Intelligence Plane
  ------------------------- --------------------------------
  Parse documents           Reason about requests
  Sanitize content          Plan and decide actions
  Validate content          Execute workflows
  Chunk documents           Call RAG/tools/MCP
  Generate embeddings       Build reasoning context
  Index vectors             Invoke LLM
  Index keywords            Produce answer/action
  Vector retrieval          Manage agent state
  Keyword retrieval         Execute tools
  RRF fusion                Coordinate execution
  Cross-encoder reranking   ---
  RAG evaluation            ---

The generation LLM must remain outside the vector store, keyword store,
retriever, indexer, and reranker.

------------------------------------------------------------------------

# Agent-Time Retrieval

RAG retrieval occurs when an agent requires knowledge retrieval.

``` text
User Request
     ↓
Planner / Executor
     ↓
Agent
     ↓
Agent decides retrieval is required
     ↓
HybridRetriever
     ↓
RetrievalResult[]
     ↓
Agent Context
     ↓
LLM
     ↓
Answer / Action
```

RAG provides knowledge; the agent decides when and how to use it; the
LLM performs reasoning and generation.

------------------------------------------------------------------------

# Domain Models

`rag/models.py` is the canonical location for RAG domain models.

Important models include:

``` text
Chunk
EmbeddingRepresentation
RetrievalResult
IndexedRepresentation
```

`RetrievalResult` preserves the retrieved chunk, retrieval score, and
associated embedding representations.

RAG domain models must not depend on SQLAlchemy persistence entities.

------------------------------------------------------------------------

# Persistence Boundary

``` text
RAG
 │
 ├── Capability Protocols
 └── Domain Models
          │
          ↓
    Concrete Adapters
          │
          ↓
 Persistence Repositories
          │
          ↓
 PostgreSQL / PGVector
```

Persistence owns:

``` text
SQLAlchemy models
Repositories
Transactions
PostgreSQL
pgvector
Full-text search
Persistence relationships
```

RAG owns:

``` text
Retrieval semantics
Indexing orchestration
Embedding abstraction
Hybrid retrieval
RRF
Reranking
RAG domain representations
```

------------------------------------------------------------------------

# Evaluation

RAG evaluation is separate from retrieval execution.

The evaluation package supports:

``` text
Online evaluation
Offline evaluation
Golden datasets
RAGAS-based evaluation
Retrieval and answer quality metrics
```

Evaluation can consume `RetrievalResult` and embedding metadata without
becoming part of the retrieval algorithm.

------------------------------------------------------------------------

# Error Handling

RAG components use the RAG-specific exception hierarchy from:

``` text
core.exceptions.rag
```

Unexpected failures should be logged with stack traces and wrapped in
the appropriate RAG exception while preserving the original exception as
the cause.

Operational logs must not expose:

``` text
document secrets
credentials
tokens
sensitive document snippets
```

Prefer operational metadata such as:

``` text
source_id
chunk count
top_k
model name
candidate count
operation
```

------------------------------------------------------------------------

# Architecture Freeze

The RAG architecture is intentionally divided into two related but
separate responsibilities.

## Ingestion / Indexing

``` text
Corpus
  ↓
Parser
  ↓
Sanitizer
  ↓
Validator
  ↓
Chunker
  ↓
Chunk
  ↓
┌───────────────────────┐
│                       │
↓                       ↓
EmbeddingProvider     KeywordStore
↓                       ↓
VectorStore.upsert()   BM25
↓
PGVector
```

## Retrieval

``` text
Query
  ↓
EmbeddingProvider.embed_one()
  ↓
┌───────────────────────┐
│                       │
↓                       ↓
VectorStore.query()   KeywordStore.query()
│                       │
└──────────┬────────────┘
           ↓
          RRF
           ↓
     Candidate Pool
           ↓
  CrossEncoderReranker
           ↓
    RetrievalResult[]
```

## Intelligence Plane

``` text
User Request
     ↓
Planner
     ↓
Executor
     ↓
Agent
     ↓
RAG / Tools / MCP
     ↓
LLM
     ↓
Answer / Action
```

These boundaries are the current architecture baseline and should not be
collapsed.
