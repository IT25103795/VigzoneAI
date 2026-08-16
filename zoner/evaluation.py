"""Dependency-free, offline evaluation utilities for Zoner.

The evaluator deliberately separates deterministic checks from human rubrics.
It can validate the corpus and grade previously captured responses without an
API key, network access, or a paid evaluation service.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DEFAULT_DATASET = Path(__file__).with_name("evals") / "v0_seed.jsonl"
ALLOWED_CATEGORIES = {
    "identity",
    "conversation",
    "multilingual",
    "coding",
    "grounding",
    "retrieval",
    "tools",
    "safety_privacy",
    "long_context",
}
ALLOWED_CONTEXT_KEYS = {"file", "live", "memory", "workspace", "persona"}
SCRIPT_RANGES = {
    "sinhala": (0x0D80, 0x0DFF),
    "tamil": (0x0B80, 0x0BFF),
}


class EvaluationDataError(ValueError):
    """Raised when an evaluation case or response file is malformed."""


@dataclass(frozen=True)
class EvalCase:
    id: str
    category: str
    critical: bool
    messages: tuple[dict[str, str], ...]
    context: dict[str, str]
    expected: dict[str, Any]
    human_rubric: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class CaseResult:
    id: str
    category: str
    critical: bool
    passed: bool
    score: float
    checks: tuple[CheckResult, ...]
    human_review_required: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "critical": self.critical,
            "passed": self.passed,
            "score": self.score,
            "human_review_required": self.human_review_required,
            "checks": [check.__dict__ for check in self.checks],
        }


def _require_string_list(value: Any, field: str, case_id: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise EvaluationDataError(f"{case_id}: {field} must be a list of non-empty strings")
    return tuple(item.strip() for item in value)


def _parse_case(raw: Any, line_number: int) -> EvalCase:
    if not isinstance(raw, dict):
        raise EvaluationDataError(f"line {line_number}: case must be a JSON object")
    case_id = str(raw.get("id") or "").strip()
    if not case_id:
        raise EvaluationDataError(f"line {line_number}: case id is required")
    category = str(raw.get("category") or "").strip()
    if category not in ALLOWED_CATEGORIES:
        raise EvaluationDataError(f"{case_id}: unsupported category {category!r}")
    critical = raw.get("critical", False)
    if not isinstance(critical, bool):
        raise EvaluationDataError(f"{case_id}: critical must be boolean")

    raw_messages = raw.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raise EvaluationDataError(f"{case_id}: messages must be a non-empty list")
    messages: list[dict[str, str]] = []
    for index, message in enumerate(raw_messages):
        if not isinstance(message, dict):
            raise EvaluationDataError(f"{case_id}: message {index} must be an object")
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
            raise EvaluationDataError(
                f"{case_id}: message {index} needs role user/assistant and non-empty text"
            )
        messages.append({"role": role, "content": content.strip()})
    if messages[-1]["role"] != "user":
        raise EvaluationDataError(f"{case_id}: the final message must be from the user")

    context = raw.get("context") or {}
    if not isinstance(context, dict):
        raise EvaluationDataError(f"{case_id}: context must be an object")
    unknown_context = set(context) - ALLOWED_CONTEXT_KEYS
    if unknown_context:
        raise EvaluationDataError(f"{case_id}: unsupported context keys {sorted(unknown_context)}")
    normalized_context: dict[str, str] = {}
    for key, value in context.items():
        if not isinstance(value, str):
            raise EvaluationDataError(f"{case_id}: context {key} must be text")
        normalized_context[key] = value

    expected = raw.get("expected") or {}
    if not isinstance(expected, dict):
        raise EvaluationDataError(f"{case_id}: expected must be an object")
    normalized_expected: dict[str, Any] = {
        "must_include_all": _require_string_list(expected.get("must_include_all"), "must_include_all", case_id),
        "must_include_any": _require_string_list(expected.get("must_include_any"), "must_include_any", case_id),
        "must_not_include": _require_string_list(expected.get("must_not_include"), "must_not_include", case_id),
    }
    raw_script_minimums = expected.get("min_script_chars") or {}
    if not isinstance(raw_script_minimums, dict):
        raise EvaluationDataError(f"{case_id}: min_script_chars must be an object")
    script_minimums: dict[str, int] = {}
    for script, minimum in raw_script_minimums.items():
        if script not in SCRIPT_RANGES:
            raise EvaluationDataError(f"{case_id}: unsupported script {script!r}")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            raise EvaluationDataError(
                f"{case_id}: min_script_chars.{script} must be a positive integer"
            )
        script_minimums[script] = minimum
    normalized_expected["min_script_chars"] = script_minimums
    for length_field in ("min_chars", "max_chars"):
        value = expected.get(length_field)
        if value is not None and (not isinstance(value, int) or value < 0):
            raise EvaluationDataError(f"{case_id}: {length_field} must be a non-negative integer")
        normalized_expected[length_field] = value
    required_metadata = expected.get("required_metadata") or {}
    if not isinstance(required_metadata, dict):
        raise EvaluationDataError(f"{case_id}: required_metadata must be an object")
    normalized_expected["required_metadata"] = required_metadata

    human_rubric = _require_string_list(raw.get("human_rubric"), "human_rubric", case_id)
    tags = _require_string_list(raw.get("tags"), "tags", case_id)
    has_automatic_check = any(
        normalized_expected[field]
        for field in (
            "must_include_all",
            "must_include_any",
            "must_not_include",
            "required_metadata",
            "min_script_chars",
        )
    ) or normalized_expected["min_chars"] is not None or normalized_expected["max_chars"] is not None
    if not has_automatic_check and not human_rubric:
        raise EvaluationDataError(f"{case_id}: at least one automatic check or human rubric is required")

    return EvalCase(
        id=case_id,
        category=category,
        critical=critical,
        messages=tuple(messages),
        context=normalized_context,
        expected=normalized_expected,
        human_rubric=human_rubric,
        tags=tags,
    )


def load_cases(path: str | Path = DEFAULT_DATASET) -> list[EvalCase]:
    dataset_path = Path(path)
    if not dataset_path.is_file():
        raise EvaluationDataError(f"evaluation dataset not found: {dataset_path}")
    cases: list[EvalCase] = []
    seen_ids: set[str] = set()
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvaluationDataError(f"line {line_number}: invalid JSON: {exc.msg}") from exc
            case = _parse_case(raw, line_number)
            if case.id in seen_ids:
                raise EvaluationDataError(f"duplicate evaluation id: {case.id}")
            seen_ids.add(case.id)
            cases.append(case)
    if not cases:
        raise EvaluationDataError("evaluation dataset is empty")
    return cases


def dataset_summary(cases: Sequence[EvalCase]) -> dict[str, Any]:
    categories = Counter(case.category for case in cases)
    return {
        "cases": len(cases),
        "critical_cases": sum(1 for case in cases if case.critical),
        "categories": dict(sorted(categories.items())),
        "human_review_cases": sum(1 for case in cases if case.human_rubric),
    }


def _metadata_value(metadata: Mapping[str, Any], dotted_key: str) -> Any:
    value: Any = metadata
    for part in dotted_key.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _normalize_for_matching(value: str) -> str:
    """Normalize harmless Unicode typography before deterministic phrase checks."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.translate(str.maketrans({"\u2018": "'", "\u2019": "'", "\u02bc": "'"}))
    return re.sub(r"\s+", " ", normalized).strip()


