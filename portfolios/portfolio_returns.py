from decimal import Decimal

from django.core.exceptions import ValidationError

from .portfolio_valuation import (
    build_portfolio_valuation_series,
)


def build_portfolio_return_series(
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
            "for portfolio returns."
        )

    previous_portfolio_value = None

    cumulative_growth_factor = Decimal("1")

    return_points = []
    annualization_supported = True

    series = []

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

        period_return = None

        if (
            previous_portfolio_value
            is not None
            and previous_portfolio_value > 0
        ):
            if not valuation_point["has_market_price_update"]:
                annualization_supported = False

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

        series.append(
            {
                "date": valuation_point[
                    "date"
                ],
                "portfolio_value": (
                    portfolio_value
                ),
                "net_cash_flow": (
                    net_cash_flow
                ),
                "period_return": (
                    period_return
                ),
                "cumulative_growth_factor": (
                    cumulative_growth_factor
                ),
            }
        )

        previous_portfolio_value = (
            portfolio_value
        )

    return {
        "series": series,
        "annualization_supported": annualization_supported,
        "return_points": return_points,
        "cumulative_growth_factor": (
            cumulative_growth_factor
        ),
    }