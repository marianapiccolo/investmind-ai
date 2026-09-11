from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .portfolio_returns import (
    build_portfolio_return_series,
)


MONEY_PRECISION = Decimal("0.0001")
PERCENT_PRECISION = Decimal("0.01")


def _to_percentage(value):
    return (
        value * Decimal("100")
    ).quantize(
        PERCENT_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def get_portfolio_performance(
    *,
    portfolio,
):
    portfolio_returns = (
        build_portfolio_return_series(
            portfolio=portfolio
        )
    )

    return_series = portfolio_returns[
        "series"
    ]

    cumulative_growth_factor = (
        portfolio_returns[
            "cumulative_growth_factor"
        ]
    )

    net_external_cash_flow = sum(
        (
            point["net_cash_flow"]
            for point in return_series
        ),
        Decimal("0"),
    )

    series = []

    for point in return_series:
        period_return = point[
            "period_return"
        ]

        series.append(
            {
                "date": point["date"],
                "portfolio_value": (
                    point[
                        "portfolio_value"
                    ].quantize(
                        MONEY_PRECISION,
                        rounding=ROUND_HALF_UP,
                    )
                ),
                "net_cash_flow": (
                    point[
                        "net_cash_flow"
                    ].quantize(
                        MONEY_PRECISION,
                        rounding=ROUND_HALF_UP,
                    )
                ),
                "daily_return_percentage": (
                    None
                    if period_return is None
                    else _to_percentage(
                        period_return
                    )
                ),
                "cumulative_twr_percentage": (
                    _to_percentage(
                        point[
                            "cumulative_growth_factor"
                        ]
                        - Decimal("1")
                    )
                ),
            }
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