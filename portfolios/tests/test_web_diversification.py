from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from portfolios.models import Portfolio


class WebDiversificationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="diversificationuser",
            password="test-password-123",
        )

        self.other_user = (
            user_model.objects.create_user(
                username="otherdiversificationuser",
                password="test-password-123",
            )
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Diversification Portfolio",
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

    def test_page_keeps_composition_when_correlation_is_unavailable(
        self,
    ):
        composition_result = {
            "id": self.portfolio.id,
            "name": self.portfolio.name,
            "currency": "EUR",
            "positions_count": 1,
            "total_market_value": Decimal(
                "2567.10"
            ),
            "largest_position_percentage": Decimal(
                "100.00"
            ),
            "hhi_concentration_index": Decimal(
                "1.0000"
            ),
            "top_holdings": [
                {
                    "ticker": "VWCE.DEX",
                    "asset_name": (
                        "Vanguard FTSE All-World "
                        "UCITS ETF"
                    ),
                    "market_value": Decimal(
                        "2567.10"
                    ),
                    "allocation_percentage": Decimal(
                        "100.00"
                    ),
                }
            ],
            "sector_allocation": [
                {
                    "label": "Unclassified",
                    "market_value": Decimal(
                        "2567.10"
                    ),
                    "allocation_percentage": Decimal(
                        "100.00"
                    ),
                }
            ],
            "asset_type_allocation": [
                {
                    "label": "ETF",
                    "market_value": Decimal(
                        "2567.10"
                    ),
                    "allocation_percentage": Decimal(
                        "100.00"
                    ),
                }
            ],
        }

        with (
            patch(
                "portfolios.web_views."
                "get_portfolio_composition_analytics",
                return_value=composition_result,
            ) as mock_composition,
            patch(
                "portfolios.web_views."
                "get_portfolio_diversification_analytics",
                side_effect=ValidationError(
                    "At least two active assets are "
                    "required for diversification "
                    "analytics."
                ),
            ) as mock_diversification,
        ):
            response = self.client.get(
                reverse(
                    "web:diversification"
                )
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "portfolios/diversification.html",
        )

        self.assertTrue(
            response.context[
                "composition"
            ]["available"]
        )

        self.assertFalse(
            response.context[
                "diversification"
            ]["available"]
        )

        self.assertEqual(
            response.context[
                "asset_type_chart"
            ],
            {
                "labels": [
                    "ETF",
                ],
                "values": [
                    100.0,
                ],
            },
        )

        self.assertEqual(
            response.context[
                "sector_chart"
            ],
            {
                "labels": [
                    "Unclassified",
                ],
                "values": [
                    100.0,
                ],
            },
        )

        self.assertContains(
            response,
            "At least two active assets",
        )

        mock_composition.assert_called_once_with(
            portfolio=self.portfolio
        )

        mock_diversification.assert_called_once_with(
            portfolio=self.portfolio
        )

    def test_page_exposes_available_correlation_metrics(
        self,
    ):
        composition_result = {
            "id": self.portfolio.id,
            "name": self.portfolio.name,
            "currency": "EUR",
            "positions_count": 2,
            "total_market_value": Decimal(
                "3000.00"
            ),
            "largest_position_percentage": Decimal(
                "60.00"
            ),
            "hhi_concentration_index": Decimal(
                "0.5200"
            ),
            "top_holdings": [],
            "sector_allocation": [],
            "asset_type_allocation": [],
        }

        diversification_result = {
            "portfolio_id": self.portfolio.id,
            "name": self.portfolio.name,
            "currency": "EUR",
            "asset_count": 2,
            "total_pairs": 1,
            "comparable_pairs": 1,
            "unavailable_pairs": 0,
            "average_pairwise_correlation": Decimal(
                "0.4200"
            ),
            "most_correlated_pair": None,
            "least_correlated_pair": None,
            "pair_correlations": [],
            "correlation_matrix": [],
        }

        with (
            patch(
                "portfolios.web_views."
                "get_portfolio_composition_analytics",
                return_value=composition_result,
            ),
            patch(
                "portfolios.web_views."
                "get_portfolio_diversification_analytics",
                return_value=diversification_result,
            ),
        ):
            response = self.client.get(
                reverse(
                    "web:diversification"
                )
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTrue(
            response.context[
                "diversification"
            ]["available"]
        )

        self.assertEqual(
            response.context[
                "diversification"
            ]["data"][
                "average_pairwise_correlation"
            ],
            Decimal("0.4200"),
        )

        self.assertContains(
            response,
            "0.4200",
        )

    def test_anonymous_user_is_redirected(
        self,
    ):
        self.client.logout()

        response = self.client.get(
            reverse(
                "web:diversification"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_user_cannot_select_another_users_portfolio(
        self,
    ):
        response = self.client.get(
            reverse(
                "web:diversification"
            ),
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