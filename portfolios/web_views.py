from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from portfolios.ai.conversation import (
    continue_ai_conversation,
    start_ai_conversation,
)
from portfolios.ai.openai_client import AIProviderError
from portfolios.ai.tool_calling import (
    InvalidAIToolResponseError,
    ToolCallingLimitError,
)
from portfolios.ai.tools import (
    InvalidPortfolioToolArgumentsError,
    UnknownPortfolioToolError,
)
from portfolios.analytics import (
    get_portfolio_composition_analytics,
)
from portfolios.forms import (
    AIAnalystQuestionForm,
    PortfolioForm,
    TransactionForm,
)
from portfolios.portfolio_diversification import (
    get_portfolio_diversification_analytics,
)
from portfolios.services import create_transaction
from portfolios.tasks import (
    generate_ai_portfolio_report_task,
)

from .integrations.alpha_vantage import MarketDataError
from .models import AIConversation, AIMessage, AIReport, Portfolio, Transaction
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
        return " ".join(str(message) for message in exc.messages)

    return str(exc)


def _load_market_summary(portfolio):
    try:
        data = get_portfolio_market_summary(portfolio=portfolio)

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
        data = get_portfolio_performance(portfolio=portfolio)

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
        data = get_portfolio_risk_analytics(portfolio=portfolio)

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

def _load_composition_analytics(
    portfolio,
):
    try:
        data = get_portfolio_composition_analytics(
            portfolio=portfolio
        )
    except (ValidationError, MarketDataError) as exc:
        return {
            "available": False,
            "data": None,
            "reason": _get_error_message(exc),
        }

    return {
        "available": True,
        "data": data,
        "reason": None,
    }


def _load_diversification_analytics(
    portfolio,
):
    try:
        data = get_portfolio_diversification_analytics(
            portfolio=portfolio
        )
    except (ValidationError, MarketDataError) as exc:
        return {
            "available": False,
            "data": None,
            "reason": _get_error_message(exc),
        }

    return {
        "available": True,
        "data": data,
        "reason": None,
    }

def _build_performance_chart(
    performance,
):
    if not performance["available"]:
        return None

    series = performance["data"]["series"]

    return {
        "labels": [point["date"].isoformat() for point in series],
        "values": [float(point["cumulative_twr_percentage"]) for point in series],
    }


def _build_composition_chart(
    market_summary,
):
    if not market_summary["available"]:
        return None

    positions = market_summary["data"]["positions"]

    if not positions:
        return None

    return {
        "labels": [position["ticker"] for position in positions],
        "values": [float(position["allocation_percentage"]) for position in positions],
    }


def _build_recent_transactions(
    portfolio,
):
    transactions = (
        Transaction.objects.filter(portfolio=portfolio)
        .select_related("asset")
        .order_by(
            "-transaction_date",
            "-id",
        )[:5]
    )

    return [
        {
            "id": transaction.id,
            "transaction_type": (transaction.transaction_type),
            "ticker": (transaction.asset.ticker),
            "asset_name": (transaction.asset.name),
            "quantity": (transaction.quantity),
            "price": (transaction.price),
            "gross_amount": (transaction.quantity * transaction.price),
            "transaction_date": (transaction.transaction_date),
            "currency": (transaction.asset.currency),
        }
        for transaction in transactions
    ]

def _build_allocation_chart(
    allocations,
):
    if not allocations:
        return None

    return {
        "labels": [
            item["label"]
            for item in allocations
        ],
        "values": [
            float(
                item["allocation_percentage"]
            )
            for item in allocations
        ],
    }

