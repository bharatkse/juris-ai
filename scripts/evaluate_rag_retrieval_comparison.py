import asyncio
from pathlib import Path

from config.settings import Settings
from rag.embeddings import SentenceTransformerEmbeddingProvider
from rag.evaluation.datasets.loader import GoldenDatasetLoader
from rag.evaluation.metrics.mrr import MeanReciprocalRank
from rag.evaluation.metrics.precision import PrecisionAtK
from rag.evaluation.metrics.recall import RecallAtK
from rag.evaluation.retrieval_evaluator import RetrievalEvaluator
from rag.evaluation.retrieval_runner import RetrievalEvaluationRunner
from rag.keyword_store import PostgresKeywordStore
from rag.models import RetrievalResult
from rag.pgvector_store import PgVectorStore
from runtime.factories.rag import build_rag_pipeline

DATASET_PATH = Path(
    "tests/datasets/rag/evaluation/legal_retrieval_v1.json",
)
TOP_K = 5


class VectorRetriever:
    def __init__(
        self,
        *,
        vector_store: PgVectorStore,
        embedding_provider: SentenceTransformerEmbeddingProvider,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider

    async def retrieve(
        self,
        *,
        query: str,
        top_k: int,
        allowed_source_ids: set[str] | None = None,
    ) -> list[RetrievalResult]:
        embedding = await self._embedding_provider.embed_one(query)

        return await self._vector_store.query(
            vector=embedding.vector,
            top_k=top_k,
            embedding_model=embedding.model_name,
            allowed_source_ids=allowed_source_ids,
        )


class KeywordRetriever:
    def __init__(
        self,
        *,
        keyword_store: PostgresKeywordStore,
    ) -> None:
        self._keyword_store = keyword_store

    async def retrieve(
        self,
        *,
        query: str,
        top_k: int,
        allowed_source_ids: set[str] | None = None,
    ) -> list[RetrievalResult]:
        return await self._keyword_store.query(
            query=query,
            top_k=top_k,
            allowed_source_ids=allowed_source_ids,
        )


def build_evaluator() -> RetrievalEvaluator:
    return RetrievalEvaluator(
        metrics=[
            RecallAtK(k=TOP_K),
            PrecisionAtK(k=TOP_K),
            MeanReciprocalRank(),
        ],
    )


async def evaluate(name: str, retriever) -> None:
    dataset = GoldenDatasetLoader().load(
        path=DATASET_PATH,
    )

    runner = RetrievalEvaluationRunner(
        retriever=retriever,
        evaluator=build_evaluator(),
        top_k=TOP_K,
    )

    report = await runner.evaluate(
        dataset=dataset,
    )

    print(f"\n=== {name} ===")
    print(f"Cases:        {report.case_count}")
    print(f"Passed:       {report.passed_cases}")
    print(f"Failed:       {report.failed_cases}")
    print(f"Pass rate:    {report.pass_rate:.2%}")

    print("\nMean scores:")
    for metric, score in report.mean_scores.items():
        print(f"  {metric}: {score:.4f}")


async def main() -> None:
    settings = Settings()

    pipeline = build_rag_pipeline(
        settings=settings,
    )

    embedding_provider = SentenceTransformerEmbeddingProvider()

    vector_store = PgVectorStore()

    vector_retriever = VectorRetriever(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
    )

    keyword_retriever = KeywordRetriever(
        keyword_store=PostgresKeywordStore(),
    )

    await evaluate(
        "VECTOR",
        vector_retriever,
    )

    await evaluate(
        "KEYWORD",
        keyword_retriever,
    )

    await evaluate(
        "HYBRID",
        pipeline.hybrid_retriever,
    )


if __name__ == "__main__":
    asyncio.run(main())
