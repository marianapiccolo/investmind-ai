from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError

from .models import MarketPrice, Transaction


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()

    return value


def build_portfolio_valuation_series(
    *,
    portfolio,
):
    transactions = list(
        Transaction.objects.filter(
            portfolio=portfolio
        )
        .select_related("asset")
        .order_by(
            "transaction_date",
            "created_at",
            "id",
        )
    )

    if not transactions:
        raise ValidationError(
            "At least one transaction is required "
            "to calculate portfolio valuation."
        )

    transactions_by_date = defaultdict(list)

    asset_ids = set()

    assets = {}

    for transaction in transactions:
        if (
            transaction.asset.currency
            != portfolio.currency
        ):
            raise ValidationError(
                "All transaction assets must use "
                "the portfolio currency."
            )

        transaction_date = _to_date(
            transaction.transaction_date
        )

        transactions_by_date[
            transaction_date
        ].append(transaction)

        asset_ids.add(
            transaction.asset_id
        )

        assets[
            transaction.asset_id
        ] = {
            "ticker": transaction.asset.ticker,
            "asset_name": transaction.asset.name,
            "sector": (
                transaction.asset.sector
                or "Unclassified"
            ),
        }

    first_transaction_date = min(
        transactions_by_date
    )

    market_prices = (
        MarketPrice.objects.filter(
            asset_id__in=asset_ids
        )
        .order_by(
            "date",
            "asset_id",
        )
    )

    latest_prices = {}

    price_updates_by_date = defaultdict(
        dict
    )

    for market_price in market_prices:
        if (
            market_price.date
            <= first_transaction_date
        ):
            latest_prices[
                market_price.asset_id
            ] = market_price.close

        if (
            market_price.date
            >= first_transaction_date
        ):
            price_updates_by_date[
                market_price.date
            ][
                market_price.asset_id
            ] = market_price.close

    valuation_dates = sorted(
        set(
            transactions_by_date.keys()
        )
        | set(
            price_updates_by_date.keys()
        )
    )

    holdings = defaultdict(
        lambda: Decimal("0")
    )

    series = []

    for valuation_date in valuation_dates:
        for (
            asset_id,
            close,
        ) in price_updates_by_date.get(
            valuation_date,
            {},
        ).items():
            latest_prices[
                asset_id
            ] = close

        asset_cash_flows = defaultdict(
            lambda: Decimal("0")
        )

        for transaction in (
            transactions_by_date.get(
                valuation_date,
                [],
            )
        ):
            transaction_value = (
                transaction.quantity
                * transaction.price
            )

            transaction_type = (
                transaction.transaction_type
                .strip()
                .upper()
            )

            if transaction_type == "BUY":
                holdings[
                    transaction.asset_id
                ] += transaction.quantity

                asset_cash_flows[
                    transaction.asset_id
                ] += transaction_value

            elif transaction_type == "SELL":
                holdings[
                    transaction.asset_id
                ] -= transaction.quantity

                asset_cash_flows[
                    transaction.asset_id
                ] -= transaction_value

            else:
                raise ValidationError(
                    "Unsupported transaction type."
                )

            if (
                holdings[
                    transaction.asset_id
                ]
                < 0
            ):
                raise ValidationError(
                    "Historical transactions result "
                    "in a negative asset quantity."
                )

        asset_values = {}

        portfolio_value = Decimal("0")

        for asset_id in asset_ids:
            quantity = holdings[
                asset_id
            ]

            if quantity == 0:
                asset_values[
                    asset_id
                ] = Decimal("0")

                continue

            market_price = latest_prices.get(
                asset_id
            )

            if market_price is None:
                ticker = assets[
                    asset_id
                ]["ticker"]

                raise ValidationError(
                    "No historical market price "
                    f"is available for {ticker} "
                    f"on or before {valuation_date}."
                )

            asset_value = (
                quantity * market_price
            )

            asset_values[
                asset_id
            ] = asset_value

            portfolio_value += (
                asset_value
            )

        normalized_asset_cash_flows = {
            asset_id: asset_cash_flows[
                asset_id
            ]
            for asset_id in asset_ids
        }

        net_cash_flow = sum(
            normalized_asset_cash_flows.values(),
            Decimal("0"),
        )

        series.append(
            {
                "date": valuation_date,
                "portfolio_value": (
                    portfolio_value
                ),
                "net_cash_flow": (
                    net_cash_flow
                ),
                "asset_values": (
                    asset_values
                ),
                "asset_cash_flows": (
                    normalized_asset_cash_flows
                ),
            }
        )

    return {
        "assets": assets,
        "series": series,
    }