def _build_transaction_rows(
    portfolio,
    transaction_type_filter="",
):
    transactions = (
        Transaction.objects.filter(
            portfolio=portfolio
        )
        .select_related("asset")
        .order_by(
            "-transaction_date",
            "-id",
        )
    )

    if transaction_type_filter:
        transactions = transactions.filter(
            transaction_type=(
                transaction_type_filter
            )
        )

    return [
        {
            "id": transaction.id,
            "transaction_type": (
                transaction.transaction_type
            ),
            "ticker": (
                transaction.asset.ticker
            ),
            "asset_name": (
                transaction.asset.name
            ),
            "asset_currency": (
                transaction.asset.currency
            ),
            "currency_symbol": (
                CURRENCY_SYMBOLS.get(
                    transaction.asset.currency,
                    transaction.asset.currency,
                )
            ),
            "quantity": (
                transaction.quantity
            ),
            "price": (
                transaction.price
            ),
            "gross_amount": (
                transaction.quantity
                * transaction.price
            ),
            "transaction_date": (
                transaction.transaction_date
            ),
        }
        for transaction in transactions
    ]

def _get_ai_conversation(
    *,
    raw_conversation_id,
    portfolio,
):
    if (
        not raw_conversation_id
        or portfolio is None
    ):
        return None

    try:
        conversation_id = int(
            raw_conversation_id
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise Http404(
            "Conversation not found."
        ) from exc

    return get_object_or_404(
        AIConversation.objects
        .filter(
            portfolio=portfolio
        )
        .prefetch_related(
            "messages"
        ),
        pk=conversation_id,
    )

def _get_ai_report(
    *,
    raw_report_id,
    portfolio,
    reports,
):
    if portfolio is None:
        return None

    if not raw_report_id:
        return reports.first()

    try:
        report_id = int(
            raw_report_id
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise Http404(
            "AI report not found."
        ) from exc

    return get_object_or_404(
        reports,
        pk=report_id,
    )

def _build_ai_conversation_items(
    conversations,
):
    items = []

    for conversation in conversations:
        first_user_message = next(
            (
                message
                for message
                in conversation.messages.all()
                if message.role
                == AIMessage.Role.USER
            ),
            None,
        )

        title = (
            first_user_message.content
            if first_user_message
            else "Conversation"
        )

        items.append(
            {
                "id": conversation.id,
                "title": title,
                "updated_at": (
                    conversation.updated_at
                ),
            }
        )

    return items

def _get_selected_portfolio(
    *,
    request,
    portfolios,
):
    portfolio_id = request.GET.get("portfolio")

    if portfolio_id is None:
        return portfolios.first()

    try:
        portfolio_id = int(portfolio_id)

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise Http404("Portfolio not found.") from exc

    return get_object_or_404(
        portfolios,
        pk=portfolio_id,
    )


@login_required
def dashboard(request):
    portfolios = Portfolio.objects.filter(user=request.user).order_by("-created_at")

    selected_portfolio = _get_selected_portfolio(
        request=request,
        portfolios=portfolios,
    )

    context = {
        "portfolios": portfolios,
        "selected_portfolio": (selected_portfolio),
        "market_summary": None,
        "performance": None,
        "risk": None,
        "currency_symbol": "",
        "performance_chart": None,
        "composition_chart": None,
        "holdings": [],
        "recent_transactions": [],
    }

    if selected_portfolio is not None:
        context["currency_symbol"] = CURRENCY_SYMBOLS.get(
            selected_portfolio.currency,
            selected_portfolio.currency,
        )

        market_summary = _load_market_summary(selected_portfolio)

        performance = _load_performance(selected_portfolio)

        risk = _load_risk_analytics(selected_portfolio)

        context["market_summary"] = market_summary

        context["performance"] = performance

        context["risk"] = risk

        context["performance_chart"] = _build_performance_chart(performance)

        context["composition_chart"] = _build_composition_chart(market_summary)

        if market_summary["available"]:
            context["holdings"] = market_summary["data"]["positions"]

        context["recent_transactions"] = _build_recent_transactions(selected_portfolio)

    return render(
        request,
        "portfolios/dashboard.html",
        context,
    )

@login_required
def performance(request):
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
        "performance": None,
        "currency_symbol": "",
        "performance_chart": None,
        "daily_return_chart": None,
    }

    if selected_portfolio is not None:
        context["currency_symbol"] = (
            CURRENCY_SYMBOLS.get(
                selected_portfolio.currency,
                selected_portfolio.currency,
            )
        )

        performance_data = (
            _load_performance(
                selected_portfolio
            )
        )

        context["performance"] = (
            performance_data
        )

        if performance_data["available"]:
            series = (
                performance_data[
                    "data"
                ]["series"]
            )

            context[
                "performance_chart"
            ] = {
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

            context[
                "daily_return_chart"
            ] = {
                "labels": [
                    point["date"].isoformat()
                    for point in series
                ],
                "values": [
                    (
                        float(
                            point[
                                "daily_return_percentage"
                            ]
                        )
                        if point[
                            "daily_return_percentage"
                        ]
                        is not None
                        else None
                    )
                    for point in series
                ],
            }

    return render(
        request,
        "portfolios/performance.html",
        context,
    )

def _build_risk_distribution_chart(
    risk,
):
    if not risk["available"]:
        return None

    data = risk["data"]

    return {
        "labels": [
            "Positive periods",
            "Negative periods",
        ],
        "values": [
            data["positive_periods"],
            data["negative_periods"],
        ],
    }


def _build_extreme_return_chart(
    risk,
):
    if not risk["available"]:
        return None

    data = risk["data"]

    return {
        "labels": [
            "Best period",
            "Worst period",
        ],
        "values": [
            float(
                data["best_period"][
                    "return_percentage"
                ]
            ),
            float(
                data["worst_period"][
                    "return_percentage"
                ]
            ),
        ],
    }


@login_required
def risk(request):
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
        "risk": None,
        "currency_symbol": "",
        "risk_distribution_chart": None,
        "extreme_return_chart": None,
    }

    if selected_portfolio is not None:
        context["currency_symbol"] = (
            CURRENCY_SYMBOLS.get(
                selected_portfolio.currency,
                selected_portfolio.currency,
            )
        )

        risk_data = (
            _load_risk_analytics(
                selected_portfolio
            )
        )

        context["risk"] = risk_data

        context[
            "risk_distribution_chart"
        ] = (
            _build_risk_distribution_chart(
                risk_data
            )
        )

        context[
            "extreme_return_chart"
        ] = (
            _build_extreme_return_chart(
                risk_data
            )
        )

    return render(
        request,
        "portfolios/risk.html",
        context,
    )

@login_required
def diversification(request):
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
        "currency_symbol": "",
        "composition": None,
        "diversification": None,
        "asset_type_chart": None,
        "sector_chart": None,
    }

    if selected_portfolio is not None:
        context["currency_symbol"] = (
            CURRENCY_SYMBOLS.get(
                selected_portfolio.currency,
                selected_portfolio.currency,
            )
        )

        composition_data = (
            _load_composition_analytics(
                selected_portfolio
            )
        )

        diversification_data = (
            _load_diversification_analytics(
                selected_portfolio
            )
        )

        context["composition"] = (
            composition_data
        )

        context["diversification"] = (
            diversification_data
        )

        if composition_data["available"]:
            data = composition_data["data"]

            context["asset_type_chart"] = (
                _build_allocation_chart(
                    data[
                        "asset_type_allocation"
                    ]
                )
            )

            context["sector_chart"] = (
                _build_allocation_chart(
                    data[
                        "sector_allocation"
                    ]
                )
            )

    return render(
        request,
        "portfolios/diversification.html",
        context,
    )

