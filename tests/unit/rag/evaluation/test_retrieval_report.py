from rag.evaluation.models.evaluation_result import EvaluationResult
from rag.evaluation.models.metric_result import MetricResult
from rag.evaluation.models.retrieval_report import RetrievalEvaluationReport


def _result(
    *,
    metrics: list[MetricResult],
    passed: bool,
) -> EvaluationResult:
    return EvaluationResult(
        metrics=metrics,
        passed=passed,
    )


def test_report_counts_cases() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(metrics=[], passed=True),
            _result(metrics=[], passed=False),
            _result(metrics=[], passed=True),
        ]
    )

    assert report.case_count == 3
    assert report.passed_cases == 2
    assert report.failed_cases == 1


def test_report_calculates_pass_rate() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(metrics=[], passed=True),
            _result(metrics=[], passed=False),
            _result(metrics=[], passed=True),
            _result(metrics=[], passed=True),
        ]
    )

    assert report.pass_rate == 0.75


def test_report_calculates_mean_scores() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(
                metrics=[
                    MetricResult(
                        metric="recall@5",
                        score=0.8,
                        passed=True,
                        metadata={},
                    ),
                    MetricResult(
                        metric="precision@5",
                        score=0.6,
                        passed=True,
                        metadata={},
                    ),
                ],
                passed=True,
            ),
            _result(
                metrics=[
                    MetricResult(
                        metric="recall@5",
                        score=0.6,
                        passed=True,
                        metadata={},
                    ),
                    MetricResult(
                        metric="precision@5",
                        score=0.4,
                        passed=False,
                        metadata={},
                    ),
                ],
                passed=False,
            ),
        ]
    )

    assert report.mean_scores == {
        "recall@5": 0.7,
        "precision@5": 0.5,
    }


def test_report_passed_when_all_cases_pass() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(metrics=[], passed=True),
            _result(metrics=[], passed=True),
        ]
    )

    assert report.passed is True


def test_report_fails_when_any_case_fails() -> None:
    report = RetrievalEvaluationReport(
        results=[
            _result(metrics=[], passed=True),
            _result(metrics=[], passed=False),
        ]
    )

    assert report.passed is False


def test_empty_report_has_zero_pass_rate() -> None:
    report = RetrievalEvaluationReport()

    assert report.case_count == 0
    assert report.passed_cases == 0
    assert report.failed_cases == 0
    assert report.pass_rate == 0.0