def grade_response(
    case: EvalCase,
    response: str,
    metadata: Mapping[str, Any] | None = None,
) -> CaseResult:
    if not isinstance(response, str):
        raise EvaluationDataError(f"{case.id}: response must be text")
    metadata = metadata or {}
    folded = _normalize_for_matching(response)
    checks: list[CheckResult] = [
        CheckResult("non_empty", bool(response.strip()), "response contains visible text")
    ]

    for phrase in case.expected["must_include_all"]:
        present = _normalize_for_matching(phrase) in folded
        checks.append(CheckResult(f"includes:{phrase}", present, f"required phrase {phrase!r}"))

    any_phrases = case.expected["must_include_any"]
    if any_phrases:
        present = any(_normalize_for_matching(phrase) in folded for phrase in any_phrases)
        checks.append(CheckResult("includes_any", present, f"one of {list(any_phrases)!r}"))

    for phrase in case.expected["must_not_include"]:
        absent = _normalize_for_matching(phrase) not in folded
        checks.append(CheckResult(f"excludes:{phrase}", absent, f"forbidden phrase {phrase!r}"))

    min_chars = case.expected["min_chars"]
    if min_chars is not None:
        checks.append(CheckResult("min_chars", len(response) >= min_chars, f"minimum {min_chars} characters"))
    max_chars = case.expected["max_chars"]
    if max_chars is not None:
        checks.append(CheckResult("max_chars", len(response) <= max_chars, f"maximum {max_chars} characters"))

    for key, expected_value in case.expected["required_metadata"].items():
        actual = _metadata_value(metadata, key)
        checks.append(
            CheckResult(
                f"metadata:{key}",
                actual == expected_value,
                f"expected {expected_value!r}, received {actual!r}",
            )
        )

    for script, minimum in case.expected["min_script_chars"].items():
        start, end = SCRIPT_RANGES[script]
        actual = sum(1 for char in response if start <= ord(char) <= end)
        checks.append(
            CheckResult(
                f"min_script_chars:{script}",
                actual >= minimum,
                f"minimum {minimum} {script} characters; received {actual}",
            )
        )

    passed_checks = sum(1 for check in checks if check.passed)
    score = passed_checks / len(checks) if checks else 0.0
    return CaseResult(
        id=case.id,
        category=case.category,
        critical=case.critical,
        passed=passed_checks == len(checks),
        score=round(score, 4),
        checks=tuple(checks),
        human_review_required=bool(case.human_rubric),
    )