@login_required
def portfolio_management(request):
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

    if request.method == "POST":
        form = PortfolioForm(
            request.POST
        )

        if form.is_valid():
            portfolio = form.save(
                commit=False
            )

            portfolio.user = request.user

            portfolio.save()

            messages.success(
                request,
                "Portfolio created successfully.",
            )

            return redirect(
                f"{reverse('web:portfolio')}"
                f"?portfolio={portfolio.id}"
            )

    else:
        form = PortfolioForm()

    context = {
        "portfolios": portfolios,
        "selected_portfolio": (
            selected_portfolio
        ),
        "form": form,
    }

    return render(
        request,
        "portfolios/portfolio.html",
        context,
    )

@login_required
def transaction_management(request):
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

    allowed_types = {
        value
        for value, _label
        in Transaction.TransactionType.choices
    }

    transaction_type_filter = (
        request.GET.get(
            "type",
            "",
        )
        .strip()
        .upper()
    )

    if (
        transaction_type_filter
        not in allowed_types
    ):
        transaction_type_filter = ""

    if request.method == "POST":
        form = TransactionForm(
            request.POST
        )

        if selected_portfolio is None:
            form.add_error(
                None,
                (
                    "Create a portfolio before "
                    "adding transactions."
                ),
            )

        elif form.is_valid():
            try:
                create_transaction(
                    portfolio=(
                        selected_portfolio
                    ),
                    asset=(
                        form.cleaned_data[
                            "asset"
                        ]
                    ),
                    transaction_type=(
                        form.cleaned_data[
                            "transaction_type"
                        ]
                    ),
                    quantity=(
                        form.cleaned_data[
                            "quantity"
                        ]
                    ),
                    price=(
                        form.cleaned_data[
                            "price"
                        ]
                    ),
                    transaction_date=(
                        form.cleaned_data[
                            "transaction_date"
                        ]
                    ),
                )

            except ValidationError as exc:
                for error_message in (
                    exc.messages
                ):
                    form.add_error(
                        None,
                        error_message,
                    )

            else:
                messages.success(
                    request,
                    (
                        "Transaction created "
                        "successfully."
                    ),
                )

                return redirect(
                    (
                        reverse(
                            "web:transactions"
                        )
                        + (
                            "?portfolio="
                            f"{selected_portfolio.id}"
                        )
                    )
                )

    else:
        form = TransactionForm()

    transaction_rows = []

    if selected_portfolio is not None:
        transaction_rows = (
            _build_transaction_rows(
                selected_portfolio,
                transaction_type_filter,
            )
        )

    context = {
        "portfolios": portfolios,
        "selected_portfolio": (
            selected_portfolio
        ),
        "form": form,
        "transactions": (
            transaction_rows
        ),
        "transaction_type_filter": (
            transaction_type_filter
        ),
        "transaction_type_choices": (
            Transaction.TransactionType.choices
        ),
    }

    return render(
        request,
        "portfolios/transactions.html",
        context,
    )

