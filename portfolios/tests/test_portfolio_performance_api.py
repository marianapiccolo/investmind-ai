from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Portfolio


class PortfolioPerformanceAPITests(
    APITestCase
):
    def setUp(self):
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
            name="Performance Portfolio",
            currency="USD",
        )

        self.other_portfolio = (
            Portfolio.objects.create(
                user=self.other_user,
                name="Other Portfolio",
                currency="USD",
            )
        )

        self.client.force_authenticate(
            user=self.user
        )

    @patch(
        "portfolios.views."
        "get_portfolio_performance"
    )
    def test_get_portfolio_performance(
        self,
        mock_performance,
    ):
        mock_performance.return_value = {
            "portfolio_id": self.portfolio.id,
            "name": self.portfolio.name,
            "currency": "USD",
            "start_date": date(
                2026,
                9,
                1,
            ),
            "end_date": date(
                2026,
                9,
                4,
            ),
            "observations": 4,
            "ending_value": Decimal(
                "1980"
            ),
            "net_external_cash_flow": (
                Decimal("1600")
            ),
            "time_weighted_return_percentage": (
                Decimal("32")
            ),
            "series": [],
        }

        url = reverse(
            "portfolio-performance",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data[
                "time_weighted_return_percentage"
            ],
            "32.00",
        )

        self.assertEqual(
            response.data[
                "portfolio_id"
            ],
            self.portfolio.id,
        )

    def test_cannot_access_another_users_performance(
        self,
    ):
        url = reverse(
            "portfolio-performance",
            args=[
                self.other_portfolio.id
            ],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_requires_authentication(
        self,
    ):
        self.client.force_authenticate(
            user=None
        )

        url = reverse(
            "portfolio-performance",
            args=[self.portfolio.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )