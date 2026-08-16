"""Safe, resumable baseline capture for the Zoner evaluation corpus.

Planning, checking, and reporting are offline. Provider calls happen only when
the ``run`` command receives the explicit ``--execute`` flag. Results are
written atomically after every case so an interrupted free-tier run can resume
without repeating successful requests.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .evaluation import (
    DEFAULT_DATASET,
    EvalCase,
    EvaluationDataError,
    dataset_summary,
    grade_saved_responses,
    load_cases,
)
from .profile import ZONER_PROFILE


DEFAULT_RESULTS_DIR = Path(__file__).with_name("results")
BASELINE_PROMPT_REVISION = ZONER_PROFILE.prompt_bundle_version.removeprefix("zoner-prompt-")
DEFAULT_RESPONSES = DEFAULT_RESULTS_DIR / f"baseline-{BASELINE_PROMPT_REVISION}.jsonl"
DEFAULT_REPORT = DEFAULT_RESULTS_DIR / f"baseline-{BASELINE_PROMPT_REVISION}-report.json"
DEFAULT_REVIEW = DEFAULT_RESULTS_DIR / f"baseline-{BASELINE_PROMPT_REVISION}-review.md"

CompletionFunction = Callable[[EvalCase, str], Awaitable[tuple[str, dict[str, Any]]]]


@dataclass(frozen=True)
class CaptureSummary:
    selected: int
    completed: int
    failed: int
    skipped: int
    interrupted: bool
    output: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_records(path: Path, records: Mapping[str, Mapping[str, Any]], case_order: Sequence[str]) -> None:
    ordered_ids = [case_id for case_id in case_order if case_id in records]
    ordered_ids.extend(sorted(set(records) - set(ordered_ids)))
    content = "".join(
        json.dumps(records[case_id], ensure_ascii=False, separators=(",", ":")) + "\n"
        for case_id in ordered_ids
    )
    _atomic_write_text(path, content)


def load_capture_records(path: str | Path) -> dict[str, dict[str, Any]]:
    capture_path = Path(path)
    if not capture_path.exists():
        return {}
    if not capture_path.is_file():
        raise EvaluationDataError(f"capture path is not a file: {capture_path}")
    records: dict[str, dict[str, Any]] = {}
    with capture_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvaluationDataError(f"capture line {line_number}: invalid JSON") from exc
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise EvaluationDataError(f"capture line {line_number}: string id is required")
            if not isinstance(item.get("response"), str) or not isinstance(item.get("metadata", {}), dict):
                raise EvaluationDataError(
                    f"capture {item['id']}: response text and metadata object are required"
                )
            if item["id"] in records:
                raise EvaluationDataError(f"duplicate capture id: {item['id']}")
            records[item["id"]] = item
    return records


def select_cases(
    cases: Sequence[EvalCase],
    *,
    categories: Sequence[str] = (),
    case_ids: Sequence[str] = (),
    critical_only: bool = False,
    limit: int | None = None,
) -> list[EvalCase]:
    category_filter = {item.strip() for item in categories if item.strip()}
    id_filter = {item.strip() for item in case_ids if item.strip()}
    selected = [
        case
        for case in cases
        if (not category_filter or case.category in category_filter)
        and (not id_filter or case.id in id_filter)
        and (not critical_only or case.critical)
    ]
    if id_filter:
        missing_ids = id_filter - {case.id for case in selected}
        if missing_ids:
            raise EvaluationDataError(f"unknown or filtered case ids: {sorted(missing_ids)}")
    if limit is not None:
        if limit < 1:
            raise EvaluationDataError("limit must be at least 1")
        selected = selected[:limit]
    if not selected:
        raise EvaluationDataError("no evaluation cases matched the selected filters")
    return selected


def case_plan(cases: Sequence[EvalCase]) -> dict[str, Any]:
    import vigzone_ai

    verified_policy_cases = [
        case.id
        for case in cases
        if vigzone_ai.verified_product_response(_case_messages(case)) is not None
    ]
    return {
        **dataset_summary(cases),
        "estimated_provider_calls": len(cases) - len(verified_policy_cases),
        "verified_policy_cases": verified_policy_cases,
        "case_ids": [case.id for case in cases],
        "provider_calls_made": False,
    }


def _case_context(case: EvalCase) -> dict[str, str]:
    context = {
        key: value
        for key, value in case.context.items()
        if key in {"workspace", "memory", "persona"} and value.strip()
    }
    reference_blocks: list[str] = []
    if case.context.get("live", "").strip():
        reference_blocks.append("EVALUATION LIVE TOOL RESULT\n" + case.context["live"].strip())
    if reference_blocks:
        existing = context.get("workspace", "").strip()
        context["workspace"] = "\n\n".join(item for item in [existing, *reference_blocks] if item)
    return context


def _case_messages(case: EvalCase) -> list[dict[str, str]]:
    """Render file fixtures through the same inline attachment shape as Vigzone chat."""

    messages = [dict(message) for message in case.messages]
    file_text = case.context.get("file", "").strip()
    if not file_text:
        return messages
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get("role") == "user":
            messages[index]["content"] = (
                messages[index]["content"].rstrip()
                + '\n\n[Attached file: zoner-evaluation-fixture.txt]\n"""\n'
                + file_text
                + '\n"""'
            )
            return messages
    raise EvaluationDataError(f"{case.id}: file fixture requires a user message")


