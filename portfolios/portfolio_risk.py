from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .portfolio_valuation import (
    build_portfolio_valuation_series,
)


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
    returns,
):
    if len(returns) < 2:
        return None

    count = Decimal(
        len(returns)
    )

    mean_return = (
        sum(
            returns,
            Decimal("0"),
        )
        / count
    )

    squared_deviations = sum(
        (
            (period_return - mean_return) ** 2
            for period_return in returns
        ),
        Decimal("0"),
    )

    sample_variance = (
        squared_deviations
        / Decimal(
            len(returns) - 1
        )
    )

    daily_volatility = (
        sample_variance.sqrt()
    )

    annualized_volatility = (
        daily_volatility
        * TRADING_DAYS_PER_YEAR.sqrt()
    )

    return annualized_volatility


def _calculate_annualized_downside_deviation(
    returns,
):
    if not returns:
        return None

    squared_downside_returns = sum(
        (
            min(
                period_return,
                Decimal("0"),
            )
            ** 2
            for period_return in returns
        ),
        Decimal("0"),
    )

    mean_squared_downside = (
        squared_downside_returns
        / Decimal(
            len(returns)
        )
    )

    daily_downside_deviation = (
        mean_squared_downside.sqrt()
    )

    return (
        daily_downside_deviation
        * TRADING_DAYS_PER_YEAR.sqrt()
    )


def get_portfolio_risk_analytics(
    *,
    portfolio,
):
    valuation = (
        build_portfolio_valuation_series(
            portfolio=portfolio
        )
    )

    valuation_series = valuation[
        "series"
    ]

    if not valuation_series:
        raise ValidationError(
            "No valuation data is available "
            "for portfolio risk analytics."
        )

    previous_portfolio_value = None

    return_points = []

    cumulative_growth_factor = Decimal("1")
    running_peak = Decimal("1")

    maximum_drawdown = Decimal("0")

    for valuation_point in valuation_series:
        portfolio_value = (
            valuation_point[
                "portfolio_value"
            ]
        )

        net_cash_flow = (
            valuation_point[
                "net_cash_flow"
            ]
        )

        if (
            previous_portfolio_value
            is not None
            and previous_portfolio_value > 0
        ):
            period_return = (
                (
                    portfolio_value
                    - net_cash_flow
                )
                / previous_portfolio_value
                - Decimal("1")
            )

            cumulative_growth_factor *= (
                Decimal("1")
                + period_return
            )

            if (
                cumulative_growth_factor
                > running_peak
            ):
                running_peak = (
                    cumulative_growth_factor
                )

            drawdown = (
                cumulative_growth_factor
                / running_peak
                - Decimal("1")
            )

            if drawdown < maximum_drawdown:
                maximum_drawdown = drawdown

            return_points.append(
                {
                    "date": valuation_point[
                        "date"
                    ],
                    "return": period_return,
                }
            )

        elif (
            previous_portfolio_value
            is not None
            and previous_portfolio_value == 0
            and portfolio_value > 0
            and net_cash_flow <= 0
        ):
            raise ValidationError(
                "Portfolio performance cannot "
                "restart from zero without an "
                "external cash contribution."
            )

        previous_portfolio_value = (
            portfolio_value
        )

    if not return_points:
        raise ValidationError(
            "At least one portfolio return "
            "observation is required."
        )

    returns = [
        point["return"]
        for point in return_points
    ]

    annualized_volatility = (
        _calculate_annualized_volatility(
            returns
        )
    )

    annualized_downside_deviation = (
        _calculate_annualized_downside_deviation(
            returns
        )
    )

    best_period = max(
        return_points,
        key=lambda point: point["return"],
    )

    worst_period = min(
        return_points,
        key=lambda point: point["return"],
    )

    positive_periods = sum(
        1
        for period_return in returns
        if period_return > 0
    )

    negative_periods = sum(
        1
        for period_return in returns
        if period_return < 0
    )

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "currency": portfolio.currency,
        "start_date": valuation_series[
            0
        ]["date"],
        "end_date": valuation_series[
            -1
        ]["date"],
        "observations": len(
            valuation_series
        ),
        "return_observations": len(
            return_points
        ),
        "time_weighted_return_percentage": (
            _to_percentage(
                cumulative_growth_factor
                - Decimal("1")
            )
        ),
        "annualized_volatility_percentage": (
            None
            if annualized_volatility is None
            else _to_percentage(
                annualized_volatility
            )
        ),
        "annualized_downside_deviation_percentage": (
            None
            if annualized_downside_deviation is None
            else _to_percentage(
                annualized_downside_deviation
            )
        ),
        "maximum_drawdown_percentage": (
            _to_percentage(
                maximum_drawdown
            )
        ),
        "best_period": {
            "date": best_period["date"],
            "return_percentage": (
                _to_percentage(
                    best_period["return"]
                )
            ),
        },
        "worst_period": {
            "date": worst_period["date"],
            "return_percentage": (
                _to_percentage(
                    worst_period["return"]
                )
            ),
        },
        "positive_periods": positive_periods,
        "negative_periods": negative_periods,
    }