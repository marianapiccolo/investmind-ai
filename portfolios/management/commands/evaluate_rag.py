from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from portfolios.ai.embeddings import (
    EmbeddingProviderError,
    InvalidEmbeddingResponseError,
)
from portfolios.ai.rag_evals import (
    run_rag_evals,
    summarize_rag_evals,
)


class Command(BaseCommand):
    help = (
        "Evaluate InvestMind RAG retrieval "
        "quality using curated test cases."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--top-k",
            type=int,
            default=3,
            help=(
                "Number of retrieved chunks "
                "evaluated per query."
            ),
        )

    def handle(
        self,
        *args,
        **options,
    ):
        top_k = options["top_k"]

        try:
            results = run_rag_evals(
                top_k=top_k
            )

        except (
            ValueError,
            EmbeddingProviderError,
            InvalidEmbeddingResponseError,
        ) as exc:
            raise CommandError(
                str(exc)
            ) from exc

        for result in results:
            if result.hit:
                status = self.style.SUCCESS(
                    "PASS"
                )

                rank = str(result.rank)

            else:
                status = self.style.ERROR(
                    "MISS"
                )

                rank = "-"

            self.stdout.write(
                f"[{status}] "
                f"{result.name} "
                f"(rank={rank})"
            )

            for position, match in enumerate(
                result.retrieved_matches,
                start=1,
            ):
                source_path, section = match

                self.stdout.write(
                    f"  {position}. "
                    f"{source_path} / "
                    f"{section}"
                )

        summary = summarize_rag_evals(
            results
        )

        self.stdout.write("")

        self.stdout.write(
            "RAG evaluation summary"
        )

        self.stdout.write(
            f"Cases: {summary.total_cases}"
        )

        self.stdout.write(
            f"Hits: {summary.hits}"
        )

        self.stdout.write(
            "Hit rate: "
            f"{summary.hit_rate:.2%}"
        )

        self.stdout.write(
            "MRR: "
            f"{summary.mean_reciprocal_rank:.4f}"
        )