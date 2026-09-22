import re


NARRATIVE_FIELDS = [
    "executive_summary",
    "performance_analysis",
    "risk_analysis",
    "diversification_analysis",
    "educational_note",
]


FORBIDDEN_PATTERNS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bhold\b",
    r"\byou should invest\b",
    r"\bi recommend\b",
    r"\bguaranteed return\b",
    r"\bwill definitely rise\b",
    r"\bwill definitely fall\b",
]


def _resolve_context_path(
    *,
    context,
    path,
):
    current = context

    for part in path.split("."):
        if not isinstance(current, dict):
            raise KeyError(path)

        if part not in current:
            raise KeyError(path)

        current = current[part]

    return current


def _get_report_text(report):
    text_parts = []

    for field in NARRATIVE_FIELDS:
        value = report.get(
            field,
            "",
        )

        if isinstance(value, str):
            text_parts.append(value)

    for field in [
        "key_observations",
        "limitations",
    ]:
        values = report.get(
            field,
            [],
        )

        if isinstance(values, list):
            text_parts.extend(
                str(value)
                for value in values
            )

    return "\n".join(text_parts)


def _evaluate_evidence(
    *,
    context,
    report,
):
    invalid_evidence = []

    for evidence in report.get(
        "evidence",
        [],
    ):
        metric_path = evidence.get(
            "metric_path"
        )

        provided_value = evidence.get(
            "value"
        )

        if not metric_path:
            invalid_evidence.append(
                {
                    "metric_path": metric_path,
                    "reason": "Missing metric path.",
                }
            )
            continue

        try:
            actual_value = (
                _resolve_context_path(
                    context=context,
                    path=metric_path,
                )
            )

        except KeyError:
            invalid_evidence.append(
                {
                    "metric_path": metric_path,
                    "reason": (
                        "Metric path does not exist "
                        "in the supplied context."
                    ),
                }
            )
            continue

        if isinstance(
            actual_value,
            (dict, list),
        ):
            invalid_evidence.append(
                {
                    "metric_path": metric_path,
                    "reason": (
                        "Evidence must reference "
                        "a scalar value."
                    ),
                }
            )
            continue

        if (
            str(actual_value)
            != str(provided_value)
        ):
            invalid_evidence.append(
                {
                    "metric_path": metric_path,
                    "reason": (
                        "Evidence value does not "
                        "match the context."
                    ),
                    "expected": str(
                        actual_value
                    ),
                    "received": str(
                        provided_value
                    ),
                }
            )

    return {
        "passed": (
            len(invalid_evidence) == 0
        ),
        "invalid_evidence": (
            invalid_evidence
        ),
    }


def _evaluate_unavailable_sections(
    *,
    context,
    report,
):
    sections = context.get(
        "sections",
        {},
    )

    expected = {
        section_name
        for (
            section_name,
            section_data,
        ) in sections.items()
        if (
            isinstance(
                section_data,
                dict,
            )
            and section_data.get(
                "available"
            )
            is False
        )
    }

    received = set(
        report.get(
            "unavailable_sections",
            [],
        )
    )

    return {
        "passed": expected == received,
        "expected": sorted(expected),
        "received": sorted(received),
    }


def _evaluate_safety_language(
    *,
    report,
):
    report_text = _get_report_text(
        report
    ).lower()

    matches = []

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(
            pattern,
            report_text,
        ):
            matches.append(pattern)

    return {
        "passed": len(matches) == 0,
        "matches": matches,
    }


def _evaluate_required_content(
    *,
    report,
):
    missing_fields = []

    for field in NARRATIVE_FIELDS:
        value = report.get(field)

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            missing_fields.append(
                field
            )

    for field in [
        "key_observations",
        "limitations",
        "evidence",
        "unavailable_sections",
    ]:
        if field not in report:
            missing_fields.append(
                field
            )

    return {
        "passed": (
            len(missing_fields) == 0
        ),
        "missing_fields": (
            missing_fields
        ),
    }


def evaluate_ai_portfolio_report(
    *,
    context,
    report,
):
    checks = {
        "required_content": (
            _evaluate_required_content(
                report=report
            )
        ),
        "evidence_grounding": (
            _evaluate_evidence(
                context=context,
                report=report,
            )
        ),
        "unavailable_sections": (
            _evaluate_unavailable_sections(
                context=context,
                report=report,
            )
        ),
        "safety_language": (
            _evaluate_safety_language(
                report=report
            )
        ),
    }

    passed = all(
        check["passed"]
        for check in checks.values()
    )

    return {
        "passed": passed,
        "checks": checks,
    }