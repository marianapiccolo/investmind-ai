from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .portfolio_valuation import (
    build_portfolio_valuation_series,
)


PERCENT_PRECISION = Decimal("0.01")


def _to_percentage_points(value):
    return (
        value * Decimal("100")
    ).quantize(
        PERCENT_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def get_portfolio_performance_attribution(
    *,
    portfolio,
):
    valuation = (
        build_portfolio_valuation_series(
            portfolio=portfolio
        )
    )

    assets = valuation["assets"]

    valuation_series = valuation[
        "series"
    ]

    daily_periods = []

    previous_point = None

    for current_point in valuation_series:
        if previous_point is None:
            previous_point = current_point
            continue

        previous_portfolio_value = (
            previous_point[
                "portfolio_value"
            ]
        )

        current_portfolio_value = (
            current_point[
                "portfolio_value"
            ]
        )

        current_cash_flow = (
            current_point[
                "net_cash_flow"
            ]
        )

        if previous_portfolio_value > 0:
            portfolio_return = (
                (
                    current_portfolio_value
                    - current_cash_flow
                )
                / previous_portfolio_value
                - Decimal("1")
            )

            asset_contributions = {}

            for asset_id in assets:
                previous_asset_value = (
                    previous_point[
                        "asset_values"
                    ].get(
                        asset_id,
                        Decimal("0"),
                    )
                )

                current_asset_value = (
                    current_point[
                        "asset_values"
                    ].get(
                        asset_id,
                        Decimal("0"),
                    )
                )

                asset_cash_flow = (
                    current_point[
                        "asset_cash_flows"
                    ].get(
                        asset_id,
                        Decimal("0"),
                    )
                )

                adjusted_asset_pnl = (
                    current_asset_value
                    - previous_asset_value
                    - asset_cash_flow
                )

                asset_contributions[
                    asset_id
                ] = (
                    adjusted_asset_pnl
                    / previous_portfolio_value
                )

            daily_periods.append(
                {
                    "portfolio_return": (
                        portfolio_return
                    ),
                    "asset_contributions": (
                        asset_contributions
                    ),
                }
            )

        elif (
            previous_portfolio_value == 0
            and current_portfolio_value > 0
            and current_cash_flow <= 0
        ):
            raise ValidationError(
                "Portfolio performance cannot "
                "restart from zero without an "
                "external cash contribution."
            )

        previous_point = current_point

    linked_asset_contributions = defaultdict(
        lambda: Decimal("0")
    )

    future_growth_factor = Decimal("1")

    for period in reversed(
        daily_periods
    ):
        for (
            asset_id,
            contribution,
        ) in period[
            "asset_contributions"
        ].items():
            linked_asset_contributions[
                asset_id
            ] += (
                contribution
                * future_growth_factor
            )

        future_growth_factor *= (
            Decimal("1")
            + period[
                "portfolio_return"
            ]
        )

    time_weighted_return = (
        future_growth_factor
        - Decimal("1")
    )

    asset_contributions = []

    sector_contributions = defaultdict(
        lambda: Decimal("0")
    )

    for asset_id, asset_data in (
        assets.items()
    ):
        contribution = (
            linked_asset_contributions[
                asset_id
            ]
        )

        asset_contributions.append(
            {
                "asset_id": asset_id,
                "ticker": asset_data[
                    "ticker"
                ],
                "asset_name": asset_data[
                    "asset_name"
                ],
                "sector": asset_data[
                    "sector"
                ],
                "contribution_percentage_points": (
                    _to_percentage_points(
                        contribution
                    )
                ),
            }
        )

        sector_contributions[
            asset_data["sector"]
        ] += contribution

    asset_contributions.sort(
        key=lambda item: (
            item[
                "contribution_percentage_points"
            ]
        ),
        reverse=True,
    )

    sector_contribution_list = [
        {
            "sector": sector,
            "contribution_percentage_points": (
                _to_percentage_points(
                    contribution
                )
            ),
        }
        for (
            sector,
            contribution,
        ) in sector_contributions.items()
    ]

    sector_contribution_list.sort(
        key=lambda item: (
            item[
                "contribution_percentage_points"
            ]
        ),
        reverse=True,
    )

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "currency": portfolio.currency,
        "start_date": (
            valuation_series[0]["date"]
        ),
        "end_date": (
            valuation_series[-1]["date"]
        ),
        "observations": len(
            valuation_series
        ),
        "time_weighted_return_percentage": (
            _to_percentage_points(
                time_weighted_return
            )
        ),
        "asset_contributions": (
            asset_contributions
        ),
        "sector_contributions": (
            sector_contribution_list
        ),
    }