from dataclasses import dataclass
from typing import Callable

from .retrieval import (
    MAX_TOP_K,
    KnowledgeSearchResult,
    search_financial_knowledge,
)


@dataclass(frozen=True)
class RAGEvalCase:
    name: str
    query: str
    expected_matches: tuple[
        tuple[str, str],
        ...,
    ]


@dataclass(frozen=True)
class RAGEvalResult:
    name: str
    query: str
    hit: bool
    rank: int | None
    reciprocal_rank: float
    retrieved_matches: tuple[
        tuple[str, str],
        ...,
    ]


@dataclass(frozen=True)
class RAGEvalSummary:
    total_cases: int
    hits: int
    hit_rate: float
    mean_reciprocal_rank: float


DEFAULT_RAG_EVAL_CASES = (
    RAGEvalCase(
        name="same_return_different_risk",
        query=(
            "Why can two portfolios with the "
            "same return have different levels "
            "of risk?"
        ),
        expected_matches=(
            (
                "returns.md",
                "Return Interpretation",
            ),
        ),
    ),
    RAGEvalCase(
        name="correlation_during_crisis",
        query=(
            "Can assets that normally move "
            "differently become more correlated "
            "during a market crisis?"
        ),
        expected_matches=(
            (
                "diversification.md",
                "Correlation",
            ),
        ),
    ),
    RAGEvalCase(
        name="irregular_cash_flows",
        query=(
            "Which return measure should I use "
            "when deposits happen on irregular "
            "dates?"
        ),
        expected_matches=(
            (
                "portfolio_performance.md",
                "XIRR",
            ),
        ),
    ),
    RAGEvalCase(
        name="peak_to_trough_loss",
        query=(
            "Which metric describes the largest "
            "decline from a portfolio peak to "
            "a later low point?"
        ),
        expected_matches=(
            (
                "portfolio_risk.md",
                "Maximum Drawdown",
            ),
        ),
    ),
    RAGEvalCase(
        name="historical_period_limitation",
        query=(
            "Can changing the period used in an "
            "analysis change the portfolio risk "
            "and performance metrics?"
        ),
        expected_matches=(
            (
                "investment_limitations.md",
                "Historical Data Limitations",
            ),
        ),
    ),
    RAGEvalCase(
        name="benchmark_suitability",
        query=(
            "Why might a benchmark be misleading "
            "for a portfolio with very different "
            "asset classes?"
        ),
        expected_matches=(
            (
                "investment_limitations.md",
                "Benchmark Limitations",
            ),
        ),
    ),
    RAGEvalCase(
        name="compounding_returns",
        query=(
            "Why does gaining ten percent and then "
            "losing ten percent not bring an "
            "investment exactly back to its "
            "starting value?"
        ),
        expected_matches=(
            (
                "returns.md",
                "Compounding",
            ),
        ),
    ),
)


def evaluate_rag_case(
    *,
    case: RAGEvalCase,
    top_k: int = 3,
    search_fn: Callable[
        ...,
        list[KnowledgeSearchResult],
    ] = search_financial_knowledge,
) -> RAGEvalResult:
    """
    Evaluate whether the expected knowledge
    appears within the retrieved top-k results.
    """
    if top_k <= 0:
        raise ValueError(
            "top_k must be greater than zero."
        )

    if top_k > MAX_TOP_K:
        raise ValueError(
            f"top_k must not exceed {MAX_TOP_K}."
        )

    results = search_fn(
        query=case.query,
        top_k=top_k,
    )

    retrieved_matches = tuple(
        (
            result.source_path,
            result.section_title,
        )
        for result in results
    )

    rank = None

    for position, result in enumerate(
        results,
        start=1,
    ):
        match = (
            result.source_path,
            result.section_title,
        )

        if match in case.expected_matches:
            rank = position
            break

    reciprocal_rank = (
        1.0 / rank
        if rank is not None
        else 0.0
    )

    return RAGEvalResult(
        name=case.name,
        query=case.query,
        hit=rank is not None,
        rank=rank,
        reciprocal_rank=reciprocal_rank,
        retrieved_matches=retrieved_matches,
    )


def run_rag_evals(
    *,
    cases: tuple[
        RAGEvalCase,
        ...,
    ] = DEFAULT_RAG_EVAL_CASES,
    top_k: int = 3,
    search_fn: Callable[
        ...,
        list[KnowledgeSearchResult],
    ] = search_financial_knowledge,
) -> list[RAGEvalResult]:
    """
    Run all configured retrieval evaluation cases.
    """
    return [
        evaluate_rag_case(
            case=case,
            top_k=top_k,
            search_fn=search_fn,
        )
        for case in cases
    ]


def summarize_rag_evals(
    results: list[RAGEvalResult],
) -> RAGEvalSummary:
    """
    Calculate Hit@K and Mean Reciprocal Rank.
    """
    if not results:
        raise ValueError(
            "At least one RAG eval result "
            "is required."
        )

    hits = sum(
        result.hit
        for result in results
    )

    hit_rate = (
        hits / len(results)
    )

    mean_reciprocal_rank = (
        sum(
            result.reciprocal_rank
            for result in results
        )
        / len(results)
    )

    return RAGEvalSummary(
        total_cases=len(results),
        hits=hits,
        hit_rate=hit_rate,
        mean_reciprocal_rank=(
            mean_reciprocal_rank
        ),
    )