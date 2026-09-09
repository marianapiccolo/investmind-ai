from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError


PERCENT_PRECISION = Decimal("0.01")
METRIC_PRECISION = Decimal("0.0001")
NORMALIZED_PRECISION = Decimal("0.0001")
NORMALIZED_BASE = Decimal("100")


def _to_percentage(value):
    return (
        value * Decimal("100")
    ).quantize(
        PERCENT_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def _calculate_correlation_and_beta(
    *,
    asset_returns,
    benchmark_returns,
):
    if (
        len(asset_returns) < 2
        or len(benchmark_returns) < 2
    ):
        return None, None

    count = Decimal(
        len(asset_returns)
    )

    asset_mean = (
        sum(
            asset_returns,
            Decimal("0"),
        )
        / count
    )

    benchmark_mean = (
        sum(
            benchmark_returns,
            Decimal("0"),
        )
        / count
    )

    covariance_sum = Decimal("0")
    asset_variance_sum = Decimal("0")
    benchmark_variance_sum = Decimal("0")

    for asset_return, benchmark_return in zip(
        asset_returns,
        benchmark_returns,
        strict=True,
    ):
        asset_deviation = (
            asset_return - asset_mean
        )

        benchmark_deviation = (
            benchmark_return
            - benchmark_mean
        )

        covariance_sum += (
            asset_deviation
            * benchmark_deviation
        )

        asset_variance_sum += (
            asset_deviation ** 2
        )

        benchmark_variance_sum += (
            benchmark_deviation ** 2
        )

    divisor = Decimal(
        len(asset_returns) - 1
    )

    covariance = (
        covariance_sum / divisor
    )

    asset_variance = (
        asset_variance_sum / divisor
    )

    benchmark_variance = (
        benchmark_variance_sum / divisor
    )

    correlation = None

    if (
        asset_variance > 0
        and benchmark_variance > 0
    ):
        denominator = (
            asset_variance
            * benchmark_variance
        ).sqrt()

        correlation = (
            covariance / denominator
        ).quantize(
            METRIC_PRECISION,
            rounding=ROUND_HALF_UP,
        )

    beta = None

    if benchmark_variance > 0:
        beta = (
            covariance
            / benchmark_variance
        ).quantize(
            METRIC_PRECISION,
            rounding=ROUND_HALF_UP,
        )

    return correlation, beta


def get_asset_benchmark_comparison(
    *,
    asset,
    benchmark,
):
    if asset.id == benchmark.id:
        raise ValidationError(
            "Asset and benchmark must be different."
        )

    if asset.currency != benchmark.currency:
        raise ValidationError(
            "Asset and benchmark must use "
            "the same currency."
        )

    asset_prices = {
        item["date"]: item["close"]
        for item in (
            asset.market_prices
            .order_by("date")
            .values(
                "date",
                "close",
            )
        )
    }

    benchmark_prices = {
        item["date"]: item["close"]
        for item in (
            benchmark.market_prices
            .order_by("date")
            .values(
                "date",
                "close",
            )
        )
    }

    common_dates = sorted(
        set(asset_prices)
        & set(benchmark_prices)
    )

    if len(common_dates) < 2:
        raise ValidationError(
            "At least two matching historical "
            "price dates are required."
        )

    first_date = common_dates[0]
    last_date = common_dates[-1]

    first_asset_price = (
        asset_prices[first_date]
    )

    first_benchmark_price = (
        benchmark_prices[first_date]
    )

    asset_returns = []
    benchmark_returns = []

    series = []

    for index, price_date in enumerate(
        common_dates
    ):
        asset_price = (
            asset_prices[price_date]
        )

        benchmark_price = (
            benchmark_prices[price_date]
        )

        asset_normalized = (
            asset_price
            / first_asset_price
            * NORMALIZED_BASE
        ).quantize(
            NORMALIZED_PRECISION,
            rounding=ROUND_HALF_UP,
        )

        benchmark_normalized = (
            benchmark_price
            / first_benchmark_price
            * NORMALIZED_BASE
        ).quantize(
            NORMALIZED_PRECISION,
            rounding=ROUND_HALF_UP,
        )

        asset_daily_return_percentage = None
        benchmark_daily_return_percentage = None

        if index > 0:
            previous_date = (
                common_dates[index - 1]
            )

            asset_daily_return = (
                asset_price
                / asset_prices[
                    previous_date
                ]
                - Decimal("1")
            )

            benchmark_daily_return = (
                benchmark_price
                / benchmark_prices[
                    previous_date
                ]
                - Decimal("1")
            )

            asset_returns.append(
                asset_daily_return
            )

            benchmark_returns.append(
                benchmark_daily_return
            )

            asset_daily_return_percentage = (
                _to_percentage(
                    asset_daily_return
                )
            )

            benchmark_daily_return_percentage = (
                _to_percentage(
                    benchmark_daily_return
                )
            )

        series.append(
            {
                "date": price_date,
                "asset_normalized": (
                    asset_normalized
                ),
                "benchmark_normalized": (
                    benchmark_normalized
                ),
                "asset_daily_return_percentage": (
                    asset_daily_return_percentage
                ),
                "benchmark_daily_return_percentage": (
                    benchmark_daily_return_percentage
                ),
            }
        )

    asset_period_return = (
        asset_prices[last_date]
        / first_asset_price
        - Decimal("1")
    )

    benchmark_period_return = (
        benchmark_prices[last_date]
        / first_benchmark_price
        - Decimal("1")
    )

    asset_period_return_percentage = (
        _to_percentage(
            asset_period_return
        )
    )

    benchmark_period_return_percentage = (
        _to_percentage(
            benchmark_period_return
        )
    )

    excess_return_percentage_points = (
        asset_period_return_percentage
        - benchmark_period_return_percentage
    ).quantize(
        PERCENT_PRECISION,
        rounding=ROUND_HALF_UP,
    )

    correlation, beta = (
        _calculate_correlation_and_beta(
            asset_returns=asset_returns,
            benchmark_returns=(
                benchmark_returns
            ),
        )
    )

    return {
        "asset_id": asset.id,
        "ticker": asset.ticker,
        "benchmark_id": benchmark.id,
        "benchmark_ticker": (
            benchmark.ticker
        ),
        "currency": asset.currency,
        "start_date": first_date,
        "end_date": last_date,
        "observations": len(
            common_dates
        ),
        "asset_period_return_percentage": (
            asset_period_return_percentage
        ),
        "benchmark_period_return_percentage": (
            benchmark_period_return_percentage
        ),
        "excess_return_percentage_points": (
            excess_return_percentage_points
        ),
        "return_correlation": correlation,
        "beta": beta,
        "series": series,
    }