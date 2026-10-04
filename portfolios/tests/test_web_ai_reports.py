from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import (
    TestCase,
    override_settings,
)
from django.urls import reverse

from portfolios.models import (
    AIReport,
    Portfolio,
)


class WebAIReportsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="reportuser",
            password="test-password-123",
        )

        self.other_user = (
            user_model.objects.create_user(
                username="otherreportuser",
                password="test-password-123",
            )
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="AI Report Portfolio",
            currency="EUR",
        )

        self.second_portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="Second Portfolio",
                currency="EUR",
            )
        )

        self.other_portfolio = (
            Portfolio.objects.create(
                user=self.other_user,
                name="Private Portfolio",
                currency="EUR",
            )
        )

        self.client.force_login(
            self.user
        )

    def _create_completed_report(
        self,
        *,
        portfolio=None,
    ):
        portfolio = (
            portfolio
            or self.portfolio
        )

        return AIReport.objects.create(
            portfolio=portfolio,
            status=AIReport.Status.COMPLETED,
            model="gpt-test",
            report={
                "executive_summary": (
                    "**Portfolio summary**"
                ),
                "performance_analysis": (
                    "Performance analysis."
                ),
                "risk_analysis": (
                    "Risk analysis."
                ),
                "diversification_analysis": (
                    "Diversification analysis."
                ),
                "key_observations": [
                    "Observation one.",
                ],
                "limitations": [
                    "Limited history.",
                ],
                "educational_note": (
                    "Educational note."
                ),
                "evidence": [
                    {
                        "metric_path": (
                            "portfolio.total_value"
                        ),
                        "value": "1000.00",
                    }
                ],
                "unavailable_sections": [],
            },
            evaluation={
                "passed": True,
                "checks": {},
            },
        )

    def test_page_lists_only_selected_portfolio_reports(
        self,
    ):
        selected_report = (
            self._create_completed_report()
        )

        other_report = (
            self._create_completed_report(
                portfolio=self.second_portfolio
            )
        )

        response = self.client.get(
            reverse("web:ai-reports"),
            {
                "portfolio": (
                    self.portfolio.id
                )
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "portfolios/ai_reports.html",
        )

        report_ids = [
            report.id
            for report
            in response.context["reports"]
        ]

        self.assertIn(
            selected_report.id,
            report_ids,
        )

        self.assertNotIn(
            other_report.id,
            report_ids,
        )

    @override_settings(
        OPENAI_MODEL="gpt-test"
    )
    @patch(
        "portfolios.web_views."
        "generate_ai_portfolio_report_task.delay"
    )
    def test_user_can_queue_ai_report(
        self,
        mock_delay,
    ):
        mock_delay.return_value = (
            SimpleNamespace(
                id="task-123"
            )
        )

        response = self.client.post(
            (
                reverse("web:ai-reports")
                + (
                    "?portfolio="
                    f"{self.portfolio.id}"
                )
            )
        )

        ai_report = (
            AIReport.objects.get(
                portfolio=self.portfolio
            )
        )

        self.assertEqual(
            ai_report.status,
            AIReport.Status.PENDING,
        )

        self.assertEqual(
            ai_report.model,
            "gpt-test",
        )

        self.assertEqual(
            ai_report.celery_task_id,
            "task-123",
        )

        mock_delay.assert_called_once_with(
            ai_report.id
        )

        self.assertRedirects(
            response,
            (
                reverse("web:ai-reports")
                + (
                    "?portfolio="
                    f"{self.portfolio.id}"
                    "&report="
                    f"{ai_report.id}"
                )
            ),
        )

    def test_completed_report_is_displayed(
        self,
    ):
        report = (
            self._create_completed_report()
        )

        response = self.client.get(
            reverse("web:ai-reports"),
            {
                "portfolio": (
                    self.portfolio.id
                ),
                "report": report.id,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "<strong>Portfolio summary</strong>",
            html=True,
        )

        self.assertContains(
            response,
            "Performance analysis.",
        )

        self.assertContains(
            response,
            "Risk analysis.",
        )

        self.assertTrue(
            response.context[
                "evaluation_passed"
            ]
        )

    def test_processing_report_enables_auto_refresh(
        self,
    ):
        report = AIReport.objects.create(
            portfolio=self.portfolio,
            status=(
                AIReport.Status.PROCESSING
            ),
            model="gpt-test",
        )

        response = self.client.get(
            reverse("web:ai-reports"),
            {
                "portfolio": (
                    self.portfolio.id
                ),
                "report": report.id,
            },
        )

        self.assertTrue(
            response.context[
                "auto_refresh"
            ]
        )

        self.assertIsNone(
            response.context[
                "report_content"
            ]
        )

    def test_rejected_report_content_is_not_exposed(
        self,
    ):
        report = AIReport.objects.create(
            portfolio=self.portfolio,
            status=(
                AIReport.Status.REJECTED
            ),
            model="gpt-test",
            report={
                "executive_summary": (
                    "Do not expose this report."
                )
            },
            evaluation={
                "passed": False,
                "checks": {},
            },
        )

        response = self.client.get(
            reverse("web:ai-reports"),
            {
                "portfolio": (
                    self.portfolio.id
                ),
                "report": report.id,
            },
        )

        self.assertIsNone(
            response.context[
                "report_content"
            ]
        )

        self.assertNotContains(
            response,
            "Do not expose this report.",
        )

        self.assertContains(
            response,
            "did not pass",
        )

    def test_report_cannot_be_accessed_through_another_portfolio(
        self,
    ):
        report = (
            self._create_completed_report(
                portfolio=self.second_portfolio
            )
        )

        response = self.client.get(
            reverse("web:ai-reports"),
            {
                "portfolio": (
                    self.portfolio.id
                ),
                "report": report.id,
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_user_cannot_select_another_users_portfolio(
        self,
    ):
        response = self.client.get(
            reverse("web:ai-reports"),
            {
                "portfolio": (
                    self.other_portfolio.id
                )
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_anonymous_user_is_redirected(
        self,
    ):
        self.client.logout()

        response = self.client.get(
            reverse("web:ai-reports")
        )

        self.assertEqual(
            response.status_code,
            302,
        )