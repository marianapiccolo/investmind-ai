from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import (
    AIReport,
    Portfolio,
)


class AIPortfolioReportAPITests(APITestCase):
    def setUp(self):
        cache.clear()

        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="AI Portfolio",
            currency="EUR",
        )

        self.other_portfolio = Portfolio.objects.create(
            user=self.other_user,
            name="Other Portfolio",
            currency="EUR",
        )

        self.client.force_authenticate(user=self.user)

    @patch("portfolios.views.generate_ai_portfolio_report_task.delay")
    def test_create_ai_report_returns_202(
        self,
        mock_delay,
    ):
        task_result = Mock()
        task_result.id = "task-123"

        mock_delay.return_value = task_result

        url = reverse(
            "portfolio-ai-reports",
            args=[self.portfolio.id],
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

        self.assertEqual(
            response.data["status"],
            AIReport.Status.PENDING,
        )

        self.assertEqual(
            response.data["celery_task_id"],
            "task-123",
        )

        ai_report = AIReport.objects.get()

        self.assertEqual(
            ai_report.portfolio,
            self.portfolio,
        )

        mock_delay.assert_called_once_with(ai_report.id)

    def test_cannot_create_report_for_another_users_portfolio(
        self,
    ):
        url = reverse(
            "portfolio-ai-reports",
            args=[self.other_portfolio.id],
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_create_requires_authentication(
        self,
    ):
        self.client.force_authenticate(user=None)

        url = reverse(
            "portfolio-ai-reports",
            args=[self.portfolio.id],
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_lists_only_users_reports(
        self,
    ):
        own_report = AIReport.objects.create(
            portfolio=self.portfolio,
            model="test-model",
            status=AIReport.Status.COMPLETED,
            report={"executive_summary": ("Own report.")},
            evaluation={"passed": True},
        )

        AIReport.objects.create(
            portfolio=(self.other_portfolio),
            model="test-model",
            status=AIReport.Status.COMPLETED,
            report={"executive_summary": ("Other report.")},
            evaluation={"passed": True},
        )

        url = reverse("ai-report-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["id"],
            own_report.id,
        )

    def test_cannot_retrieve_another_users_report(
        self,
    ):
        other_report = AIReport.objects.create(
            portfolio=(self.other_portfolio),
            model="test-model",
        )

        url = reverse(
            "ai-report-detail",
            args=[other_report.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_rejected_report_is_not_exposed(
        self,
    ):
        rejected_report = AIReport.objects.create(
            portfolio=self.portfolio,
            model="test-model",
            status=(AIReport.Status.REJECTED),
            report={"executive_summary": ("Unsafe output.")},
            evaluation={"passed": False},
        )

        url = reverse(
            "ai-report-detail",
            args=[rejected_report.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["status"],
            AIReport.Status.REJECTED,
        )

        self.assertIsNone(response.data["report"])

        self.assertFalse(response.data["evaluation_passed"])
