from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .models import Transaction
from .portfolio_performance import (
    get_portfolio_performance,
)


PERCENT_PRECISION = Decimal("0.01")
MONEY_PRECISION = Decimal("0.0001")

DAYS_PER_YEAR = 365.0

MINIMUM_RATE = -0.999999
INITIAL_MAXIMUM_RATE = 1.0
MAXIMUM_RATE_LIMIT = 10000.0

XIRR_TOLERANCE = 1e-10
XIRR_MAX_ITERATIONS = 200


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()

    return value


def _to_percentage(value):
    return (
        Decimal(str(value))
        * Decimal("100")
    ).quantize(
        PERCENT_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def _calculate_xnpv(
    *,
    rate,
    cash_flows,
):
    if rate <= -1:
        raise ValueError(
            "Rate must be greater than -1."
        )

    first_date = cash_flows[0]["date"]

    total = 0.0

    for cash_flow in cash_flows:
        days = (
            cash_flow["date"]
            - first_date
        ).days

        years = (
            days / DAYS_PER_YEAR
        )

        total += (
            float(cash_flow["amount"])
            / ((1.0 + rate) ** years)
        )

    return total


def _solve_xirr(*, cash_flows):
    has_negative = any(
        cash_flow["amount"] < 0
        for cash_flow in cash_flows
    )

    has_positive = any(
        cash_flow["amount"] > 0
        for cash_flow in cash_flows
    )

    if not has_negative or not has_positive:
        raise ValidationError(
            "XIRR requires at least one negative "
            "and one positive cash flow."
        )

    lower_rate = MINIMUM_RATE
    upper_rate = INITIAL_MAXIMUM_RATE

    lower_value = _calculate_xnpv(
        rate=lower_rate,
        cash_flows=cash_flows,
    )

    upper_value = _calculate_xnpv(
        rate=upper_rate,
        cash_flows=cash_flows,
    )

    while (
        lower_value * upper_value > 0
        and upper_rate < MAXIMUM_RATE_LIMIT
    ):
        upper_rate = (
            upper_rate * 2
            + 1
        )

        upper_value = _calculate_xnpv(
            rate=upper_rate,
            cash_flows=cash_flows,
        )

    if lower_value * upper_value > 0:
        raise ValidationError(
            "Unable to calculate a money-weighted "
            "return for these cash flows."
        )

    for _ in range(
        XIRR_MAX_ITERATIONS
    ):
        midpoint_rate = (
            lower_rate + upper_rate
        ) / 2

        midpoint_value = _calculate_xnpv(
            rate=midpoint_rate,
            cash_flows=cash_flows,
        )

        if (
            abs(midpoint_value)
            < XIRR_TOLERANCE
        ):
            return midpoint_rate

        if (
            lower_value
            * midpoint_value
            <= 0
        ):
            upper_rate = midpoint_rate
            upper_value = midpoint_value

        else:
            lower_rate = midpoint_rate
            lower_value = midpoint_value

    return (
        lower_rate + upper_rate
    ) / 2


def get_portfolio_money_weighted_performance(
    *,
    portfolio,
):
    performance = (
        get_portfolio_performance(
            portfolio=portfolio
        )
    )

    transactions = list(
        Transaction.objects.filter(
            portfolio=portfolio
        )
        .select_related("asset")
        .order_by(
            "transaction_date",
            "created_at",
            "id",
        )
    )

    if not transactions:
        raise ValidationError(
            "At least one transaction is required "
            "to calculate money-weighted return."
        )

    cash_flows_by_date = defaultdict(
        lambda: Decimal("0")
    )

    cash_flow_events = []

    for transaction in transactions:
        if (
            transaction.asset.currency
            != portfolio.currency
        ):
            raise ValidationError(
                "All transaction assets must use "
                "the portfolio currency."
            )

        transaction_date = _to_date(
            transaction.transaction_date
        )

        transaction_value = (
            transaction.quantity
            * transaction.price
        ).quantize(
            MONEY_PRECISION,
            rounding=ROUND_HALF_UP,
        )

        transaction_type = (
            transaction.transaction_type
            .strip()
            .upper()
        )

        if transaction_type == "BUY":
            investor_cash_flow = (
                -transaction_value
            )

        elif transaction_type == "SELL":
            investor_cash_flow = (
                transaction_value
            )

        else:
            raise ValidationError(
                "Unsupported transaction type."
            )

        cash_flows_by_date[
            transaction_date
        ] += investor_cash_flow

        cash_flow_events.append(
            {
                "date": transaction_date,
                "type": transaction_type,
                "amount": investor_cash_flow,
            }
        )

    ending_value = performance[
        "ending_value"
    ]

    end_date = performance[
        "end_date"
    ]

    if ending_value > 0:
        cash_flows_by_date[
            end_date
        ] += ending_value

        cash_flow_events.append(
            {
                "date": end_date,
                "type": "ENDING_VALUE",
                "amount": ending_value,
            }
        )

    aggregated_cash_flows = [
        {
            "date": cash_flow_date,
            "amount": amount,
        }
        for (
            cash_flow_date,
            amount,
        ) in sorted(
            cash_flows_by_date.items()
        )
        if amount != 0
    ]

    if len(aggregated_cash_flows) < 2:
        raise ValidationError(
            "At least two dated cash flows are "
            "required to calculate XIRR."
        )

    xirr = _solve_xirr(
        cash_flows=aggregated_cash_flows
    )

    cash_flow_events.sort(
        key=lambda item: item["date"]
    )

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "currency": portfolio.currency,
        "start_date": (
            aggregated_cash_flows[0][
                "date"
            ]
        ),
        "end_date": (
            aggregated_cash_flows[-1][
                "date"
            ]
        ),
        "ending_value": ending_value,
        "money_weighted_return_percentage": (
            _to_percentage(xirr)
        ),
        "cash_flows": cash_flow_events,
    }