def _routing_mode(case: EvalCase) -> str:
    if case.category == "coding":
        return "code"
    if case.category in {"grounding", "retrieval"}:
        return "file"
    return "general"


async def complete_with_vigzone(case: EvalCase, model: str) -> tuple[str, dict[str, Any]]:
    """Run one case through the same payload builder/provider path as Vigzone chat."""

    load_dotenv()
    import vigzone_ai

    if not vigzone_ai.API_KEY:
        raise EvaluationDataError(
            "GROQ_API_KEY is not configured. Add it to the project .env before using --execute."
        )
    selected_model = model.strip() or vigzone_ai.FAST_MODEL
    if selected_model not in vigzone_ai.ALLOWED_CHAT_MODELS:
        raise EvaluationDataError(f"model is not allowlisted by Vigzone: {selected_model}")
    metadata: dict[str, Any] = {}
    response = await vigzone_ai.chat_once(
        _case_messages(case),
        model=selected_model,
        user_name="Zoner Evaluation",
        context_parts=_case_context(case),
        feature_policy={
            "website_studio": True,
            "image_search": True,
            "premium_modes": True,
        },
        routing_mode=_routing_mode(case),
        conversation_id=f"zoner-eval:{case.id}",
        metadata_callback=metadata.update,
        allowed_models={selected_model},
    )
    return response, metadata


_SECRET_PATTERNS = (
    (re.compile(r"\bgsk_[A-Za-z0-9_-]{8,}"), "[REDACTED_GROQ_KEY]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"), "[REDACTED_API_KEY]"),
    (
        re.compile(r"(?i)\b(authorization|api[_ -]?key|encryption[_ -]?secret)\b\s*[:=]\s*\S+"),
        r"\1=[REDACTED]",
    ),
)


def sanitize_error(error: BaseException) -> str:
    text = str(error).replace("\x00", " ").strip() or error.__class__.__name__
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:800]


_RETRY_AFTER_PATTERN = re.compile(
    r"try again in (?:about )?([0-9]+(?:\.[0-9]+)?)s",
    re.IGNORECASE,
)


def _retry_delay_seconds(error: BaseException, attempt: int) -> float:
    """Respect provider cooldown hints while keeping retries bounded."""

    fallback = min(8.0, max(2.0, 2.0 * attempt))
    match = _RETRY_AFTER_PATTERN.search(str(error))
    if not match:
        return fallback
    return min(60.0, max(fallback, float(match.group(1)) + 1.0))


def _successful(record: Mapping[str, Any] | None) -> bool:
    if not record or not str(record.get("response") or "").strip():
        return False
    metadata = record.get("metadata") or {}
    runner = metadata.get("runner") if isinstance(metadata, Mapping) else None
    return not isinstance(runner, Mapping) or runner.get("status") == "ok"


def _daily_provider_quota_exhausted(error_text: str) -> bool:
    """Return true when retrying more cases cannot make useful progress."""

    normalized = error_text.casefold()
    return any(
        marker in normalized
        for marker in (
            "daily free-tier limit",
            "tokens per day",
            " tpd ",
        )
    )


def _captured_prompt_versions(records: Mapping[str, Mapping[str, Any]]) -> set[str]:
    versions: set[str] = set()
    for record in records.values():
        metadata = record.get("metadata") or {}
        zoner = metadata.get("zoner") if isinstance(metadata, Mapping) else None
        if isinstance(zoner, Mapping):
            version = str(zoner.get("prompt_bundle_version") or "").strip()
            if version:
                versions.add(version)
    return versions


