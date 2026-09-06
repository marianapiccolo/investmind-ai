from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .market_data import get_cached_market_quote
from .models import Position, Transaction

AVERAGE_PRICE_PRECISION = Decimal("0.0001")


@transaction.atomic
def create_transaction(
    *,
    portfolio,
    asset,
    transaction_type,
    quantity,
    price,
    transaction_date,
):
    quantity = Decimal(quantity)
    price = Decimal(price)

    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    if price <= 0:
        raise ValidationError("Price must be greater than zero.")

    position = (
        Position.objects.select_for_update()
        .filter(
            portfolio=portfolio,
            asset=asset,
        )
        .first()
    )

    if transaction_type == Transaction.TransactionType.BUY:
        _process_buy(
            portfolio=portfolio,
            asset=asset,
            position=position,
            quantity=quantity,
            price=price,
        )

    elif transaction_type == Transaction.TransactionType.SELL:
        _process_sell(
            position=position,
            quantity=quantity,
        )

    else:
        raise ValidationError("Invalid transaction type.")

    investment_transaction = Transaction.objects.create(
        portfolio=portfolio,
        asset=asset,
        transaction_type=transaction_type,
        quantity=quantity,
        price=price,
        transaction_date=transaction_date,
    )

    return investment_transaction


def _process_buy(*, portfolio, asset, position, quantity, price):
    if position is None:
        return Position.objects.create(
            portfolio=portfolio,
            asset=asset,
            quantity=quantity,
            average_price=price,
        )

    current_cost = position.quantity * position.average_price
    purchase_cost = quantity * price

    new_quantity = position.quantity + quantity

    new_average_price = ((current_cost + purchase_cost) / new_quantity).quantize(
        AVERAGE_PRICE_PRECISION,
        rounding=ROUND_HALF_UP,
    )

    position.quantity = new_quantity
    position.average_price = new_average_price

    position.save(
        update_fields=[
            "quantity",
            "average_price",
            "updated_at",
        ]
    )

    return position


def _process_sell(*, position, quantity):
    if position is None:
        raise ValidationError("Cannot sell an asset that is not in the portfolio.")

    if quantity > position.quantity:
        raise ValidationError(
            "Cannot sell more units than the portfolio currently owns."
        )

    new_quantity = position.quantity - quantity

    if new_quantity == 0:
        position.delete()
        return

    position.quantity = new_quantity

    position.save(
        update_fields=[
            "quantity",
            "updated_at",
        ]
    )


MONEY_PRECISION = Decimal("0.0001")
PERCENT_PRECISION = Decimal("0.01")


def get_portfolio_summary(*, portfolio):
    positions = list(
        portfolio.positions.select_related("asset").order_by("asset__ticker")
    )

    for position in positions:
        if position.asset.currency != portfolio.currency:
            raise ValidationError(
                "Portfolio summary currently supports only "
                "assets in the portfolio currency."
            )

    position_data = []

    for position in positions:
        invested_amount = (position.quantity * position.average_price).quantize(
            MONEY_PRECISION,
            rounding=ROUND_HALF_UP,
        )

        position_data.append(
            {
                "position": position,
                "invested_amount": invested_amount,
            }
        )

    total_invested = sum(
        (item["invested_amount"] for item in position_data),
        Decimal("0"),
    ).quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )

    positions_summary = []

    for item in position_data:
        position = item["position"]
        invested_amount = item["invested_amount"]

        if total_invested == 0:
            allocation_percentage = Decimal("0.00")
        else:
            allocation_percentage = (
                invested_amount / total_invested * Decimal("100")
            ).quantize(
                PERCENT_PRECISION,
                rounding=ROUND_HALF_UP,
            )

        positions_summary.append(
            {
                "asset_id": position.asset.id,
                "ticker": position.asset.ticker,
                "asset_name": position.asset.name,
                "quantity": position.quantity,
                "average_price": position.average_price,
                "invested_amount": invested_amount,
                "allocation_percentage": allocation_percentage,
            }
        )

    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "currency": portfolio.currency,
        "total_invested": total_invested,
        "positions_count": len(positions),
        "positions": positions_summary,
    }


def get_portfolio_market_summary(*, portfolio):
    base_summary = get_portfolio_summary(portfolio=portfolio)

    market_positions = []
    total_market_value = Decimal("0")

    for position in base_summary["positions"]:
        quote = get_cached_market_quote(symbol=position["ticker"])

        current_price = quote["price"]

        market_value = (position["quantity"] * current_price).quantize(
            MONEY_PRECISION,
            rounding=ROUND_HALF_UP,
        )

        unrealized_profit_loss = (market_value - position["invested_amount"]).quantize(
            MONEY_PRECISION,
            rounding=ROUND_HALF_UP,
        )

        if position["invested_amount"] == 0:
            return_percentage = Decimal("0.00")
        else:
            return_percentage = (
                unrealized_profit_loss / position["invested_amount"] * Decimal("100")
            ).quantize(
                PERCENT_PRECISION,
                rounding=ROUND_HALF_UP,
            )

        total_market_value += market_value

        market_positions.append(
            {
                **position,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_profit_loss": unrealized_profit_loss,
                "return_percentage": return_percentage,
                "latest_trading_day": quote["latest_trading_day"],
                "provider": quote["provider"],
            }
        )

    total_market_value = total_market_value.quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )

    total_unrealized_profit_loss = (
        total_market_value - base_summary["total_invested"]
    ).quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )

    if base_summary["total_invested"] == 0:
        total_return_percentage = Decimal("0.00")
    else:
        total_return_percentage = (
            total_unrealized_profit_loss
            / base_summary["total_invested"]
            * Decimal("100")
        ).quantize(
            PERCENT_PRECISION,
            rounding=ROUND_HALF_UP,
        )

    for position in market_positions:
        if total_market_value == 0:
            allocation_percentage = Decimal("0.00")
        else:
            allocation_percentage = (
                position["market_value"] / total_market_value * Decimal("100")
            ).quantize(
                PERCENT_PRECISION,
                rounding=ROUND_HALF_UP,
            )

        position["allocation_percentage"] = allocation_percentage

    return {
        "id": base_summary["id"],
        "name": base_summary["name"],
        "currency": base_summary["currency"],
        "total_invested": base_summary["total_invested"],
        "total_market_value": total_market_value,
        "total_unrealized_profit_loss": (total_unrealized_profit_loss),
        "total_return_percentage": (total_return_percentage),
        "positions_count": base_summary["positions_count"],
        "positions": market_positions,
    }
