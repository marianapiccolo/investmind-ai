from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from portfolios.analytics import (
    get_portfolio_composition_analytics,
)
from portfolios.models import Portfolio
from portfolios.portfolio_diversification import (
    get_portfolio_diversification_analytics,
)
from portfolios.portfolio_performance import (
    get_portfolio_performance as calculate_portfolio_performance,
)
from portfolios.portfolio_risk import (
    get_portfolio_risk_analytics,
)


class UnknownPortfolioToolError(ValueError):
    """Raised when an unknown portfolio tool is requested."""


class InvalidPortfolioToolArgumentsError(ValueError):
    """Raised when a portfolio tool receives unsupported arguments."""


@dataclass(frozen=True)
class PortfolioTool:
    name: str
    description: str
    handler: Callable[[Portfolio], dict[str, Any]]


def _to_json_safe(value: Any) -> Any:
    """
    Convert deterministic backend results into JSON-safe values.

    Financial analytics may contain Decimal, date, datetime,
    tuples, lists, or nested dictionaries. Tool results must be
    serializable before they are sent to an LLM provider.
    """
    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(key): _to_json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_to_json_safe(item) for item in value]

    return value


def _performance_tool(
    portfolio: Portfolio,
) -> dict[str, Any]:
    result = calculate_portfolio_performance(portfolio=portfolio)

    return _to_json_safe(result)


def _risk_tool(
    portfolio: Portfolio,
) -> dict[str, Any]:
    result = get_portfolio_risk_analytics(portfolio=portfolio)

    return _to_json_safe(result)


def _composition_tool(
    portfolio: Portfolio,
) -> dict[str, Any]:
    result = get_portfolio_composition_analytics(portfolio=portfolio)

    return _to_json_safe(result)


def _diversification_tool(
    portfolio: Portfolio,
) -> dict[str, Any]:
    result = get_portfolio_diversification_analytics(portfolio=portfolio)

    return _to_json_safe(result)


PORTFOLIO_TOOLS = {
    "get_portfolio_performance": PortfolioTool(
        name="get_portfolio_performance",
        description=(
            "Returns deterministic historical performance metrics for the portfolio."
        ),
        handler=_performance_tool,
    ),
    "get_portfolio_risk": PortfolioTool(
        name="get_portfolio_risk",
        description=(
            "Returns deterministic portfolio risk "
            "metrics such as volatility and drawdown."
        ),
        handler=_risk_tool,
    ),
    "get_portfolio_composition": PortfolioTool(
        name="get_portfolio_composition",
        description=(
            "Returns deterministic portfolio composition and concentration analytics."
        ),
        handler=_composition_tool,
    ),
    "get_portfolio_diversification": PortfolioTool(
        name="get_portfolio_diversification",
        description=(
            "Returns deterministic diversification and correlation analytics."
        ),
        handler=_diversification_tool,
    ),
}


def get_portfolio_tool_specs() -> list[dict[str, Any]]:
    """
    Return provider-independent tool descriptions.

    The LLM receives no portfolio identifier. Portfolio ownership
    is resolved by the Django application before tool execution.
    """
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        }
        for tool in PORTFOLIO_TOOLS.values()
    ]


def execute_portfolio_tool(
    *,
    tool_name: str,
    portfolio: Portfolio,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute one approved read-only portfolio tool.

    The portfolio is supplied by trusted application code rather
    than by the language model.
    """
    tool = PORTFOLIO_TOOLS.get(tool_name)

    if tool is None:
        raise UnknownPortfolioToolError(f"Unknown portfolio tool: {tool_name}")

    if arguments:
        raise InvalidPortfolioToolArgumentsError(
            f"Tool '{tool_name}' does not accept arguments."
        )

    return tool.handler(portfolio)