async def capture_cases(
    cases: Sequence[EvalCase],
    *,
    output: str | Path = DEFAULT_RESPONSES,
    model: str = "",
    resume: bool = False,
    overwrite: bool = False,
    rerun_successful: bool = False,
    delay_seconds: float = 2.0,
    max_retries: int = 2,
    completion: CompletionFunction = complete_with_vigzone,
) -> CaptureSummary:
    output_path = Path(output)
    if delay_seconds < 0:
        raise EvaluationDataError("delay must not be negative")
    if max_retries < 0 or max_retries > 5:
        raise EvaluationDataError("max retries must be between 0 and 5")
    if resume and overwrite:
        raise EvaluationDataError("resume and overwrite cannot be used together")
    if rerun_successful and not resume:
        raise EvaluationDataError("rerunning successful cases requires resume mode")
    if output_path.exists() and not resume and not overwrite:
        raise EvaluationDataError(
            f"capture already exists: {output_path}. Use --resume or --overwrite explicitly."
        )
    records = load_capture_records(output_path) if resume else {}
    captured_prompt_versions = _captured_prompt_versions(records)
    active_prompt_version = ZONER_PROFILE.prompt_bundle_version
    if captured_prompt_versions and captured_prompt_versions != {active_prompt_version}:
        raise EvaluationDataError(
            "capture prompt version mismatch: found "
            f"{sorted(captured_prompt_versions)}, active is {active_prompt_version}. "
            "Choose a new --output file so evaluation configurations are not mixed."
        )
    case_order = [case.id for case in cases]
    completed = failed = skipped = 0
    interrupted = False

    try:
        for index, case in enumerate(cases):
            if resume and _successful(records.get(case.id)) and not rerun_successful:
                skipped += 1
                continue
            started = time.perf_counter()
            error_text = ""
            response = ""
            metadata: dict[str, Any] = {}
            attempts = 0
            cooldown_after_error = 0.0
            while attempts <= max_retries:
                attempts += 1
                try:
                    response, metadata = await completion(case, model)
                    if not response.strip():
                        raise EvaluationDataError("Zoner returned an empty response")
                    error_text = ""
                    break
                except (KeyboardInterrupt, asyncio.CancelledError):
                    raise
                except Exception as exc:
                    error_text = sanitize_error(exc)
                    cooldown_after_error = _retry_delay_seconds(exc, attempts)
                    if _daily_provider_quota_exhausted(error_text):
                        break
                    if attempts <= max_retries:
                        await asyncio.sleep(cooldown_after_error)
            duration_ms = max(1, int((time.perf_counter() - started) * 1000))
            runner_metadata = {
                "status": "error" if error_text else "ok",
                "attempts": attempts,
                "duration_ms": duration_ms,
                "captured_at": _utc_now(),
                "requested_model": model or "vigzone_fast_default",
                "error": error_text or None,
            }
            safe_metadata = dict(metadata) if isinstance(metadata, dict) else {}
            safe_metadata.setdefault("zoner", ZONER_PROFILE.runtime_metadata())
            safe_metadata["runner"] = runner_metadata
            records[case.id] = {
                "id": case.id,
                "response": response if not error_text else "",
                "metadata": safe_metadata,
            }
            _write_records(output_path, records, case_order)
            if error_text:
                failed += 1
                if _daily_provider_quota_exhausted(error_text):
                    interrupted = True
                    break
            else:
                completed += 1
            if index < len(cases) - 1:
                next_delay = max(delay_seconds, cooldown_after_error if error_text else 0.0)
                if next_delay:
                    await asyncio.sleep(next_delay)
    except (KeyboardInterrupt, asyncio.CancelledError):
        interrupted = True

    return CaptureSummary(
        selected=len(cases),
        completed=completed,
        failed=failed,
        skipped=skipped,
        interrupted=interrupted,
        output=str(output_path),
    )


def _responses_for_grading(records: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        case_id: {
            "response": str(record.get("response") or ""),
            "metadata": dict(record.get("metadata") or {}),
        }
        for case_id, record in records.items()
        if _successful(record)
    }


