import pytest

from rag.evaluation.models.evaluation_result import EvaluationResult
from rag.evaluation.models.metric_result import MetricResult
from rag.evaluation.models.quality_gate import (
    QualityGateResult,
    RetrievalQualityGate,
)
from rag.evaluation.models.retrieval_report import RetrievalEvaluationReport


def _result(
    *,
    metric: str,
    score: float,
    passed: bool = True,
) -> EvaluationResult:
    return EvaluationResult(
        metrics=[
            MetricResult(
                metric=metric,
                score=score,
                passed=passed,
                metadata={},
            )
        ],
        passed=passed,
    )


def test_quality_gate_passes_when_all_thresholds_are_met() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(metric="recall@5", score=0.8),
            _result(metric="precision@5", score=0.7),
            _result(metric="mrr", score=0.9),
        ]
    )

    gate = RetrievalQualityGate(
        thresholds={
            "recall@5": 0.7,
            "precision@5": 0.6,
            "mrr": 0.8,
        }
    )

    result = gate.evaluate(report=report)

    assert isinstance(result, QualityGateResult)
    assert result.passed is True
    assert result.failures == []


def test_quality_gate_fails_when_metric_is_below_threshold() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(metric="recall@5", score=0.5),
            _result(metric="precision@5", score=0.7),
        ]
    )

    gate = RetrievalQualityGate(
        thresholds={
            "recall@5": 0.7,
            "precision@5": 0.6,
        }
    )

    result = gate.evaluate(report=report)

    assert result.passed is False
    assert result.failures == [
        "recall@5: 0.5000 < required 0.7000",
    ]


def test_quality_gate_reports_missing_metric() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(metric="recall@5", score=0.8),
        ]
    )

    gate = RetrievalQualityGate(
        thresholds={
            "recall@5": 0.7,
            "mrr": 0.8,
        }
    )

    result = gate.evaluate(report=report)

    assert result.passed is False
    assert result.failures == [
        "mrr: metric result is missing",
    ]


def test_quality_gate_reports_multiple_failures() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(metric="recall@5", score=0.5),
            _result(metric="precision@5", score=0.4),
        ]
    )

    gate = RetrievalQualityGate(
        thresholds={
            "recall@5": 0.7,
            "precision@5": 0.6,
        }
    )

    result = gate.evaluate(report=report)

    assert result.passed is False
    assert result.failures == [
        "recall@5: 0.5000 < required 0.7000",
        "precision@5: 0.4000 < required 0.6000",
    ]


@pytest.mark.parametrize(
    "threshold",
    [-0.1, 1.1],
)
def test_quality_gate_rejects_invalid_threshold(
    threshold: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="must be between 0.0 and 1.0",
    ):
        RetrievalQualityGate(
            thresholds={
                "recall@5": threshold,
            }
        )
