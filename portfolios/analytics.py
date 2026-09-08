from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from .services import get_portfolio_market_summary


MONEY_PRECISION = Decimal("0.0001")
PERCENT_PRECISION = Decimal("0.01")
INDEX_PRECISION = Decimal("0.0001")

TOP_HOLDINGS_LIMIT = 3


def _build_allocation_breakdown(
    *,
    totals,
    total_market_value,
):
    breakdown = []

    for label, market_value in totals.items():
        if total_market_value == 0:
            allocation_percentage = Decimal("0.00")
        else:
            allocation_percentage = (
                market_value
                / total_market_value
                * Decimal("100")
            ).quantize(
                PERCENT_PRECISION,
                rounding=ROUND_HALF_UP,
            )

        breakdown.append(
            {
                "label": label,
                "market_value": market_value.quantize(
                    MONEY_PRECISION,
                    rounding=ROUND_HALF_UP,
                ),
                "allocation_percentage": (
                    allocation_percentage
                ),
            }
        )

    return sorted(
        breakdown,
        key=lambda item: item["market_value"],
        reverse=True,
    )


def get_portfolio_composition_analytics(
    *,
    portfolio,
):
    market_summary = get_portfolio_market_summary(
        portfolio=portfolio
    )

    positions = market_summary["positions"]

    total_market_value = market_summary[
        "total_market_value"
    ]

    sector_totals = defaultdict(
        lambda: Decimal("0")
    )

    asset_type_totals = defaultdict(
        lambda: Decimal("0")
    )

    hhi = Decimal("0")

    for position in positions:
        sector_totals[
            position["sector"]
        ] += position["market_value"]

        asset_type_totals[
            position["asset_type"]
        ] += position["market_value"]

        if total_market_value > 0:
            weight = (
                position["market_value"]
                / total_market_value
            )

            hhi += weight * weight

    sorted_positions = sorted(
        positions,
        key=lambda position: (
            position["market_value"]
        ),
        reverse=True,
    )

    top_holdings = [
        {
            "ticker": position["ticker"],
            "asset_name": position[
                "asset_name"
            ],
            "market_value": position[
                "market_value"
            ],
            "allocation_percentage": position[
                "allocation_percentage"
            ],
        }
        for position in sorted_positions[
            :TOP_HOLDINGS_LIMIT
        ]
    ]

    if sorted_positions:
        largest_position_percentage = (
            sorted_positions[0][
                "allocation_percentage"
            ]
        )
    else:
        largest_position_percentage = (
            Decimal("0.00")
        )

    hhi = hhi.quantize(
        INDEX_PRECISION,
        rounding=ROUND_HALF_UP,
    )

    sector_allocation = (
        _build_allocation_breakdown(
            totals=sector_totals,
            total_market_value=(
                total_market_value
            ),
        )
    )

    asset_type_allocation = (
        _build_allocation_breakdown(
            totals=asset_type_totals,
            total_market_value=(
                total_market_value
            ),
        )
    )

    return {
        "id": market_summary["id"],
        "name": market_summary["name"],
        "currency": market_summary["currency"],
        "positions_count": market_summary[
            "positions_count"
        ],
        "total_market_value": (
            total_market_value
        ),
        "largest_position_percentage": (
            largest_position_percentage
        ),
        "hhi_concentration_index": hhi,
        "top_holdings": top_holdings,
        "sector_allocation": sector_allocation,
        "asset_type_allocation": (
            asset_type_allocation
        ),
    }