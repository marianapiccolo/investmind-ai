from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from portfolios.models import Portfolio


class WebRiskTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="riskuser",
            password="test-password-123",
        )

        self.other_user = (
            user_model.objects.create_user(
                username="otherriskuser",
                password="test-password-123",
            )
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Risk Portfolio",
            currency="EUR",
        )

        self.other_portfolio = (
            Portfolio.objects.create(
                user=self.other_user,
                name="Private Risk Portfolio",
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
    def test_risk_page_uses_backend_data(
        self,
        mock_risk,
    ):
        mock_risk.return_value = {
            "portfolio_id": self.portfolio.id,
            "name": self.portfolio.name,
            "currency": "EUR",
            "start_date": date(
                2026,
                8,
                26,
            ),
            "end_date": date(
                2026,
                9,
                7,
            ),
            "observations": 9,
            "return_observations": 8,
            "time_weighted_return_percentage": Decimal(
                "14.95"
            ),
            "annualized_volatility_percentage": Decimal(
                "81.69"
            ),
            "annualized_downside_deviation_percentage": Decimal(
                "6.30"
            ),
            "maximum_drawdown_percentage": Decimal(
                "-1.14"
            ),
            "best_period": {
                "date": date(
                    2026,
                    8,
                    27,
                ),
                "return_percentage": Decimal(
                    "14.51"
                ),
            },
            "worst_period": {
                "date": date(
                    2026,
                    8,
                    31,
                ),
                "return_percentage": Decimal(
                    "-1.12"
                ),
            },
            "positive_periods": 4,
            "negative_periods": 4,
        }

        response = self.client.get(
            reverse("web:risk")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "portfolios/risk.html",
        )

        self.assertEqual(
            response.context[
                "selected_portfolio"
            ],
            self.portfolio,
        )

        self.assertTrue(
            response.context[
                "risk"
            ]["available"]
        )

        self.assertEqual(
            response.context[
                "risk_distribution_chart"
            ],
            {
                "labels": [
                    "Positive periods",
                    "Negative periods",
                ],
                "values": [
                    4,
                    4,
                ],
            },
        )

        self.assertEqual(
            response.context[
                "extreme_return_chart"
            ],
            {
                "labels": [
                    "Best period",
                    "Worst period",
                ],
                "values": [
                    14.51,
                    -1.12,
                ],
            },
        )

        mock_risk.assert_called_once_with(
            portfolio=self.portfolio
        )

    @patch(
        "portfolios.web_views."
        "get_portfolio_risk_analytics"
    )
    def test_risk_page_handles_unavailable_data(
        self,
        mock_risk,
    ):
        mock_risk.side_effect = ValidationError(
            "Insufficient historical data."
        )

        response = self.client.get(
            reverse("web:risk")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertFalse(
            response.context[
                "risk"
            ]["available"]
        )

        self.assertContains(
            response,
            "Insufficient historical data.",
        )

    def test_anonymous_user_is_redirected(
        self,
    ):
        self.client.logout()

        response = self.client.get(
            reverse("web:risk")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_user_cannot_select_another_users_portfolio(
        self,
    ):
        response = self.client.get(
            reverse("web:risk"),
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