from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .portfolio_returns import (
    build_portfolio_return_series,
)


TRADING_DAYS_PER_YEAR = Decimal("252")

PERCENT_PRECISION = Decimal("0.01")
RATE_PRECISION = Decimal("0.000001")
RATIO_PRECISION = Decimal("0.0001")


def _to_percentage(
    value,
    *,
    precision=PERCENT_PRECISION,
):
    return (
        value * Decimal("100")
    ).quantize(
        precision,
        rounding=ROUND_HALF_UP,
    )


def _annual_to_periodic_rate(
    annual_rate_percentage,
):
    if (
        annual_rate_percentage
        <= Decimal("-100")
    ):
        raise ValidationError(
            "Annual risk-free rate must "
            "be greater than -100%."
        )

    annual_rate = (
        annual_rate_percentage
        / Decimal("100")
    )

    periodic_rate = (
        (
            1.0
            + float(annual_rate)
        )
        ** (
            1.0
            / float(
                TRADING_DAYS_PER_YEAR
            )
        )
        - 1.0
    )

    return Decimal(
        str(periodic_rate)
    )


def _calculate_sample_standard_deviation(
    values,
):
    if len(values) < 2:
        return None

    count = Decimal(
        len(values)
    )

    mean_value = (
        sum(
            values,
            Decimal("0"),
        )
        / count
    )

    squared_deviations = sum(
        (
            (value - mean_value) ** 2
            for value in values
        ),
        Decimal("0"),
    )

    sample_variance = (
        squared_deviations
        / Decimal(
            len(values) - 1
        )
    )

    return sample_variance.sqrt()


def _calculate_downside_deviation(
    excess_returns,
):
    if not excess_returns:
        return None

    squared_downside_returns = sum(
        (
            min(
                excess_return,
                Decimal("0"),
            )
            ** 2
            for excess_return in excess_returns
        ),
        Decimal("0"),
    )

    mean_squared_downside = (
        squared_downside_returns
        / Decimal(
            len(excess_returns)
        )
    )

    return (
        mean_squared_downside.sqrt()
    )


def get_portfolio_risk_adjusted_performance(
    *,
    portfolio,
    annual_risk_free_rate_percentage,
):
    portfolio_returns = (
        build_portfolio_return_series(
            portfolio=portfolio
        )
    )

    return_points = portfolio_returns[
        "return_points"
    ]

    return_series = portfolio_returns[
        "series"
    ]

    if len(return_points) < 2:
        raise ValidationError(
            "At least two portfolio return "
            "observations are required for "
            "risk-adjusted performance."
        )

    periodic_risk_free_rate = (
        _annual_to_periodic_rate(
            annual_risk_free_rate_percentage
        )
    )

    returns = [
        point["return"]
        for point in return_points
    ]

    excess_returns = [
        period_return
        - periodic_risk_free_rate
        for period_return in returns
    ]

    mean_excess_return = (
        sum(
            excess_returns,
            Decimal("0"),
        )
        / Decimal(
            len(excess_returns)
        )
    )

    portfolio_volatility = (
        _calculate_sample_standard_deviation(
            returns
        )
    )

    downside_deviation = (
        _calculate_downside_deviation(
            excess_returns
        )
    )

    annualization_factor = (
        TRADING_DAYS_PER_YEAR.sqrt()
    )

    sharpe_ratio = None

    if (
        portfolio_volatility is not None
        and portfolio_volatility > 0
    ):
        sharpe_ratio = (
            mean_excess_return
            / portfolio_volatility
            * annualization_factor
        ).quantize(
            RATIO_PRECISION,
            rounding=ROUND_HALF_UP,
        )

    sortino_ratio = None

    if (
        downside_deviation is not None
        and downside_deviation > 0
    ):
        sortino_ratio = (
            mean_excess_return
            / downside_deviation
            * annualization_factor
        ).quantize(
            RATIO_PRECISION,
            rounding=ROUND_HALF_UP,
        )

    cumulative_growth_factor = (
        portfolio_returns[
            "cumulative_growth_factor"
        ]
    )

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "currency": portfolio.currency,
        "start_date": return_series[
            0
        ]["date"],
        "end_date": return_series[
            -1
        ]["date"],
        "return_observations": len(
            return_points
        ),
        "annual_risk_free_rate_percentage": (
            annual_risk_free_rate_percentage.quantize(
                Decimal("0.0001"),
                rounding=ROUND_HALF_UP,
            )
        ),
        "periodic_risk_free_rate_percentage": (
            _to_percentage(
                periodic_risk_free_rate,
                precision=RATE_PRECISION,
            )
        ),
        "time_weighted_return_percentage": (
            _to_percentage(
                cumulative_growth_factor
                - Decimal("1")
            )
        ),
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
    }