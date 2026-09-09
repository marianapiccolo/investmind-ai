from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .models import MarketPrice, Transaction


MONEY_PRECISION = Decimal("0.0001")
PERCENT_PRECISION = Decimal("0.01")


def _to_percentage(value):
    return (
        value * Decimal("100")
    ).quantize(
        PERCENT_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()

    return value


def get_portfolio_performance(
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
            "to calculate portfolio performance."
        )

    first_transaction_date = _to_date(
        transactions[0].transaction_date
    )

    transactions_by_date = defaultdict(
        list
    )

    asset_ids = set()

    asset_tickers = {}

    for transaction in transactions:
        transaction_date = _to_date(
            transaction.transaction_date
        )

        transactions_by_date[
            transaction_date
        ].append(transaction)

        asset_ids.add(
            transaction.asset_id
        )

        asset_tickers[
            transaction.asset_id
        ] = transaction.asset.ticker

    market_prices = (
        MarketPrice.objects.filter(
            asset_id__in=asset_ids
        )
        .order_by(
            "date",
            "asset_id",
        )
    )

    price_updates_by_date = defaultdict(
        dict
    )

    latest_prices = {}

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

    previous_portfolio_value = None

    cumulative_growth_factor = Decimal("1")

    net_external_cash_flow = Decimal("0")

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

        daily_cash_flow = Decimal("0")

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

                daily_cash_flow += (
                    transaction_value
                )

            elif transaction_type == "SELL":
                holdings[
                    transaction.asset_id
                ] -= transaction.quantity

                daily_cash_flow -= (
                    transaction_value
                )

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

        portfolio_value = Decimal("0")

        for (
            asset_id,
            quantity,
        ) in holdings.items():
            if quantity == 0:
                continue

            market_price = (
                latest_prices.get(
                    asset_id
                )
            )

            if market_price is None:
                ticker = asset_tickers[
                    asset_id
                ]

                raise ValidationError(
                    "No historical market price "
                    f"is available for {ticker} "
                    f"on or before {valuation_date}."
                )

            portfolio_value += (
                quantity
                * market_price
            )

        portfolio_value = (
            portfolio_value.quantize(
                MONEY_PRECISION,
                rounding=ROUND_HALF_UP,
            )
        )

        daily_cash_flow = (
            daily_cash_flow.quantize(
                MONEY_PRECISION,
                rounding=ROUND_HALF_UP,
            )
        )

        net_external_cash_flow += (
            daily_cash_flow
        )

        daily_return = None

        if (
            previous_portfolio_value
            is not None
            and previous_portfolio_value > 0
        ):
            daily_return = (
                (
                    portfolio_value
                    - daily_cash_flow
                )
                / previous_portfolio_value
                - Decimal("1")
            )

            cumulative_growth_factor *= (
                Decimal("1")
                + daily_return
            )

        elif (
            previous_portfolio_value
            is not None
            and previous_portfolio_value == 0
            and portfolio_value > 0
            and daily_cash_flow <= 0
        ):
            raise ValidationError(
                "Portfolio performance cannot "
                "restart from zero without an "
                "external cash contribution."
            )

        series.append(
            {
                "date": valuation_date,
                "portfolio_value": (
                    portfolio_value
                ),
                "net_cash_flow": (
                    daily_cash_flow
                ),
                "daily_return_percentage": (
                    None
                    if daily_return is None
                    else _to_percentage(
                        daily_return
                    )
                ),
                "cumulative_twr_percentage": (
                    _to_percentage(
                        cumulative_growth_factor
                        - Decimal("1")
                    )
                ),
            }
        )

        previous_portfolio_value = (
            portfolio_value
        )

    if not series:
        raise ValidationError(
            "No valuation dates are available "
            "for portfolio performance."
        )

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "currency": portfolio.currency,
        "start_date": series[0]["date"],
        "end_date": series[-1]["date"],
        "observations": len(series),
        "ending_value": series[-1][
            "portfolio_value"
        ],
        "net_external_cash_flow": (
            net_external_cash_flow.quantize(
                MONEY_PRECISION,
                rounding=ROUND_HALF_UP,
            )
        ),
        "time_weighted_return_percentage": (
            _to_percentage(
                cumulative_growth_factor
                - Decimal("1")
            )
        ),
        "series": series,
    }