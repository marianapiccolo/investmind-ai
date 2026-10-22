from django.test import SimpleTestCase

from portfolios.ai.evals import NARRATIVE_FIELDS, evaluate_ai_portfolio_report


class BooleanEvidenceTests(SimpleTestCase):
    def evaluate(self, actual, provided, *, path=None):
        context = {
            "sections": {
                "risk": {
                    "available": True,
                    "data": {"annualization_available": actual},
                },
            },
        }
        report = {
            field: "The analysis describes the supplied historical metrics."
            for field in NARRATIVE_FIELDS
        }
        report.update(
            key_observations=["Historical metrics are available."],
            limitations=["Historical observations cover a limited period."],
            evidence=[
                {
                    "metric_path": path or "sections.risk.data.annualization_available",
                    "value": provided,
                }
            ],
            unavailable_sections=[],
        )
        result = evaluate_ai_portfolio_report(context=context, report=report)
        return result, context, report

    def test_json_true_matches_python_boolean_true(self):
        result, context, report = self.evaluate(True, "true")
        self.assertTrue(result["passed"])
        self.assertIs(
            context["sections"]["risk"]["data"]["annualization_available"], True
        )
        self.assertEqual(report["evidence"][0]["value"], "true")

    def test_json_false_matches_python_boolean_false(self):
        result, _, _ = self.evaluate(False, "false")
        self.assertTrue(result["passed"])

    def test_existing_python_boolean_spelling_remains_valid(self):
        for value in [True, False]:
            with self.subTest(value=value):
                result, _, _ = self.evaluate(value, str(value))
                self.assertTrue(result["passed"])

    def test_opposite_boolean_is_rejected(self):
        for actual, provided in [
            (True, "false"),
            (False, "true"),
            (True, "False"),
            (False, "True"),
        ]:
            with self.subTest(actual=actual, provided=provided):
                result, _, _ = self.evaluate(actual, provided)
                self.assertFalse(result["passed"])
                errors = result["checks"]["evidence_grounding"]["invalid_evidence"]
                self.assertEqual(
                    errors[0]["reason"], "Evidence value does not match the context."
                )
                self.assertEqual(errors[0]["received"], provided)

    def test_boolean_is_not_interchangeable_with_numbers(self):
        for actual, provided in [(True, "1"), (False, "0"), (1, "true"), (0, "false")]:
            with self.subTest(actual=actual, provided=provided):
                result, _, _ = self.evaluate(actual, provided)
                self.assertFalse(result["passed"])

    def test_strings_keep_exact_case_and_whitespace_matching(self):
        for actual, provided in [
            ("True", "true"),
            ("false", "False"),
            ("AAPL", "aapl"),
            ("USD", " USD "),
        ]:
            with self.subTest(actual=actual, provided=provided):
                result, _, _ = self.evaluate(actual, provided)
                self.assertFalse(result["passed"])
        result, _, _ = self.evaluate("true", "true")
        self.assertTrue(result["passed"])

    def test_other_boolean_spellings_are_not_silently_coerced(self):
        for provided in ["TRUE", " true ", "yes", "on", "1.0", ""]:
            with self.subTest(provided=provided):
                result, _, _ = self.evaluate(True, provided)
                self.assertFalse(result["passed"])

    def test_financial_value_and_precision_mismatches_still_fail(self):
        for actual, provided in [
            ("14.94", "14.95"),
            ("14.9400", "14.94"),
            ("9385.8400", "9,385.8400"),
        ]:
            with self.subTest(actual=actual, provided=provided):
                result, _, _ = self.evaluate(actual, provided)
                self.assertFalse(result["passed"])
        result, _, _ = self.evaluate("14.94", "14.94")
        self.assertTrue(result["passed"])

    def test_unknown_path_and_object_evidence_still_fail(self):
        for actual, path in [
            (True, "sections.risk.data.invented"),
            ({"available": True}, None),
        ]:
            with self.subTest(actual=actual, path=path):
                result, _, _ = self.evaluate(actual, "true", path=path)
                self.assertFalse(result["passed"])

    def test_other_checks_can_still_reject_report_with_valid_boolean(self):
        _, context, report = self.evaluate(True, "true")
        report["executive_summary"] = "You should buy this asset."
        result = evaluate_ai_portfolio_report(context=context, report=report)
        self.assertTrue(result["checks"]["evidence_grounding"]["passed"])
        self.assertFalse(result["checks"]["safety_language"]["passed"])
        self.assertFalse(result["passed"])
