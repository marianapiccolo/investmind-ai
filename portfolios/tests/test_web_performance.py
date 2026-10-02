from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from portfolios.models import Portfolio


class WebPerformanceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="performanceuser",
            password="test-password-123",
        )

        self.other_user = (
            user_model.objects.create_user(
                username="otherperformanceuser",
                password="test-password-123",
            )
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Performance Portfolio",
            currency="EUR",
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

    @patch(
        "portfolios.web_views."
        "get_portfolio_performance"
    )
    def test_performance_page_uses_backend_data(
        self,
        mock_performance,
    ):
        mock_performance.return_value = {
            "portfolio_id": self.portfolio.id,
            "name": self.portfolio.name,
            "currency": "EUR",
            "start_date": date(
                2026,
                9,
                1,
            ),
            "end_date": date(
                2026,
                9,
                2,
            ),
            "observations": 2,
            "ending_value": Decimal(
                "1100.00"
            ),
            "net_external_cash_flow": Decimal(
                "1000.00"
            ),
            "time_weighted_return_percentage": Decimal(
                "10.00"
            ),
            "series": [
                {
                    "date": date(
                        2026,
                        9,
                        1,
                    ),
                    "portfolio_value": Decimal(
                        "1000.00"
                    ),
                    "net_cash_flow": Decimal(
                        "1000.00"
                    ),
                    "daily_return_percentage": None,
                    "cumulative_twr_percentage": Decimal(
                        "0.00"
                    ),
                },
                {
                    "date": date(
                        2026,
                        9,
                        2,
                    ),
                    "portfolio_value": Decimal(
                        "1100.00"
                    ),
                    "net_cash_flow": Decimal(
                        "0.00"
                    ),
                    "daily_return_percentage": Decimal(
                        "10.00"
                    ),
                    "cumulative_twr_percentage": Decimal(
                        "10.00"
                    ),
                },
            ],
        }

        response = self.client.get(
            reverse("web:performance")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "portfolios/performance.html",
        )

        self.assertEqual(
            response.context[
                "selected_portfolio"
            ],
            self.portfolio,
        )

        self.assertEqual(
            response.context[
                "performance_chart"
            ],
            {
                "labels": [
                    "2026-09-01",
                    "2026-09-02",
                ],
                "values": [
                    0.0,
                    10.0,
                ],
            },
        )

        self.assertEqual(
            response.context[
                "daily_return_chart"
            ],
            {
                "labels": [
                    "2026-09-01",
                    "2026-09-02",
                ],
                "values": [
                    None,
                    10.0,
                ],
            },
        )

        mock_performance.assert_called_once_with(
            portfolio=self.portfolio
        )

    def test_anonymous_user_is_redirected(
        self,
    ):
        self.client.logout()

        response = self.client.get(
            reverse("web:performance")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_user_cannot_select_another_users_portfolio(
        self,
    ):
        response = self.client.get(
            reverse("web:performance"),
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