from datetime import (
    date,
    datetime,
    timezone,
)
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from portfolios.models import (
    Asset,
    Portfolio,
    Transaction,
)

class WebDashboardTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="dashboarduser",
            password="test-password-123",
        )

        self.other_user = user_model.objects.create_user(
            username="otheruser",
            password="test-password-123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Retirement Portfolio",
            currency="EUR",
        )

        self.other_portfolio = Portfolio.objects.create(
            user=self.other_user,
            name="Private Portfolio",
            currency="EUR",
        )

        self.client.force_login(
            self.user
        )

    @patch(
        "portfolios.web_views."
        "get_portfolio_performance"
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
        mock_performance,
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
            "positions": [
                {
                    "ticker": "VWCE.DEX",
                    "asset_name": (
                        "Vanguard FTSE "
                        "All-World UCITS ETF"
                    ),
                    "allocation_percentage": Decimal(
                        "100.00"
                    ),
                }
            ],
        }

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
                "2541.00"
            ),
            "net_external_cash_flow": Decimal(
                "1600.00"
            ),
            "time_weighted_return_percentage": Decimal(
                "14.95"
            ),
            "series": [
                {
                    "date": date(
                        2026,
                        9,
                        1,
                    ),
                    "portfolio_value": Decimal(
                        "2500.00"
                    ),
                    "net_cash_flow": Decimal(
                        "0.00"
                    ),
                    "daily_return_percentage": Decimal(
                        "0.00"
                    ),
                    "cumulative_twr_percentage": Decimal(
                        "10.00"
                    ),
                },
                {
                    "date": date(
                        2026,
                        9,
                        2,
                    ),
                    "portfolio_value": Decimal(
                        "2541.00"
                    ),
                    "net_cash_flow": Decimal(
                        "0.00"
                    ),
                    "daily_return_percentage": Decimal(
                        "1.64"
                    ),
                    "cumulative_twr_percentage": Decimal(
                        "14.95"
                    ),
                },
            ],
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
                "performance"
            ]["available"]
        )

        self.assertTrue(
            response.context[
                "risk"
            ]["available"]
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
                    10.0,
                    14.95,
                ],
            },
        )

        self.assertEqual(
            response.context[
                "composition_chart"
            ],
            {
                "labels": [
                    "VWCE.DEX",
                ],
                "values": [
                    100.0,
                ],
            },
        )

        mock_market_summary.assert_called_once_with(
            portfolio=self.portfolio
        )

        mock_performance.assert_called_once_with(
            portfolio=self.portfolio
        )

        mock_risk.assert_called_once_with(
            portfolio=self.portfolio
        )

    @patch(
        "portfolios.web_views."
        "get_portfolio_performance"
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
        mock_performance,
    ):
        second_portfolio = Portfolio.objects.create(
            user=self.user,
            name="Second Portfolio",
            currency="USD",
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
            "positions": [
                {
                    "ticker": "AAPL",
                    "asset_name": "Apple",
                    "allocation_percentage": Decimal(
                        "100.00"
                    ),
                }
            ],
        }

        mock_performance.return_value = {
            "portfolio_id": second_portfolio.id,
            "name": second_portfolio.name,
            "currency": "USD",
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
                "110.00"
            ),
            "net_external_cash_flow": Decimal(
                "100.00"
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
                        "100.00"
                    ),
                    "net_cash_flow": Decimal(
                        "0.00"
                    ),
                    "daily_return_percentage": Decimal(
                        "0.00"
                    ),
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
                        "110.00"
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
            response.status_code,
            200,
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

        mock_market_summary.assert_called_once_with(
            portfolio=second_portfolio
        )

        mock_performance.assert_called_once_with(
            portfolio=second_portfolio
        )

        mock_risk.assert_called_once_with(
            portfolio=second_portfolio
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

        @patch(
        "portfolios.web_views."
        "get_portfolio_performance"
        )
        @patch(
            "portfolios.web_views."
            "get_portfolio_risk_analytics"
        )
        @patch(
            "portfolios.web_views."
            "get_portfolio_market_summary"
        )
        def test_dashboard_loads_recent_transactions(
            self,
            mock_market_summary,
            mock_risk,
            mock_performance,
        ):
            asset = Asset.objects.create(
                ticker="VWCE.DEX",
                name=(
                    "Vanguard FTSE "
                    "All-World UCITS ETF"
                ),
                asset_type="ETF",
                sector="",
                currency="EUR",
            )

            Transaction.objects.create(
                portfolio=self.portfolio,
                asset=asset,
                transaction_type="BUY",
                quantity=Decimal(
                    "10.00000000"
                ),
                price=Decimal(
                    "100.0000"
                ),
                transaction_date=datetime(
                    2026,
                    8,
                    26,
                    12,
                    0,
                    tzinfo=timezone.utc,
                ),
            )

            Transaction.objects.create(
                portfolio=self.portfolio,
                asset=asset,
                transaction_type="BUY",
                quantity=Decimal(
                    "5.00000000"
                ),
                price=Decimal(
                    "120.0000"
                ),
                transaction_date=datetime(
                    2026,
                    8,
                    27,
                    12,
                    0,
                    tzinfo=timezone.utc,
                ),
            )

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
                "positions": [],
            }

            mock_performance.return_value = {
                "portfolio_id": self.portfolio.id,
                "name": self.portfolio.name,
                "currency": "EUR",
                "start_date": None,
                "end_date": None,
                "observations": 0,
                "ending_value": Decimal(
                    "0.00"
                ),
                "net_external_cash_flow": Decimal(
                    "0.00"
                ),
                "time_weighted_return_percentage": Decimal(
                    "0.00"
                ),
                "series": [],
            }

            mock_risk.return_value = {
                "return_observations": 0,
                "annualized_volatility_percentage": Decimal(
                    "0.00"
                ),
                "maximum_drawdown_percentage": Decimal(
                    "0.00"
                ),
            }

            response = self.client.get(
                reverse("web:dashboard")
            )

            transactions = response.context[
                "recent_transactions"
            ]

            self.assertEqual(
                len(transactions),
                2,
            )

            self.assertEqual(
                transactions[0]["quantity"],
                Decimal("5.00000000"),
            )

            self.assertEqual(
            transactions[0]["gross_amount"],
            Decimal("600"),
        )

            self.assertEqual(
                transactions[1]["quantity"],
                Decimal("10.00000000"),
            )

            self.assertEqual(
            transactions[1]["gross_amount"],
            Decimal("1000"),
        )


        

        