from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from portfolios.models import Portfolio


class WebDashboardTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="dashboarduser",
            password="test-password-123",
        )

        self.other_user = (
            user_model.objects.create_user(
                username="otheruser",
                password="test-password-123",
            )
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Retirement Portfolio",
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
        "get_portfolio_risk_analytics"
    )
    @patch(
        "portfolios.web_views."
        "get_portfolio_market_summary"
    )
    def test_dashboard_uses_real_backend_data(
        self,
        mock_market_summary,
        mock_risk,
    ):
        mock_market_summary.return_value = {
            "total_invested": Decimal(
                "1600.00"
            ),
            "total_market_value": Decimal(
                "2541.00"
            ),
            "total_unrealized_profit_loss": Decimal(
                "941.00"
            ),
            "total_return_percentage": Decimal(
                "58.81"
            ),
        }

        mock_risk.return_value = {
            "return_observations": 8,
            "annualized_volatility_percentage": Decimal(
                "81.69"
            ),
            "maximum_drawdown_percentage": Decimal(
                "-1.14"
            ),
        }

        response = self.client.get(
            reverse("web:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context[
                "selected_portfolio"
            ],
            self.portfolio,
        )

        self.assertTrue(
            response.context[
                "market_summary"
            ]["available"]
        )

        self.assertTrue(
            response.context[
                "risk"
            ]["available"]
        )

        mock_market_summary.assert_called_once_with(
            portfolio=self.portfolio
        )

        mock_risk.assert_called_once_with(
            portfolio=self.portfolio
        )

    @patch(
        "portfolios.web_views."
        "get_portfolio_risk_analytics"
    )
    @patch(
        "portfolios.web_views."
        "get_portfolio_market_summary"
    )
    def test_dashboard_allows_owned_portfolio_selection(
        self,
        mock_market_summary,
        mock_risk,
    ):
        second_portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="Second Portfolio",
                currency="USD",
            )
        )

        mock_market_summary.return_value = {
            "total_invested": Decimal(
                "100.00"
            ),
            "total_market_value": Decimal(
                "110.00"
            ),
            "total_unrealized_profit_loss": Decimal(
                "10.00"
            ),
            "total_return_percentage": Decimal(
                "10.00"
            ),
        }

        mock_risk.return_value = {
            "return_observations": 5,
            "annualized_volatility_percentage": Decimal(
                "10.00"
            ),
            "maximum_drawdown_percentage": Decimal(
                "-2.00"
            ),
        }

        response = self.client.get(
            reverse("web:dashboard"),
            {
                "portfolio": (
                    second_portfolio.id
                )
            },
        )

        self.assertEqual(
            response.context[
                "selected_portfolio"
            ],
            second_portfolio,
        )

        self.assertEqual(
            response.context[
                "currency_symbol"
            ],
            "$",
        )

    def test_user_cannot_select_another_users_portfolio(
        self,
    ):
        response = self.client.get(
            reverse("web:dashboard"),
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