@login_required
def ai_analyst(request):
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

    conversations = (
        AIConversation.objects.none()
    )

    if selected_portfolio is not None:
        conversations = (
            AIConversation.objects
            .filter(
                portfolio=selected_portfolio
            )
            .prefetch_related(
                "messages"
            )
            .order_by(
                "-updated_at",
                "-created_at",
            )
        )

    raw_conversation_id = (
        request.POST.get(
            "conversation"
        )
        if request.method == "POST"
        else request.GET.get(
            "conversation"
        )
    )

    selected_conversation = (
        _get_ai_conversation(
            raw_conversation_id=(
                raw_conversation_id
            ),
            portfolio=selected_portfolio,
        )
    )

    if request.method == "POST":
        form = AIAnalystQuestionForm(
            request.POST
        )

        if selected_portfolio is None:
            form.add_error(
                None,
                (
                    "Create a portfolio before "
                    "using the AI Analyst."
                ),
            )

        elif form.is_valid():
            question = (
                form.cleaned_data[
                    "question"
                ]
            )

            try:
                if (
                    selected_conversation
                    is None
                ):
                    (
                        selected_conversation,
                        _answer,
                    ) = (
                        start_ai_conversation(
                            portfolio=(
                                selected_portfolio
                            ),
                            question=question,
                        )
                    )

                else:
                    continue_ai_conversation(
                        conversation=(
                            selected_conversation
                        ),
                        question=question,
                    )

            except AIProviderError:
                form.add_error(
                    None,
                    (
                        "The AI provider is "
                        "temporarily unavailable. "
                        "Please try again."
                    ),
                )

            except (
                InvalidAIToolResponseError,
                ToolCallingLimitError,
                UnknownPortfolioToolError,
                InvalidPortfolioToolArgumentsError,
            ):
                form.add_error(
                    None,
                    (
                        "The AI analysis could "
                        "not be completed. "
                        "Please try again."
                    ),
                )

            except ValidationError as exc:
                for error_message in (
                    exc.messages
                ):
                    form.add_error(
                        None,
                        error_message,
                    )

            except MarketDataError:
                form.add_error(
                    None,
                    (
                        "Market data is currently "
                        "unavailable. Please try "
                        "again later."
                    ),
                )

            else:
                return redirect(
                    (
                        reverse(
                            "web:ai-analyst"
                        )
                        + (
                            "?portfolio="
                            f"{selected_portfolio.id}"
                            "&conversation="
                            f"{selected_conversation.id}"
                        )
                    )
                )

    else:
        form = AIAnalystQuestionForm()

    conversation_items = (
        _build_ai_conversation_items(
            conversations
        )
    )

    selected_messages = []

    if selected_conversation is not None:
        selected_messages = list(
            selected_conversation
            .messages.all()
        )

    context = {
        "portfolios": portfolios,
        "selected_portfolio": (
            selected_portfolio
        ),
        "conversations": (
            conversation_items
        ),
        "selected_conversation": (
            selected_conversation
        ),
        "selected_messages": (
            selected_messages
        ),
        "form": form,
    }

    return render(
        request,
        "portfolios/ai_analyst.html",
        context,
    )

