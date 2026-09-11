from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .portfolio_valuation import (
    build_portfolio_valuation_series,
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
    valuation = (
        build_portfolio_valuation_series(
            portfolio=portfolio
        )
    )

    valuation_series = valuation[
        "series"
    ]

    previous_portfolio_value = None

    cumulative_growth_factor = Decimal("1")

    net_external_cash_flow = Decimal("0")

    series = []

    for valuation_point in valuation_series:
        portfolio_value = (
            valuation_point[
                "portfolio_value"
            ]
        )

        daily_cash_flow = (
            valuation_point[
                "net_cash_flow"
            ]
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
                "date": valuation_point[
                    "date"
                ],
                "portfolio_value": (
                    portfolio_value.quantize(
                        MONEY_PRECISION,
                        rounding=ROUND_HALF_UP,
                    )
                ),
                "net_cash_flow": (
                    daily_cash_flow.quantize(
                        MONEY_PRECISION,
                        rounding=ROUND_HALF_UP,
                    )
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