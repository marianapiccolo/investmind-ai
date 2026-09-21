from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError

from portfolios.analytics import (
    get_portfolio_composition_analytics,
)
from portfolios.integrations.alpha_vantage import (
    MarketDataError,
)
from portfolios.money_weighted_performance import (
    get_portfolio_money_weighted_performance,
)
from portfolios.performance_attribution import (
    get_portfolio_performance_attribution,
)
from portfolios.portfolio_diversification import (
    get_portfolio_diversification_analytics,
)
from portfolios.portfolio_performance import (
    get_portfolio_performance,
)
from portfolios.portfolio_risk import (
    get_portfolio_risk_analytics,
)


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)

    if isinstance(
        value,
        (date, datetime),
    ):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _json_safe(item)
            for item in value
        ]

    return value


def _unavailable(reason):
    return {
        "available": False,
        "reason": reason,
    }


def _available(data):
    return {
        "available": True,
        "data": _json_safe(data),
    }


def _validation_reason(exc):
    if hasattr(exc, "messages"):
        return " ".join(exc.messages)

    return str(exc)


def build_ai_portfolio_context(
    *,
    portfolio,
):
    sections = {}

    try:
        composition = (
            get_portfolio_composition_analytics(
                portfolio=portfolio
            )
        )

        sections["composition"] = _available(
            {
                "positions_count": composition[
                    "positions_count"
                ],
                "total_market_value": composition[
                    "total_market_value"
                ],
                "largest_position_percentage": (
                    composition[
                        "largest_position_percentage"
                    ]
                ),
                "hhi_concentration_index": (
                    composition[
                        "hhi_concentration_index"
                    ]
                ),
                "top_holdings": composition[
                    "top_holdings"
                ],
                "sector_allocation": composition[
                    "sector_allocation"
                ],
                "asset_type_allocation": composition[
                    "asset_type_allocation"
                ],
            }
        )

    except (
        ValidationError,
        MarketDataError,
    ) as exc:
        sections["composition"] = (
            _unavailable(
                _validation_reason(exc)
            )
        )

    try:
        performance = get_portfolio_performance(
            portfolio=portfolio
        )

        sections["performance"] = _available(
            {
                "start_date": performance[
                    "start_date"
                ],
                "end_date": performance[
                    "end_date"
                ],
                "observations": performance[
                    "observations"
                ],
                "ending_value": performance[
                    "ending_value"
                ],
                "net_external_cash_flow": (
                    performance[
                        "net_external_cash_flow"
                    ]
                ),
                "time_weighted_return_percentage": (
                    performance[
                        "time_weighted_return_percentage"
                    ]
                ),
            }
        )

    except ValidationError as exc:
        sections["performance"] = (
            _unavailable(
                _validation_reason(exc)
            )
        )

    try:
        money_weighted = (
            get_portfolio_money_weighted_performance(
                portfolio=portfolio
            )
        )

        sections[
            "money_weighted_performance"
        ] = _available(
            {
                "start_date": money_weighted[
                    "start_date"
                ],
                "end_date": money_weighted[
                    "end_date"
                ],
                "ending_value": money_weighted[
                    "ending_value"
                ],
                "money_weighted_return_percentage": (
                    money_weighted[
                        "money_weighted_return_percentage"
                    ]
                ),
            }
        )

    except ValidationError as exc:
        sections[
            "money_weighted_performance"
        ] = _unavailable(
            _validation_reason(exc)
        )

    try:
        risk = get_portfolio_risk_analytics(
            portfolio=portfolio
        )

        sections["risk"] = _available(
            risk
        )

    except ValidationError as exc:
        sections["risk"] = _unavailable(
            _validation_reason(exc)
        )

    try:
        attribution = (
            get_portfolio_performance_attribution(
                portfolio=portfolio
            )
        )

        sections["attribution"] = _available(
            {
                "time_weighted_return_percentage": (
                    attribution[
                        "time_weighted_return_percentage"
                    ]
                ),
                "asset_contributions": (
                    attribution[
                        "asset_contributions"
                    ][:5]
                ),
                "sector_contributions": (
                    attribution[
                        "sector_contributions"
                    ][:5]
                ),
            }
        )

    except ValidationError as exc:
        sections["attribution"] = (
            _unavailable(
                _validation_reason(exc)
            )
        )

    try:
        diversification = (
            get_portfolio_diversification_analytics(
                portfolio=portfolio
            )
        )

        sections[
            "diversification"
        ] = _available(
            {
                "asset_count": diversification[
                    "asset_count"
                ],
                "total_pairs": diversification[
                    "total_pairs"
                ],
                "comparable_pairs": (
                    diversification[
                        "comparable_pairs"
                    ]
                ),
                "unavailable_pairs": (
                    diversification[
                        "unavailable_pairs"
                    ]
                ),
                "average_pairwise_correlation": (
                    diversification[
                        "average_pairwise_correlation"
                    ]
                ),
                "most_correlated_pair": (
                    diversification[
                        "most_correlated_pair"
                    ]
                ),
                "least_correlated_pair": (
                    diversification[
                        "least_correlated_pair"
                    ]
                ),
            }
        )

    except ValidationError as exc:
        sections[
            "diversification"
        ] = _unavailable(
            _validation_reason(exc)
        )

    return _json_safe(
        {
            "portfolio": {
                "id": portfolio.id,
                "name": portfolio.name,
                "currency": portfolio.currency,
            },
            "sections": sections,
        }
    )