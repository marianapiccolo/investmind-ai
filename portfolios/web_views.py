from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .integrations.alpha_vantage import MarketDataError
from .models import Portfolio
from .portfolio_performance import (
    get_portfolio_performance,
)
from .portfolio_risk import (
    get_portfolio_risk_analytics,
)
from .services import (
    get_portfolio_market_summary,
)


CURRENCY_SYMBOLS = {
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
}


def _get_error_message(exc):
    if isinstance(
        exc,
        ValidationError,
    ):
        return " ".join(
            str(message)
            for message in exc.messages
        )

    return str(exc)


def _load_market_summary(portfolio):
    try:
        data = get_portfolio_market_summary(
            portfolio=portfolio
        )

    except (
        ValidationError,
        MarketDataError,
    ) as exc:
        return {
            "available": False,
            "data": None,
            "reason": _get_error_message(exc),
        }

    return {
        "available": True,
        "data": data,
        "reason": "",
    }


def _load_performance(portfolio):
    try:
        data = get_portfolio_performance(
            portfolio=portfolio
        )

    except ValidationError as exc:
        return {
            "available": False,
            "data": None,
            "reason": _get_error_message(exc),
        }

    return {
        "available": True,
        "data": data,
        "reason": "",
    }


def _load_risk_analytics(portfolio):
    try:
        data = get_portfolio_risk_analytics(
            portfolio=portfolio
        )

    except ValidationError as exc:
        return {
            "available": False,
            "data": None,
            "reason": _get_error_message(exc),
        }

    return {
        "available": True,
        "data": data,
        "reason": "",
    }


def _build_performance_chart(
    performance,
):
    if not performance["available"]:
        return None

    series = performance["data"]["series"]

    return {
        "labels": [
            point["date"].isoformat()
            for point in series
        ],
        "values": [
            float(
                point[
                    "cumulative_twr_percentage"
                ]
            )
            for point in series
        ],
    }


def _build_composition_chart(
    market_summary,
):
    if not market_summary["available"]:
        return None

    positions = (
        market_summary["data"]["positions"]
    )

    if not positions:
        return None

    return {
        "labels": [
            position["ticker"]
            for position in positions
        ],
        "values": [
            float(
                position[
                    "allocation_percentage"
                ]
            )
            for position in positions
        ],
    }


def _get_selected_portfolio(
    *,
    request,
    portfolios,
):
    portfolio_id = request.GET.get(
        "portfolio"
    )

    if portfolio_id is None:
        return portfolios.first()

    try:
        portfolio_id = int(portfolio_id)

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise Http404(
            "Portfolio not found."
        ) from exc

    return get_object_or_404(
        portfolios,
        pk=portfolio_id,
    )


@login_required
def dashboard(request):
    portfolios = (
        Portfolio.objects.filter(
            user=request.user
        )
        .order_by("-created_at")
    )

    selected_portfolio = (
        _get_selected_portfolio(
            request=request,
            portfolios=portfolios,
        )
    )

    context = {
        "portfolios": portfolios,
        "selected_portfolio": (
            selected_portfolio
        ),
        "market_summary": None,
        "performance": None,
        "risk": None,
        "currency_symbol": "",
        "performance_chart": None,
        "composition_chart": None,
    }

    if selected_portfolio is not None:
        context["currency_symbol"] = (
            CURRENCY_SYMBOLS.get(
                selected_portfolio.currency,
                selected_portfolio.currency,
            )
        )

        market_summary = (
            _load_market_summary(
                selected_portfolio
            )
        )

        performance = (
            _load_performance(
                selected_portfolio
            )
        )

        risk = (
            _load_risk_analytics(
                selected_portfolio
            )
        )

        context["market_summary"] = (
            market_summary
        )

        context["performance"] = (
            performance
        )

        context["risk"] = risk

        context["performance_chart"] = (
            _build_performance_chart(
                performance
            )
        )

        context["composition_chart"] = (
            _build_composition_chart(
                market_summary
            )
        )

    return render(
        request,
        "portfolios/dashboard.html",
        context,
    )