@login_required
def ai_reports(request):
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

    reports = AIReport.objects.none()

    if selected_portfolio is not None:
        reports = (
            AIReport.objects.filter(
                portfolio=selected_portfolio
            )
            .order_by("-created_at")
        )

    if request.method == "POST":
        if selected_portfolio is None:
            messages.error(
                request,
                (
                    "Create a portfolio before "
                    "generating an AI report."
                ),
            )

            return redirect(
                "web:ai-reports"
            )

        ai_report = AIReport.objects.create(
            portfolio=selected_portfolio,
            model=settings.OPENAI_MODEL,
        )

        task = (
            generate_ai_portfolio_report_task
            .delay(
                ai_report.id
            )
        )

        ai_report.celery_task_id = (
            task.id
        )

        ai_report.save(
            update_fields=[
                "celery_task_id",
                "updated_at",
            ]
        )

        messages.success(
            request,
            "AI report generation started.",
        )

        return redirect(
            (
                reverse(
                    "web:ai-reports"
                )
                + (
                    "?portfolio="
                    f"{selected_portfolio.id}"
                    "&report="
                    f"{ai_report.id}"
                )
            )
        )

    selected_report = (
        _get_ai_report(
            raw_report_id=(
                request.GET.get(
                    "report"
                )
            ),
            portfolio=selected_portfolio,
            reports=reports,
        )
    )

    evaluation_passed = None
    report_content = None
    auto_refresh = False

    if selected_report is not None:
        auto_refresh = (
            selected_report.status
            in {
                AIReport.Status.PENDING,
                AIReport.Status.PROCESSING,
            }
        )

        if (
            selected_report.status
            == AIReport.Status.COMPLETED
        ):
            report_content = (
                selected_report.report
            )

        if selected_report.evaluation:
            evaluation_passed = (
                selected_report.evaluation.get(
                    "passed"
                )
            )

    context = {
        "portfolios": portfolios,
        "selected_portfolio": (
            selected_portfolio
        ),
        "reports": reports,
        "selected_report": (
            selected_report
        ),
        "report_content": (
            report_content
        ),
        "evaluation_passed": (
            evaluation_passed
        ),
        "auto_refresh": (
            auto_refresh
        ),
    }

    return render(
        request,
        "portfolios/ai_reports.html",
        context,
    )