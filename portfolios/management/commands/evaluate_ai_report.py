import json

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from portfolios.ai.evals import (
    evaluate_ai_portfolio_report,
)
from portfolios.ai.portfolio_context import (
    build_ai_portfolio_context,
)
from portfolios.ai.portfolio_report import (
    generate_ai_portfolio_report,
)
from portfolios.models import Portfolio


class Command(BaseCommand):
    help = (
        "Generate and evaluate an AI portfolio "
        "report for a portfolio."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "portfolio_id",
            type=int,
        )

    def handle(
        self,
        *args,
        **options,
    ):
        portfolio_id = options[
            "portfolio_id"
        ]

        try:
            portfolio = Portfolio.objects.get(
                id=portfolio_id
            )

        except Portfolio.DoesNotExist as exc:
            raise CommandError(
                "Portfolio not found."
            ) from exc

        context = build_ai_portfolio_context(
            portfolio=portfolio
        )

        report = generate_ai_portfolio_report(
            portfolio=portfolio,
            context=context,
        )

        evaluation = (
            evaluate_ai_portfolio_report(
                context=context,
                report=report,
            )
        )

        self.stdout.write(
            json.dumps(
                {
                    "report": report,
                    "evaluation": evaluation,
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

        if evaluation["passed"]:
            self.stdout.write(
                self.style.SUCCESS(
                    "AI evaluation passed."
                )
            )

        else:
            self.stdout.write(
                self.style.ERROR(
                    "AI evaluation failed."
                )
            )