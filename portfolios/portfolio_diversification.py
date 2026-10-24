from decimal import Decimal, ROUND_HALF_UP
from itertools import combinations

from django.core.exceptions import ValidationError

from .models import MarketPrice, Position


CORRELATION_PRECISION = Decimal("0.0001")
MIN_RETURN_OBSERVATIONS = 3


def _calculate_correlation(
    *,
    asset_prices,
    benchmark_prices,
):
    common_dates = sorted(
        set(asset_prices)
        & set(benchmark_prices)
    )

    if (
        len(common_dates)
        < MIN_RETURN_OBSERVATIONS + 1
    ):
        return (
            None,
            max(
                len(common_dates) - 1,
                0,
            ),
        )

    asset_returns = []
    benchmark_returns = []

    for index in range(
        1,
        len(common_dates),
    ):
        previous_date = common_dates[
            index - 1
        ]

        current_date = common_dates[
            index
        ]

        previous_asset_price = (
            asset_prices[
                previous_date
            ]
        )

        current_asset_price = (
            asset_prices[
                current_date
            ]
        )

        previous_benchmark_price = (
            benchmark_prices[
                previous_date
            ]
        )

        current_benchmark_price = (
            benchmark_prices[
                current_date
            ]
        )

        if (
            previous_asset_price <= 0
            or current_asset_price <= 0
            or previous_benchmark_price <= 0
            or current_benchmark_price <= 0
        ):
            raise ValidationError(
                "Historical market prices "
                "must be greater than zero."
            )

        asset_return = (
            current_asset_price
            / previous_asset_price
            - Decimal("1")
        )

        benchmark_return = (
            current_benchmark_price
            / previous_benchmark_price
            - Decimal("1")
        )

        asset_returns.append(
            asset_return
        )

        benchmark_returns.append(
            benchmark_return
        )

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

    for (
        asset_return,
        benchmark_return,
    ) in zip(
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

    if (
        asset_variance_sum == 0
        or benchmark_variance_sum == 0
    ):
        return (
            None,
            len(asset_returns),
        )

    denominator = (
        asset_variance_sum
        * benchmark_variance_sum
    ).sqrt()

    correlation = (
        covariance_sum / denominator
    ).quantize(
        CORRELATION_PRECISION,
        rounding=ROUND_HALF_UP,
    )

    return (
        correlation,
        len(asset_returns),
    )


def get_portfolio_diversification_analytics(
    *,
    portfolio,
):
    positions = list(
        Position.objects.filter(
            portfolio=portfolio,
            quantity__gt=0,
        )
        .select_related("asset")
        .order_by("asset__ticker")
    )

    if len(positions) < 2:
        raise ValidationError(
            "At least two active assets are "
            "required for diversification analytics."
        )

    assets = {}

    for position in positions:
        asset = position.asset

        if asset.currency != portfolio.currency:
            raise ValidationError(
                "All portfolio assets must use "
                "the portfolio currency."
            )

        assets[asset.id] = {
            "asset_id": asset.id,
            "ticker": asset.ticker,
            "asset_name": asset.name,
        }

    asset_ids = list(
        assets.keys()
    )

    prices_by_asset = {
        asset_id: {}
        for asset_id in asset_ids
    }

    market_prices = (
        MarketPrice.objects.filter(
            asset_id__in=asset_ids
        )
        .order_by(
            "date",
            "asset_id",
        )
    )

    for market_price in market_prices:
        prices_by_asset[
            market_price.asset_id
        ][
            market_price.date
        ] = market_price.close

    matrix = {
        asset_id: {
            other_asset_id: None
            for other_asset_id in asset_ids
        }
        for asset_id in asset_ids
    }

    for asset_id in asset_ids:
        matrix[
            asset_id
        ][
            asset_id
        ] = Decimal("1.0000")

    pair_correlations = []

    valid_pair_correlations = []

    for (
        first_asset_id,
        second_asset_id,
    ) in combinations(
        asset_ids,
        2,
    ):
        correlation, observations = (
            _calculate_correlation(
                asset_prices=(
                    prices_by_asset[
                        first_asset_id
                    ]
                ),
                benchmark_prices=(
                    prices_by_asset[
                        second_asset_id
                    ]
                ),
            )
        )

        matrix[
            first_asset_id
        ][
            second_asset_id
        ] = correlation

        matrix[
            second_asset_id
        ][
            first_asset_id
        ] = correlation

        pair_data = {
            "asset_a_id": first_asset_id,
            "ticker_a": assets[
                first_asset_id
            ]["ticker"],
            "asset_b_id": second_asset_id,
            "ticker_b": assets[
                second_asset_id
            ]["ticker"],
            "return_observations": (
                observations
            ),
            "correlation": correlation,
        }

        pair_correlations.append(
            pair_data
        )

        if correlation is not None:
            valid_pair_correlations.append(
                pair_data
            )

    total_pairs = len(
        pair_correlations
    )

    comparable_pairs = len(
        valid_pair_correlations
    )

    unavailable_pairs = (
        total_pairs - comparable_pairs
    )

    average_pairwise_correlation = None
    most_correlated_pair = None
    least_correlated_pair = None

    if valid_pair_correlations:
        average_pairwise_correlation = (
            sum(
                (
                    pair["correlation"]
                    for pair in (
                        valid_pair_correlations
                    )
                ),
                Decimal("0"),
            )
            / Decimal(
                comparable_pairs
            )
        ).quantize(
            CORRELATION_PRECISION,
            rounding=ROUND_HALF_UP,
        )

        most_correlated_pair = max(
            valid_pair_correlations,
            key=lambda pair: (
                pair["correlation"]
            ),
        )

        least_correlated_pair = min(
            valid_pair_correlations,
            key=lambda pair: (
                pair["correlation"]
            ),
        )

    correlation_matrix = []

    for asset_id in asset_ids:
        correlations = {
            assets[
                other_asset_id
            ]["ticker"]: matrix[
                asset_id
            ][
                other_asset_id
            ]
            for other_asset_id in asset_ids
        }

        correlation_matrix.append(
            {
                "asset_id": asset_id,
                "ticker": assets[
                    asset_id
                ]["ticker"],
                "correlations": (
                    correlations
                ),
            }
        )

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "currency": portfolio.currency,
        "asset_count": len(
            asset_ids
        ),
        "total_pairs": total_pairs,
        "comparable_pairs": (
            comparable_pairs
        ),
        "unavailable_pairs": (
            unavailable_pairs
        ),
        "average_pairwise_correlation": (
            average_pairwise_correlation
        ),
        "most_correlated_pair": (
            most_correlated_pair
        ),
        "least_correlated_pair": (
            least_correlated_pair
        ),
        "pair_correlations": (
            pair_correlations
        ),
        "correlation_matrix": (
            correlation_matrix
        ),
    }