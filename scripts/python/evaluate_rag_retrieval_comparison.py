import asyncio
from pathlib import Path

from config.settings import Settings
from rag.embeddings import SentenceTransformerEmbeddingProvider
from rag.evaluation.datasets.loader import GoldenDatasetLoader
from rag.evaluation.metrics.faithfulness import FaithfulnessMetric
from rag.evaluation.metrics.mrr import MeanReciprocalRank
from rag.evaluation.metrics.precision import PrecisionAtK
from rag.evaluation.metrics.recall import RecallAtK
from rag.evaluation.retrieval_evaluator import RetrievalEvaluator
from rag.evaluation.retrieval_runner import RetrievalEvaluationRunner
from rag.keyword_store import PostgresKeywordStore
from rag.models import RetrievalResult
from rag.pgvector_store import PgVectorStore
from wiring.factories.evaluation import build_faithfulness_backend
from wiring.factories.rag import build_rag_pipeline

DATASET_PATH = Path(
    "tests/datasets/rag/evaluation/legal_retrieval_gold_v1.json",
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
    ) -> list[RetrievalResult]:
        embedding = await self._embedding_provider.embed_one(query)

        return await self._vector_store.query(
            vector=embedding.vector, top_k=top_k, embedding_model=embedding.model_name
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
    ) -> list[RetrievalResult]:
        return await self._keyword_store.query(
            query=query,
            top_k=top_k,
        )


def build_evaluator(*, settings: Settings) -> RetrievalEvaluator:
    return RetrievalEvaluator(
        metrics=[
            RecallAtK(k=TOP_K),
            PrecisionAtK(k=TOP_K),
            MeanReciprocalRank(),
            # NOTE: the golden dataset has no populated `answer` field
            # for any case today, so this always reports "no generated
            # answer" with passed=True (not applicable, not a failure --
            # see faithfulness.py) until the dataset (or this script)
            # produces real answers. score stays 0.0 and is visible in
            # mean_scores, but it does NOT drag down passed_cases/
            # pass_rate. Wired in now so it activates automatically
            # once that gap is closed.
            FaithfulnessMetric(backend=build_faithfulness_backend(settings=settings)),
        ],
    )


async def evaluate(name: str, retriever, *, settings: Settings) -> None:
    dataset = GoldenDatasetLoader().load(
        path=DATASET_PATH,
    )

    runner = RetrievalEvaluationRunner(
        retriever=retriever,
        evaluator=build_evaluator(settings=settings),
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
        settings=settings,
    )

    await evaluate(
        "KEYWORD",
        keyword_retriever,
        settings=settings,
    )

    await evaluate(
        "HYBRID",
        pipeline.hybrid_retriever,
        settings=settings,
    )


if __name__ == "__main__":
    asyncio.run(main())
