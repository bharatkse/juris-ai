"""
Unit tests for HarmfulContentJudge.
"""

from __future__ import annotations

import pytest

from agentic.guardrails.harmful_content import HarmfulContentJudge


def _judge(response: str):
    async def judge(prompt: str) -> str:
        return response

    return judge


@pytest.mark.asyncio
async def test_non_harmful_verdict_is_parsed() -> None:
    checker = HarmfulContentJudge(
        judge=_judge('{"harmful": false, "category": null, "reason": "Legal analysis."}'),
    )

    result = await checker.evaluate(content="The statute prohibits X under section Y.")

    assert result.harmful is False
    assert result.category is None


@pytest.mark.asyncio
async def test_harmful_verdict_is_parsed() -> None:
    checker = HarmfulContentJudge(
        judge=_judge('{"harmful": true, "category": "violence", "reason": "Explicit threat."}'),
    )

    result = await checker.evaluate(content="anything")

    assert result.harmful is True
    assert result.category == "violence"


@pytest.mark.asyncio
async def test_json_wrapped_in_markdown_fence_is_parsed() -> None:
    checker = HarmfulContentJudge(
        judge=_judge('```json\n{"harmful": false, "category": null, "reason": "fine"}\n```'),
    )

    result = await checker.evaluate(content="anything")

    assert result.harmful is False


@pytest.mark.asyncio
async def test_json_wrapped_in_prose_is_parsed() -> None:
    checker = HarmfulContentJudge(
        judge=_judge(
            'Sure, here is my verdict: {"harmful": false, "category": null, '
            '"reason": "fine"} -- hope that helps!'
        ),
    )

    result = await checker.evaluate(content="anything")

    assert result.harmful is False


@pytest.mark.asyncio
async def test_unparseable_verdict_fails_closed() -> None:
    """
    An unparsable judge response must count as harmful, not be
    silently treated as safe -- mirrors AnswerEvaluator's precedent for
    a failed groundedness judge call (fail closed, not open).
    """

    checker = HarmfulContentJudge(judge=_judge("not json at all"))

    result = await checker.evaluate(content="anything")

    assert result.harmful is True
    assert result.category == "judge_unavailable"


@pytest.mark.asyncio
async def test_non_object_json_fails_closed() -> None:
    checker = HarmfulContentJudge(judge=_judge("[1, 2, 3]"))

    result = await checker.evaluate(content="anything")

    assert result.harmful is True


@pytest.mark.asyncio
async def test_empty_content_short_circuits_without_calling_the_judge() -> None:
    calls: list[str] = []

    async def judge(prompt: str) -> str:
        calls.append(prompt)
        return '{"harmful": true}'

    checker = HarmfulContentJudge(judge=judge)

    result = await checker.evaluate(content="   ")

    assert result.harmful is False
    assert calls == []
