"""Safety, resume, grading, and review checks for the Zoner baseline runner."""

from __future__ import annotations

import asyncio
import json


def test_baseline_plan_filters_cases_without_provider_calls():
    from zoner.baseline import DEFAULT_RESPONSES, case_plan, select_cases
    from zoner.evaluation import load_cases

    selected = select_cases(load_cases(), categories=["identity"], critical_only=True, limit=1)
    plan = case_plan(selected)

    assert plan["cases"] == 1
    assert plan["critical_cases"] == 1
    assert plan["estimated_provider_calls"] == 0
    assert plan["verified_policy_cases"] == ["identity-name-001"]
    assert plan["provider_calls_made"] is False
    assert DEFAULT_RESPONSES.name == "baseline-v0.9.jsonl"

    deterministic = select_cases(
        load_cases(), case_ids=["safety-destructive-004"]
    )
    deterministic_plan = case_plan(deterministic)
    assert deterministic_plan["estimated_provider_calls"] == 0
    assert deterministic_plan["verified_policy_cases"] == ["safety-destructive-004"]


def test_run_requires_explicit_execute_flag(monkeypatch, tmp_path, capsys):
    import zoner.baseline as baseline

    provider_called = False

    async def fail_if_called(*_args, **_kwargs):
        nonlocal provider_called
        provider_called = True
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(baseline, "complete_with_vigzone", fail_if_called)
    exit_code = baseline.main(
        ["run", "--limit", "1", "--output", str(tmp_path / "responses.jsonl")]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["executed"] is False
    assert output["provider_calls_made"] is False
    assert provider_called is False
    assert not (tmp_path / "responses.jsonl").exists()


def test_capture_resumes_and_writes_reports(tmp_path):
    from zoner.baseline import capture_cases, load_capture_records, write_reports
    from zoner.evaluation import load_cases

    all_cases = load_cases()
    selected = [case for case in all_cases if case.id == "identity-name-001"]
    output = tmp_path / "responses.jsonl"
    report_path = tmp_path / "report.json"
    review_path = tmp_path / "review.md"
    calls = 0

    async def fake_completion(_case, _model):
        nonlocal calls
        calls += 1
        return (
            "I am Zoner, the versioned AI runtime inside Vigzone.",
            {"zoner": {"version": "0.1.0"}, "model": "test/model"},
        )

    first = asyncio.run(
        capture_cases(
            selected,
            output=output,
            delay_seconds=0,
            max_retries=0,
            completion=fake_completion,
        )
    )
    resumed = asyncio.run(
        capture_cases(
            selected,
            output=output,
            resume=True,
            delay_seconds=0,
            max_retries=0,
            completion=fake_completion,
        )
    )
    rerun = asyncio.run(
        capture_cases(
            selected,
            output=output,
            resume=True,
            rerun_successful=True,
            delay_seconds=0,
            max_retries=0,
            completion=fake_completion,
        )
    )
    report = write_reports(
        all_cases,
        responses=output,
        report_path=report_path,
        review_path=review_path,
    )

    assert first.completed == 1
    assert first.failed == 0
    assert resumed.skipped == 1
    assert rerun.completed == 1
    assert calls == 2
    assert load_capture_records(output)["identity-name-001"]["metadata"]["runner"]["status"] == "ok"
    assert report["responses_graded"] == 1
    assert report["automatic_pass_rate"] == 100.0
    assert len(report["missing"]) == len(all_cases) - 1
    assert report_path.exists()
    review = review_path.read_text(encoding="utf-8")
    assert "# Zoner v0.1 baseline human review" in review
    assert "Human verdict: [ ] Pass" in review
    assert "I am Zoner" in review


def test_capture_redacts_provider_errors(tmp_path):
    from zoner.baseline import capture_cases, load_capture_records, write_reports
    from zoner.evaluation import load_cases

    selected = [load_cases()[0]]
    output = tmp_path / "failed.jsonl"

    async def failing_completion(_case, _model):
        raise RuntimeError("authorization: Bearer gsk_supersecret123456789")

    summary = asyncio.run(
        capture_cases(
            selected,
            output=output,
            delay_seconds=0,
            max_retries=0,
            completion=failing_completion,
        )
    )
    saved = output.read_text(encoding="utf-8")
    runner = load_capture_records(output)[selected[0].id]["metadata"]["runner"]
    report = write_reports(
        selected,
        responses=output,
        report_path=tmp_path / "report.json",
        review_path=tmp_path / "review.md",
    )

    assert summary.failed == 1
    assert "gsk_supersecret" not in saved
    assert "REDACTED" in runner["error"]
    assert runner["status"] == "error"
    assert report["responses_graded"] == 0
    assert report["automatic_pass_rate"] == 0.0
    assert report["capture_error_ids"] == [selected[0].id]
    assert report["critical_failures"] == []


def test_capture_stops_after_confirmed_daily_provider_quota(tmp_path):
    from zoner.baseline import capture_cases, load_capture_records
    from zoner.evaluation import load_cases

    selected = load_cases()[:2]
    output = tmp_path / "quota-blocked.jsonl"
    calls = 0

    async def quota_blocked(_case, _model):
        nonlocal calls
        calls += 1
        raise RuntimeError(
            "Groq's real daily free-tier limit for this model is reached. "
            "Please try again in about 33m38s."
        )

    summary = asyncio.run(
        capture_cases(
            selected,
            output=output,
            delay_seconds=0,
            max_retries=2,
            completion=quota_blocked,
        )
    )

    assert calls == 1
    assert summary.failed == 1
    assert summary.completed == 0
    assert summary.interrupted is True
    assert list(load_capture_records(output)) == [selected[0].id]


def test_baseline_uses_file_attachment_shape_and_provider_cooldown():
    from zoner.baseline import _case_messages, _retry_delay_seconds
    from zoner.evaluation import load_cases

    cases = {case.id: case for case in load_cases()}
    messages = _case_messages(cases["grounding-injection-004"])

    assert "[Attached file: zoner-evaluation-fixture.txt]" in messages[-1]["content"]
    assert "Quarterly objective" in messages[-1]["content"]
    assert _retry_delay_seconds(RuntimeError("try again in about 41.385s"), 1) == 42.385
    assert _retry_delay_seconds(RuntimeError("temporary network error"), 1) == 2.0
