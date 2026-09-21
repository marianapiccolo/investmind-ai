import json

from django.conf import settings

from .openai_client import (
    generate_structured_response,
)
from .portfolio_context import (
    build_ai_portfolio_context,
)


REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {
            "type": "string",
        },
        "performance_analysis": {
            "type": "string",
        },
        "risk_analysis": {
            "type": "string",
        },
        "diversification_analysis": {
            "type": "string",
        },
        "key_observations": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "limitations": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
        "educational_note": {
            "type": "string",
        },
    },
    "required": [
        "executive_summary",
        "performance_analysis",
        "risk_analysis",
        "diversification_analysis",
        "key_observations",
        "limitations",
        "educational_note",
    ],
    "additionalProperties": False,
}


PORTFOLIO_REPORT_INSTRUCTIONS = """
You are the analytical explanation layer of InvestMind AI.

You receive structured financial metrics already calculated
by the application's deterministic Python backend.

Rules:
- Use only information explicitly provided in the input.
- Do not invent financial values, market data, benchmarks,
  holdings, dates, or assumptions.
- Do not recalculate or replace backend financial metrics.
- Clearly distinguish performance, risk, concentration,
  attribution, and diversification.
- If a section is marked unavailable, acknowledge the
  limitation instead of inferring missing information.
- Do not predict future returns or prices.
- Do not tell the user to buy, sell, or hold an investment.
- Do not provide personalized investment recommendations.
- Explain the available historical data in clear,
  professional language.
- Mention relevant limitations of short or incomplete
  historical samples.
- Keep the response concise and useful.
"""


def generate_ai_portfolio_report(
    *,
    portfolio,
):
    context = build_ai_portfolio_context(
        portfolio=portfolio
    )

    report = generate_structured_response(
        instructions=(
            PORTFOLIO_REPORT_INSTRUCTIONS
        ),
        input_text=json.dumps(
            context,
            ensure_ascii=False,
        ),
        schema_name=(
            "investmind_portfolio_report"
        ),
        schema=REPORT_SCHEMA,
    )

    return {
        "portfolio_id": portfolio.id,
        "name": portfolio.name,
        "model": settings.OPENAI_MODEL,
        **report,
    }