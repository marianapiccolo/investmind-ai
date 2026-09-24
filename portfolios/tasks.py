import logging

from celery import shared_task
from django.utils import timezone

from .ai.evals import (
    evaluate_ai_portfolio_report,
)
from .ai.openai_client import (
    AIProviderError,
)
from .ai.portfolio_context import (
    build_ai_portfolio_context,
)
from .ai.portfolio_report import (
    generate_ai_portfolio_report,
)
from .historical_market_data import (
    sync_asset_market_history,
)
from .market_data import refresh_market_quote
from .models import AIReport, Asset

logger = logging.getLogger(__name__)


@shared_task
def refresh_market_quote_task(symbol):
    logger.info(
        "Refreshing market quote for symbol=%s",
        symbol,
    )

    quote = refresh_market_quote(symbol=symbol)

    logger.info(
        "Market quote refreshed successfully for symbol=%s",
        symbol,
    )

    return quote["symbol"]


@shared_task
def schedule_active_market_quote_refreshes():

    logger.info("Scheduling active market quote refreshes.")
    symbols = (
        Asset.objects.filter(positions__isnull=False)
        .values_list("ticker", flat=True)
        .distinct()
        .order_by("ticker")
    )

    scheduled_count = 0

    for symbol in symbols:
        refresh_market_quote_task.delay(symbol)
        scheduled_count += 1

    logger.info(
        "Scheduled %s market quote refresh tasks.",
        scheduled_count,
    )
    return scheduled_count


@shared_task
def sync_asset_market_history_task(asset_id):
    asset = Asset.objects.get(id=asset_id)

    logger.info(
        "Synchronizing historical market data for symbol=%s",
        asset.ticker,
    )

    result = sync_asset_market_history(asset=asset)

    logger.info(
        "Historical market data synchronized for symbol=%s total=%s",
        asset.ticker,
        result["total"],
    )

    return result["total"]


@shared_task
def generate_ai_portfolio_report_task(
    ai_report_id,
):
    ai_report = AIReport.objects.select_related("portfolio").get(id=ai_report_id)

    ai_report.status = AIReport.Status.PROCESSING

    ai_report.started_at = timezone.now()

    ai_report.error_message = ""

    ai_report.save(
        update_fields=[
            "status",
            "started_at",
            "error_message",
            "updated_at",
        ]
    )

    try:
        context = build_ai_portfolio_context(portfolio=(ai_report.portfolio))

        report = generate_ai_portfolio_report(
            portfolio=(ai_report.portfolio),
            context=context,
        )

        evaluation = evaluate_ai_portfolio_report(
            context=context,
            report=report,
        )

        ai_report.context_snapshot = context

        ai_report.report = report

        ai_report.evaluation = evaluation

        if evaluation["passed"]:
            ai_report.status = AIReport.Status.COMPLETED

        else:
            ai_report.status = AIReport.Status.REJECTED

        ai_report.completed_at = timezone.now()

        ai_report.save(
            update_fields=[
                "context_snapshot",
                "report",
                "evaluation",
                "status",
                "completed_at",
                "updated_at",
            ]
        )

        return {
            "ai_report_id": (ai_report.id),
            "status": (ai_report.status),
        }

    except AIProviderError:
        ai_report.status = AIReport.Status.FAILED

        ai_report.error_message = "AI provider is unavailable."

        ai_report.completed_at = timezone.now()

        ai_report.save(
            update_fields=[
                "status",
                "error_message",
                "completed_at",
                "updated_at",
            ]
        )

        raise

    except Exception:
        ai_report.status = AIReport.Status.FAILED

        ai_report.error_message = "AI report generation failed."

        ai_report.completed_at = timezone.now()

        ai_report.save(
            update_fields=[
                "status",
                "error_message",
                "completed_at",
                "updated_at",
            ]
        )

        raise