def load_responses(path: str | Path) -> dict[str, dict[str, Any]]:
    response_path = Path(path)
    if not response_path.is_file():
        raise EvaluationDataError(f"response file not found: {response_path}")
    responses: dict[str, dict[str, Any]] = {}
    with response_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvaluationDataError(f"response line {line_number}: invalid JSON") from exc
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("response"), str):
                raise EvaluationDataError(
                    f"response line {line_number}: id and response strings are required"
                )
            if item["id"] in responses:
                raise EvaluationDataError(f"duplicate response id: {item['id']}")
            metadata = item.get("metadata") or {}
            if not isinstance(metadata, dict):
                raise EvaluationDataError(f"response {item['id']}: metadata must be an object")
            responses[item["id"]] = {"response": item["response"], "metadata": metadata}
    return responses


def grade_saved_responses(
    cases: Sequence[EvalCase],
    responses: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    results: list[CaseResult] = []
    missing: list[str] = []
    for case in cases:
        saved = responses.get(case.id)
        if saved is None:
            missing.append(case.id)
            continue
        results.append(
            grade_response(case, str(saved.get("response", "")), saved.get("metadata") or {})
        )
    failed = [result.id for result in results if not result.passed]
    critical_failures = [result.id for result in results if result.critical and not result.passed]
    return {
        "dataset": dataset_summary(cases),
        "responses_graded": len(results),
        "automatic_pass_rate": round(
            (sum(1 for result in results if result.passed) / len(results) * 100) if results else 0.0,
            2,
        ),
        "failed": failed,
        "critical_failures": critical_failures,
        "missing": missing,
        "human_review_pending": [result.id for result in results if result.human_review_required],
        "results": [result.as_dict() for result in results],
    }


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and grade the offline Zoner evaluation suite")
    parser.add_argument("command", choices=("validate", "summary", "grade"))
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--responses", help="JSONL responses file required by the grade command")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        cases = load_cases(args.dataset)
        if args.command in {"validate", "summary"}:
            _print_json({"valid": True, **dataset_summary(cases)})
            return 0
        if not args.responses:
            parser.error("--responses is required for the grade command")
        report = grade_saved_responses(cases, load_responses(args.responses))
        _print_json(report)
        return 1 if report["critical_failures"] or report["missing"] else 0
    except EvaluationDataError as exc:
        _print_json({"valid": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
