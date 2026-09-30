"""
Unit tests: scripts/python/evaluate_rag_retrieval.py.

The CI golden-set eval (rag-eval.yaml) must measure the retrieval mode it
asks for. With the embedding model or its cache unreachable, it used to
report keyword-only scores as the hybrid pass rate. Now a search in the
wrong mode stops the run (exit 2) and prints the underlying error once;
a pass rate below --min-pass-rate exits 1. The database, models and cache
are replaced by fakes; the real HybridRetriever runs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

SERVER = Path(__file__).resolve().parents[3]
SCRIPT = SERVER / "scripts" / "python" / "evaluate_rag_retrieval.py"
DATASET = SERVER / "tests" / "datasets" / "rag" / "evaluation" / "legal_retrieval_gold_v1.json"


@pytest.fixture(scope="module")
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("evaluate_rag_retrieval", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Metadata:
    model_name = "test-embedder"


class _Embedder:
    metadata = _Metadata()

    def __init__(self, *, fails: bool) -> None:
        self.fails = fails

    async def embed(self, *, texts):
        return [await self.embed_one(text=text) for text in texts]

    async def embed_one(self, *, text):
        if self.fails:
            raise ConnectionError("Error 111 connecting to localhost:6379.")
        return [0.1, 0.2]


class _Store:
    async def upsert(self, **_):
        return None

    async def query(self, **_):
        return []


class _Reranker:
    async def rerank(self, *, query, candidates, top_k):
        return candidates[:top_k]


@pytest.fixture
def fakes(script: ModuleType, monkeypatch: pytest.MonkeyPatch):
    def install(*, embedder_fails: bool) -> None:
        monkeypatch.setattr(script, "DATASET_PATH", DATASET)
        monkeypatch.setattr(
            script, "Settings", lambda: SimpleNamespace(llm=SimpleNamespace(rag_rrf_k=60))
        )
        monkeypatch.setattr(script, "build_cache", lambda **_: object())
        monkeypatch.setattr(
            script,
            "build_rag_pipeline",
            lambda **_: SimpleNamespace(embedding_provider=_Embedder(fails=embedder_fails)),
        )
        monkeypatch.setattr(script, "build_faithfulness_backend", lambda **_: None)
        monkeypatch.setattr(script, "PgVectorStore", _Store)
        monkeypatch.setattr(script, "PostgresKeywordStore", _Store)
        monkeypatch.setattr(script, "CrossEncoderReranker", _Reranker)

    return install


def test_mode_defaults_to_full(script: ModuleType) -> None:
    args = script.parse_args([])

    assert args.mode == "full"
    assert args.min_pass_rate is None
    assert args.summary is None


def test_an_unknown_mode_is_rejected(script: ModuleType) -> None:
    with pytest.raises(SystemExit):
        script.parse_args(["--mode", "vector_only"])


async def test_full_mode_exits_2_and_prints_the_cause_when_embeddings_fail(
    script: ModuleType, fakes, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    fakes(embedder_fails=True)
    summary = tmp_path / "summary.md"

    code = await script.main(
        script.parse_args(["--min-pass-rate", "65", "--summary", str(summary)])
    )

    err = capsys.readouterr().err
    assert code == script.EXIT_WRONG_MODE
    assert "requested full but used keyword_only" in err
    assert "Traceback" in err
    assert "ConnectionError: Error 111 connecting to localhost:6379." in err
    assert "Pass rate" not in capsys.readouterr().out
    assert not summary.exists()


async def test_keyword_only_mode_reports_and_writes_the_summary(
    script: ModuleType, fakes, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    fakes(embedder_fails=True)
    summary = tmp_path / "summary.md"

    code = await script.main(
        script.parse_args(["--mode", "keyword_only", "--summary", str(summary)])
    )

    out = capsys.readouterr().out
    assert code == 0
    assert "Mode:          requested keyword_only; used keyword_only (29)" in out
    assert "Pass rate:" in out
    assert "### Retrieval eval: `keyword_only`" in summary.read_text()
    assert "(not gating)" in summary.read_text()


async def test_a_pass_rate_below_the_gate_exits_1(
    script: ModuleType, fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    # The fake stores find nothing, so every case fails.
    fakes(embedder_fails=False)

    code = await script.main(script.parse_args(["--min-pass-rate", "65"]))

    assert code == script.EXIT_BELOW_GATE
    assert "below the 65.0% gate (full)" in capsys.readouterr().err
