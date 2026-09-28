from django.test import SimpleTestCase

from portfolios.ai.rag_evals import (
    RAGEvalCase,
    evaluate_rag_case,
    summarize_rag_evals,
)
from portfolios.ai.retrieval import (
    KnowledgeSearchResult,
)

class RAGEvalTests(SimpleTestCase):
    def _result(
        self,
        *,
        source_path: str,
        section_title: str,
    ) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            chunk_id=1,
            document_id=1,
            document_title="Document",
            source_path=source_path,
            section_title=section_title,
            content="Knowledge content.",
            distance=0.2,
            similarity=0.8,
        )

    def test_eval_passes_when_expected_chunk_is_first(
        self,
    ):
        case = RAGEvalCase(
            name="drawdown",
            query="Explain drawdown.",
            expected_matches=(
                (
                    "portfolio_risk.md",
                    "Maximum Drawdown",
                ),
            ),
        )

        def search_fn(**kwargs):
            return [
                self._result(
                    source_path=(
                        "portfolio_risk.md"
                    ),
                    section_title=(
                        "Maximum Drawdown"
                    ),
                )
            ]

        result = evaluate_rag_case(
            case=case,
            search_fn=search_fn,
        )

        self.assertTrue(result.hit)
        self.assertEqual(result.rank, 1)
        self.assertEqual(
            result.reciprocal_rank,
            1.0,
        )

    def test_eval_tracks_lower_rank(
        self,
    ):
        case = RAGEvalCase(
            name="xirr",
            query="Irregular deposits.",
            expected_matches=(
                (
                    "portfolio_performance.md",
                    "XIRR",
                ),
            ),
        )

        def search_fn(**kwargs):
            return [
                self._result(
                    source_path="returns.md",
                    section_title=(
                        "Investment Returns"
                    ),
                ),
                self._result(
                    source_path=(
                        "portfolio_performance.md"
                    ),
                    section_title="XIRR",
                ),
            ]

        result = evaluate_rag_case(
            case=case,
            search_fn=search_fn,
        )

        self.assertTrue(result.hit)
        self.assertEqual(result.rank, 2)
        self.assertEqual(
            result.reciprocal_rank,
            0.5,
        )

    def test_eval_reports_miss(
        self,
    ):
        case = RAGEvalCase(
            name="correlation",
            query="Correlation.",
            expected_matches=(
                (
                    "diversification.md",
                    "Correlation",
                ),
            ),
        )

        def search_fn(**kwargs):
            return [
                self._result(
                    source_path=(
                        "portfolio_risk.md"
                    ),
                    section_title="Volatility",
                )
            ]

        result = evaluate_rag_case(
            case=case,
            search_fn=search_fn,
        )

        self.assertFalse(result.hit)
        self.assertIsNone(result.rank)
        self.assertEqual(
            result.reciprocal_rank,
            0.0,
        )

    def test_summary_calculates_metrics(
        self,
    ):
        first_case = RAGEvalCase(
            name="first",
            query="First.",
            expected_matches=(
                ("a.md", "A"),
            ),
        )

        second_case = RAGEvalCase(
            name="second",
            query="Second.",
            expected_matches=(
                ("b.md", "B"),
            ),
        )

        first_result = evaluate_rag_case(
            case=first_case,
            search_fn=lambda **kwargs: [
                self._result(
                    source_path="a.md",
                    section_title="A",
                )
            ],
        )

        second_result = evaluate_rag_case(
            case=second_case,
            search_fn=lambda **kwargs: [
                self._result(
                    source_path="x.md",
                    section_title="X",
                )
            ],
        )

        summary = summarize_rag_evals(
            [
                first_result,
                second_result,
            ]
        )

        self.assertEqual(
            summary.total_cases,
            2,
        )

        self.assertEqual(
            summary.hits,
            1,
        )

        self.assertEqual(
            summary.hit_rate,
            0.5,
        )

        self.assertEqual(
            summary.mean_reciprocal_rank,
            0.5,
        )