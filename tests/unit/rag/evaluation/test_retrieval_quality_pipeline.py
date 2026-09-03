from rag.evaluation.models.evaluation_result import EvaluationResult
from rag.evaluation.models.metric_result import MetricResult
from rag.evaluation.models.quality_gate import RetrievalQualityGate
from rag.evaluation.models.retrieval_report import RetrievalEvaluationReport


def _result(
    *,
    recall: float,
    precision: float,
    mrr: float,
) -> EvaluationResult:
    return EvaluationResult(
        metrics=[
            MetricResult(
                metric="recall@5",
                score=recall,
                passed=recall >= 0.6,
                metadata={},
            ),
            MetricResult(
                metric="precision@5",
                score=precision,
                passed=precision >= 0.6,
                metadata={},
            ),
            MetricResult(
                metric="mrr",
                score=mrr,
                passed=mrr > 0.0,
                metadata={},
            ),
        ],
        passed=(recall >= 0.6 and precision >= 0.6 and mrr > 0.0),
    )


def test_quality_gate_passes_for_acceptable_report() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(
                recall=0.8,
                precision=0.7,
                mrr=0.9,
            ),
            _result(
                recall=0.7,
                precision=0.8,
                mrr=0.5,
            ),
        ]
    )

    gate = RetrievalQualityGate(
        thresholds={
            "recall@5": 0.7,
            "precision@5": 0.6,
            "mrr": 0.5,
        }
    )

    result = gate.evaluate(report=report)

    assert result.passed is True
    assert result.failures == []


def test_quality_gate_fails_for_low_mean_retrieval_quality() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(
                recall=0.4,
                precision=0.8,
                mrr=0.5,
            ),
            _result(
                recall=0.6,
                precision=0.7,
                mrr=0.5,
            ),
        ]
    )

    gate = RetrievalQualityGate(
        thresholds={
            "recall@5": 0.6,
            "precision@5": 0.6,
            "mrr": 0.5,
        }
    )

    result = gate.evaluate(report=report)

    assert result.passed is False
    assert result.failures == [
        "recall@5: 0.5000 < required 0.6000",
    ]


def test_quality_gate_evaluates_mean_scores_across_cases() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(
                recall=1.0,
                precision=0.5,
                mrr=1.0,
            ),
            _result(
                recall=0.0,
                precision=1.0,
                mrr=0.0,
            ),
        ]
    )

    assert report.mean_scores == {
        "recall@5": 0.5,
        "precision@5": 0.75,
        "mrr": 0.5,
    }

    gate = RetrievalQualityGate(
        thresholds={
            "recall@5": 0.5,
            "precision@5": 0.7,
            "mrr": 0.5,
        }
    )

    result = gate.evaluate(report=report)

    assert result.passed is True
