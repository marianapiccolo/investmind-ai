from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from portfolios.ai.openai_client import (
    AIProviderError,
)
from portfolios.models import (
    AIReport,
    Portfolio,
)
from portfolios.tasks import (
    generate_ai_portfolio_report_task,
)


class AIReportTaskTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="AI Portfolio",
            currency="EUR",
        )

        self.ai_report = AIReport.objects.create(
            portfolio=self.portfolio,
            model="test-model",
        )

        self.context = {
            "portfolio": {
                "id": self.portfolio.id,
                "name": self.portfolio.name,
                "currency": "EUR",
            },
            "sections": {},
        }

        self.report = {
            "portfolio_id": self.portfolio.id,
            "name": self.portfolio.name,
            "model": "test-model",
            "executive_summary": "Summary.",
            "performance_analysis": "Performance.",
            "risk_analysis": "Risk.",
            "diversification_analysis": (
                "Diversification."
            ),
            "key_observations": [],
            "limitations": [],
            "educational_note": (
                "Educational only."
            ),
            "evidence": [],
            "unavailable_sections": [],
        }

    @patch(
        "portfolios.tasks."
        "evaluate_ai_portfolio_report"
    )
    @patch(
        "portfolios.tasks."
        "generate_ai_portfolio_report"
    )
    @patch(
        "portfolios.tasks."
        "build_ai_portfolio_context"
    )
    def test_completed_report_is_persisted(
        self,
        mock_context,
        mock_generate,
        mock_evaluate,
    ):
        mock_context.return_value = (
            self.context
        )

        mock_generate.return_value = (
            self.report
        )

        mock_evaluate.return_value = {
            "passed": True,
            "checks": {},
        }

        generate_ai_portfolio_report_task(
            self.ai_report.id
        )

        self.ai_report.refresh_from_db()

        self.assertEqual(
            self.ai_report.status,
            AIReport.Status.COMPLETED,
        )

        self.assertEqual(
            self.ai_report.context_snapshot,
            self.context,
        )

        self.assertEqual(
            self.ai_report.report,
            self.report,
        )

        self.assertTrue(
            self.ai_report.evaluation[
                "passed"
            ]
        )

        self.assertIsNotNone(
            self.ai_report.started_at
        )

        self.assertIsNotNone(
            self.ai_report.completed_at
        )

    @patch(
        "portfolios.tasks."
        "evaluate_ai_portfolio_report"
    )
    @patch(
        "portfolios.tasks."
        "generate_ai_portfolio_report"
    )
    @patch(
        "portfolios.tasks."
        "build_ai_portfolio_context"
    )
    def test_failed_eval_rejects_report(
        self,
        mock_context,
        mock_generate,
        mock_evaluate,
    ):
        mock_context.return_value = (
            self.context
        )

        mock_generate.return_value = (
            self.report
        )

        mock_evaluate.return_value = {
            "passed": False,
            "checks": {
                "evidence_grounding": {
                    "passed": False,
                }
            },
        }

        generate_ai_portfolio_report_task(
            self.ai_report.id
        )

        self.ai_report.refresh_from_db()

        self.assertEqual(
            self.ai_report.status,
            AIReport.Status.REJECTED,
        )

        self.assertFalse(
            self.ai_report.evaluation[
                "passed"
            ]
        )

    @patch(
        "portfolios.tasks."
        "generate_ai_portfolio_report"
    )
    @patch(
        "portfolios.tasks."
        "build_ai_portfolio_context"
    )
    def test_provider_failure_marks_report_as_failed(
        self,
        mock_context,
        mock_generate,
    ):
        mock_context.return_value = (
            self.context
        )

        mock_generate.side_effect = (
            AIProviderError(
                "Provider unavailable."
            )
        )

        with self.assertRaises(
            AIProviderError
        ):
            generate_ai_portfolio_report_task(
                self.ai_report.id
            )

        self.ai_report.refresh_from_db()

        self.assertEqual(
            self.ai_report.status,
            AIReport.Status.FAILED,
        )

        self.assertEqual(
            self.ai_report.error_message,
            "AI provider is unavailable.",
        )

        self.assertIsNotNone(
            self.ai_report.completed_at
        )