def _capture_errors(records: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for case_id, record in records.items():
        if _successful(record):
            continue
        metadata = record.get("metadata") or {}
        runner = metadata.get("runner") if isinstance(metadata, Mapping) else {}
        if isinstance(runner, Mapping) and runner.get("status") == "error":
            errors.append(
                {
                    "id": case_id,
                    "attempts": int(runner.get("attempts") or 0),
                    "error": str(runner.get("error") or "capture failed"),
                }
            )
    return errors


def _capture_component_versions(
    records: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[str]]:
    fields = (
        "version",
        "prompt_bundle_version",
        "retrieval_policy_version",
        "tool_policy_version",
        "evaluation_suite_version",
    )
    observed = {field: set() for field in fields}
    for record in records.values():
        metadata = record.get("metadata") or {}
        zoner = metadata.get("zoner") if isinstance(metadata, Mapping) else None
        if not isinstance(zoner, Mapping):
            continue
        for field in fields:
            value = str(zoner.get(field) or "").strip()
            if value:
                observed[field].add(value)
    return {field: sorted(values) for field, values in observed.items()}


def _review_markdown(
    cases: Sequence[EvalCase],
    records: Mapping[str, Mapping[str, Any]],
    report: Mapping[str, Any],
) -> str:
    results = {item["id"]: item for item in report.get("results", [])}
    capture_error_ids = set(report.get("capture_error_ids", []))
    unattempted_ids = set(report.get("unattempted", []))
    lines = [
        "# Zoner v0.1 baseline human review",
        "",
        f"Generated: {_utc_now()}",
        f"Automatic pass rate: {report.get('automatic_pass_rate', 0)}%",
        f"Critical automatic failures: {len(report.get('critical_failures', []))}",
        f"Missing responses: {len(report.get('missing', []))}",
        "",
        "Mark one verdict for every completed case. Automatic checks are signals, not a replacement for judgment.",
        "",
    ]
    for case in cases:
        record = records.get(case.id) or {}
        response = str(record.get("response") or "")
        result = results.get(case.id) or {}
        checks = result.get("checks") or []
        latest_prompt = case.messages[-1]["content"]
        lines.extend(
            [
                f"## {case.id}",
                "",
                f"- Category: `{case.category}`",
                f"- Critical: `{'yes' if case.critical else 'no'}`",
                "- Automatic result: `"
                + (
                    "CAPTURE ERROR"
                    if case.id in capture_error_ids
                    else "NOT CAPTURED"
                    if case.id in unattempted_ids
                    else "PASS"
                    if result.get("passed")
                    else "FAIL"
                )
                + "`",
                "- Human verdict: [ ] Pass  [ ] Fail  [ ] Needs discussion",
                "- Reviewer notes:",
                "",
                "### Prompt",
                "",
                f"<pre>{html.escape(latest_prompt)}</pre>",
                "",
                "### Zoner response",
                "",
                f"<pre>{html.escape(response or '[missing]')}</pre>",
                "",
                "### Automatic checks",
                "",
            ]
        )
        if checks:
            lines.extend(
                f"- {'PASS' if check.get('passed') else 'FAIL'} — {check.get('detail', '')}"
                for check in checks
            )
        else:
            lines.append("- No response was available for automatic grading.")
        lines.extend(["", "### Human rubric", ""])
        lines.extend(f"- {criterion}" for criterion in case.human_rubric)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_reports(
    cases: Sequence[EvalCase],
    *,
    responses: str | Path = DEFAULT_RESPONSES,
    report_path: str | Path = DEFAULT_REPORT,
    review_path: str | Path = DEFAULT_REVIEW,
) -> dict[str, Any]:
    records = load_capture_records(responses)
    report = grade_saved_responses(cases, _responses_for_grading(records))
    capture_errors = _capture_errors(records)
    report["capture_errors"] = capture_errors
    report["capture_error_ids"] = [item["id"] for item in capture_errors]
    report["unattempted"] = [case.id for case in cases if case.id not in records]
    report["capture_successes"] = report["responses_graded"]
    report["capture_completion_rate"] = round(
        report["responses_graded"] / len(cases) * 100 if cases else 0.0,
        2,
    )
    report["active_zoner"] = ZONER_PROFILE.runtime_metadata()
    report["capture_component_versions"] = _capture_component_versions(records)
    report["mixed_capture_config"] = any(
        len(report["capture_component_versions"][field]) > 1
        for field in (
            "version",
            "prompt_bundle_version",
            "retrieval_policy_version",
            "tool_policy_version",
        )
    )
    report["generated_at"] = _utc_now()
    _atomic_write_text(Path(report_path), json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(Path(review_path), _review_markdown(cases, records, report))
    return report


def runtime_check() -> dict[str, Any]:
    load_dotenv()
    import vigzone_ai

    return {
        "ready": bool(vigzone_ai.API_KEY),
        "provider": "groq",
        "default_model": vigzone_ai.FAST_MODEL,
        "allowed_models": sorted(vigzone_ai.ALLOWED_CHAT_MODELS),
        "zoner": ZONER_PROFILE.runtime_metadata(),
        "provider_call_made": False,
        "next": (
            "Run with --execute when you have confirmed your provider allowance."
            if vigzone_ai.API_KEY
            else "Configure GROQ_API_KEY in the project .env before using --execute."
        ),
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--category", action="append", default=[], help="repeat to select categories")
    parser.add_argument("--case-id", action="append", default=[], help="repeat to select exact case ids")
    parser.add_argument("--critical-only", action="store_true")
    parser.add_argument("--limit", type=int)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan, capture, and report the Zoner v0 baseline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="offline configuration check; makes no provider call")
    check_parser.set_defaults(command="check")

    plan_parser = subparsers.add_parser("plan", help="show selected cases and call count without executing")
    plan_parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    _add_filters(plan_parser)

    run_parser = subparsers.add_parser("run", help="capture real Zoner responses")
    run_parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    run_parser.add_argument("--output", default=str(DEFAULT_RESPONSES))
    run_parser.add_argument("--model", default="")
    run_parser.add_argument("--delay", type=float, default=2.0)
    run_parser.add_argument("--max-retries", type=int, default=2)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--overwrite", action="store_true")
    run_parser.add_argument(
        "--rerun-selected",
        action="store_true",
        help="with --resume, replace successful records for the selected cases",
    )
    run_parser.add_argument(
        "--execute",
        action="store_true",
        help="required acknowledgement that this command makes provider calls",
    )
    _add_filters(run_parser)

    report_parser = subparsers.add_parser("report", help="grade saved captures and create review worksheet")
    report_parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    report_parser.add_argument("--responses", default=str(DEFAULT_RESPONSES))
    report_parser.add_argument("--report", default=str(DEFAULT_REPORT))
    report_parser.add_argument("--review", default=str(DEFAULT_REVIEW))
    report_parser.add_argument("--strict", action="store_true")

    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "check":
            _print_json(runtime_check())
            return 0
        cases = load_cases(args.dataset)
        if args.command == "report":
            report = write_reports(
                cases,
                responses=args.responses,
                report_path=args.report,
                review_path=args.review,
            )
            _print_json(
                {
                    "responses_graded": report["responses_graded"],
                    "automatic_pass_rate": report["automatic_pass_rate"],
                    "critical_failures": report["critical_failures"],
                    "capture_errors": report["capture_error_ids"],
                    "capture_error_details": report["capture_errors"],
                    "capture_prompt_versions": report["capture_component_versions"][
                        "prompt_bundle_version"
                    ],
                    "missing": report["missing"],
                    "report": args.report,
                    "review": args.review,
                }
            )
            return 1 if args.strict and (report["critical_failures"] or report["missing"]) else 0
        selected = select_cases(
            cases,
            categories=args.category,
            case_ids=args.case_id,
            critical_only=args.critical_only,
            limit=args.limit,
        )
        if args.command == "plan":
            _print_json(case_plan(selected))
            return 0
        if not args.execute:
            _print_json(
                {
                    "executed": False,
                    **case_plan(selected),
                    "next": "Add --execute after confirming your provider allowance.",
                }
            )
            return 0
        summary = asyncio.run(
            capture_cases(
                selected,
                output=args.output,
                model=args.model,
                resume=args.resume,
                overwrite=args.overwrite,
                rerun_successful=args.rerun_selected,
                delay_seconds=args.delay,
                max_retries=args.max_retries,
            )
        )
        report_path = Path(args.output).with_name(Path(args.output).stem + "-report.json")
        review_path = Path(args.output).with_name(Path(args.output).stem + "-review.md")
        report = write_reports(
            cases,
            responses=args.output,
            report_path=report_path,
            review_path=review_path,
        )
        _print_json(
            {
                **summary.as_dict(),
                "automatic_pass_rate": report["automatic_pass_rate"],
                "critical_failures": report["critical_failures"],
                "capture_errors": report["capture_error_ids"],
                "capture_error_details": report["capture_errors"],
                "capture_prompt_versions": report["capture_component_versions"][
                    "prompt_bundle_version"
                ],
                "remaining": len(report["missing"]),
                "report": str(report_path),
                "review": str(review_path),
            }
        )
        return 0 if not summary.interrupted else 130
    except EvaluationDataError as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
