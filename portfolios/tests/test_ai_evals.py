from django.test import SimpleTestCase

from portfolios.ai.evals import (
    evaluate_ai_portfolio_report,
)


class AIPortfolioReportEvalTests(
    SimpleTestCase
):
    def setUp(self):
        self.context = {
            "portfolio": {
                "id": 1,
                "name": "Test Portfolio",
                "currency": "EUR",
            },
            "sections": {
                "performance": {
                    "available": True,
                    "data": {
                        "time_weighted_return_percentage": (
                            "8.90"
                        ),
                    },
                },
                "risk": {
                    "available": True,
                    "data": {
                        "maximum_drawdown_percentage": (
                            "-6.40"
                        ),
                    },
                },
                "diversification": {
                    "available": False,
                    "reason": (
                        "At least two active assets "
                        "are required."
                    ),
                },
            },
        }

    def _valid_report(self):
        return {
            "executive_summary": (
                "The portfolio has positive "
                "historical performance."
            ),
            "performance_analysis": (
                "Historical performance was positive."
            ),
            "risk_analysis": (
                "The portfolio experienced a "
                "historical drawdown."
            ),
            "diversification_analysis": (
                "Diversification data is unavailable."
            ),
            "key_observations": [
                "Performance data is available.",
            ],
            "limitations": [
                "Diversification analysis is "
                "unavailable because the portfolio "
                "does not contain enough active assets.",
            ],
            "educational_note": (
                "This analysis is educational."
            ),
            "evidence": [
                {
                    "metric_path": (
                        "sections.performance.data."
                        "time_weighted_return_percentage"
                    ),
                    "value": "8.90",
                },
                {
                    "metric_path": (
                        "sections.risk.data."
                        "maximum_drawdown_percentage"
                    ),
                    "value": "-6.40",
                },
            ],
            "unavailable_sections": [
                "diversification"
            ],
        }

    def test_valid_report_passes_evaluation(
        self,
    ):
        result = evaluate_ai_portfolio_report(
            context=self.context,
            report=self._valid_report(),
        )

        self.assertTrue(
            result["passed"]
        )

    def test_rejects_invented_evidence_value(
        self,
    ):
        report = self._valid_report()

        report["evidence"][0][
            "value"
        ] = "99.99"

        result = evaluate_ai_portfolio_report(
            context=self.context,
            report=report,
        )

        self.assertFalse(
            result["passed"]
        )

        self.assertFalse(
            result[
                "checks"
            ][
                "evidence_grounding"
            ][
                "passed"
            ]
        )

    def test_rejects_unknown_metric_path(
        self,
    ):
        report = self._valid_report()

        report["evidence"][0][
            "metric_path"
        ] = (
            "sections.performance.data."
            "invented_metric"
        )

        result = evaluate_ai_portfolio_report(
            context=self.context,
            report=report,
        )

        self.assertFalse(
            result[
                "checks"
            ][
                "evidence_grounding"
            ][
                "passed"
            ]
        )

    def test_detects_missing_unavailable_section(
        self,
    ):
        report = self._valid_report()

        report[
            "unavailable_sections"
        ] = []

        result = evaluate_ai_portfolio_report(
            context=self.context,
            report=report,
        )

        self.assertFalse(
            result[
                "checks"
            ][
                "unavailable_sections"
            ][
                "passed"
            ]
        )

    def test_detects_recommendation_language(
        self,
    ):
        report = self._valid_report()

        report[
            "executive_summary"
        ] = (
            "You should buy more of this asset."
        )

        result = evaluate_ai_portfolio_report(
            context=self.context,
            report=report,
        )

        self.assertFalse(
            result[
                "checks"
            ][
                "safety_language"
            ][
                "passed"
            ]
        )