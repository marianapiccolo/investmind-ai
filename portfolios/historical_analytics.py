from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError


PERCENT_PRECISION = Decimal("0.01")
TRADING_DAYS_PER_YEAR = Decimal("252")


def _to_percentage(value):
    return (
        value * Decimal("100")
    ).quantize(
        PERCENT_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def _calculate_annualized_volatility(
    daily_returns,
):
    if len(daily_returns) < 2:
        return None

    count = Decimal(
        len(daily_returns)
    )

    mean_return = (
        sum(
            daily_returns,
            Decimal("0"),
        )
        / count
    )

    squared_deviations = sum(
        (
            (daily_return - mean_return) ** 2
            for daily_return in daily_returns
        ),
        Decimal("0"),
    )

    sample_variance = (
        squared_deviations
        / Decimal(
            len(daily_returns) - 1
        )
    )

    daily_volatility = (
        sample_variance.sqrt()
    )

    annualized_volatility = (
        daily_volatility
        * TRADING_DAYS_PER_YEAR.sqrt()
    )

    return _to_percentage(
        annualized_volatility
    )


def get_asset_historical_analytics(
    *,
    asset,
):
    prices = list(
        asset.market_prices
        .order_by("date")
        .values(
            "date",
            "close",
        )
    )

    if len(prices) < 2:
        raise ValidationError(
            "At least two historical prices "
            "are required for analytics."
        )

    start_price = prices[0]["close"]
    end_price = prices[-1]["close"]

    daily_returns = []

    series = []

    running_peak = start_price

    maximum_drawdown = Decimal("0")

    for index, price_data in enumerate(
        prices
    ):
        current_price = price_data["close"]

        if index == 0:
            daily_return_percentage = None

        else:
            previous_price = prices[
                index - 1
            ]["close"]

            daily_return = (
                current_price
                / previous_price
                - Decimal("1")
            )

            daily_returns.append(
                daily_return
            )

            daily_return_percentage = (
                _to_percentage(
                    daily_return
                )
            )

        cumulative_return = (
            current_price
            / start_price
            - Decimal("1")
        )

        if current_price > running_peak:
            running_peak = current_price

        drawdown = (
            current_price
            / running_peak
            - Decimal("1")
        )

        if drawdown < maximum_drawdown:
            maximum_drawdown = drawdown

        series.append(
            {
                "date": price_data["date"],
                "close": current_price,
                "daily_return_percentage": (
                    daily_return_percentage
                ),
                "cumulative_return_percentage": (
                    _to_percentage(
                        cumulative_return
                    )
                ),
                "drawdown_percentage": (
                    _to_percentage(
                        drawdown
                    )
                ),
            }
        )

    period_return = (
        end_price
        / start_price
        - Decimal("1")
    )

    annualized_volatility = (
        _calculate_annualized_volatility(
            daily_returns
        )
    )

    return {
        "asset_id": asset.id,
        "ticker": asset.ticker,
        "currency": asset.currency,
        "start_date": prices[0]["date"],
        "end_date": prices[-1]["date"],
        "observations": len(prices),
        "start_price": start_price,
        "end_price": end_price,
        "period_return_percentage": (
            _to_percentage(
                period_return
            )
        ),
        "annualized_volatility_percentage": (
            annualized_volatility
        ),
        "maximum_drawdown_percentage": (
            _to_percentage(
                maximum_drawdown
            )
        ),
        "series": series,
    }