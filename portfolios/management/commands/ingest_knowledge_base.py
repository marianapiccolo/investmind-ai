from pathlib import Path

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from portfolios.ai.embeddings import (
    EmbeddingProviderError,
    InvalidEmbeddingResponseError,
)
from portfolios.ai.ingestion import (
    ingest_knowledge_base,
)


class Command(BaseCommand):
    help = (
        "Ingest the InvestMind AI financial "
        "knowledge base into PostgreSQL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--directory",
            type=Path,
            default=None,
            help=(
                "Optional directory containing "
                "Markdown knowledge documents."
            ),
        )

    def handle(
        self,
        *args,
        **options,
    ):
        directory = options["directory"]

        try:
            results = ingest_knowledge_base(
                directory=directory
            )

        except (
            FileNotFoundError,
            ValueError,
            EmbeddingProviderError,
            InvalidEmbeddingResponseError,
        ) as exc:
            raise CommandError(
                str(exc)
            ) from exc

        changed_count = 0
        skipped_count = 0

        for document, changed in results:
            if changed:
                changed_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        "Indexed: "
                        f"{document.source_path}"
                    )
                )

            else:
                skipped_count += 1

                self.stdout.write(
                    self.style.WARNING(
                        "Skipped unchanged: "
                        f"{document.source_path}"
                    )
                )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Knowledge-base ingestion "
                "completed."
            )
        )

        self.stdout.write(
            f"Indexed: {changed_count}"
        )

        self.stdout.write(
            f"Skipped: {skipped_count}"
        )

        self.stdout.write(
            f"Total: {len(results)}"
        )