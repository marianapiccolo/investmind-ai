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
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric_path": {
                        "type": "string",
                    },
                    "value": {
                        "type": "string",
                    },
                },
                "required": [
                    "metric_path",
                    "value",
                ],
                "additionalProperties": False,
            },
        },
        "unavailable_sections": {
            "type": "array",
            "items": {
                "type": "string",
            },
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
        "evidence",
        "unavailable_sections",
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
- Any numerical financial value mentioned in the report
  must come directly from the provided context.
- Clearly distinguish performance, risk, concentration,
  attribution, and diversification.
- If a section is marked unavailable, acknowledge the
  limitation instead of inferring missing information.
- A null metric is unavailable even if its section is available.
- Explain any supplied annualization_unavailable_reason. Do not estimate
  missing annualized metrics from period returns or other values.
- Do not predict future returns or prices.
- Do not tell the user to buy, sell, or hold an investment.
- Do not provide personalized investment recommendations.
- Explain the available historical data in clear,
  professional language.
- Mention relevant limitations of short or incomplete
  historical samples.
- Keep the response concise and useful.

Evidence rules:
- For metrics used in the analysis, include evidence items.
- metric_path must be the exact dot-separated path from
  the supplied context.
- Every evidence item must reference a scalar value only.
- Never reference an entire object or array as evidence.
- When referencing a value inside an array, include the
  zero-based array index in metric_path.
- For example:
  sections.composition.data.top_holdings.0.ticker
  is valid, while
  sections.composition.data.top_holdings
  is not valid evidence.
- value must exactly match the scalar value supplied at
  that path.
- Do not serialize objects or arrays into the value field.
- Do not create evidence for unavailable data.
- unavailable_sections must contain the exact section names
  whose available field is false.
"""

def generate_ai_portfolio_report(
    *,
    portfolio,
    context=None,
):
    if context is None:
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