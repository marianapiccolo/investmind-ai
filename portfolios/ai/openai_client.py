import json
import logging

from django.conf import settings
from openai import APIError, OpenAI

logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    PUBLIC_MESSAGES = {
        "provider_unavailable": "AI provider is unavailable.",
        "not_configured": "AI provider is not configured.",
        "output_limit": (
            "The AI response reached the configured output limit. "
            "Please ask the administrator to review the limit."
        ),
        "incomplete_response": "The AI provider returned an incomplete response. Please try again.",
        "empty_response": "The AI provider returned an empty response. Please try again.",
        "invalid_response": "The AI provider returned an invalid response. Please try again.",
    }

    def __init__(self, message="AI provider is unavailable.", *, code="provider_unavailable"):
        super().__init__(message)
        self.code = code if code in self.PUBLIC_MESSAGES else "provider_unavailable"
        self.public_message = self.PUBLIC_MESSAGES[self.code]


def generate_structured_response(
    *,
    instructions,
    input_text,
    schema_name,
    schema,
):
    if not settings.OPENAI_API_KEY:
        raise AIProviderError(
            "OpenAI API key is not configured.",
            code="not_configured",
        )

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
    )

    try:
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions=instructions,
            input=input_text,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
            max_output_tokens=(
                settings.OPENAI_MAX_OUTPUT_TOKENS
            ),
            store=False,
        )

    except APIError as exc:
        logger.exception(
            "OpenAI API request failed."
        )

        raise AIProviderError(
            "AI provider is temporarily unavailable."
        ) from exc
    
    if response.status == "incomplete":
        incomplete_reason = None

        if response.incomplete_details:
            incomplete_reason = (
                response.incomplete_details.reason
            )

        logger.warning(
            (
                "OpenAI response was incomplete. "
                "reason=%s"
            ),
            incomplete_reason,
        )

        raise AIProviderError(
            "AI provider returned an incomplete response.",
            code=(
                "output_limit"
                if incomplete_reason == "max_output_tokens"
                else "incomplete_response"
            ),
        )    

    if not response.output_text:
        raise AIProviderError(
            "AI provider returned an empty response.",
            code="empty_response",
        )

    try:
        return json.loads(
            response.output_text
        )

    except json.JSONDecodeError as exc:
        logger.exception(
            "OpenAI returned invalid structured output."
        )

        raise AIProviderError(
            "AI provider returned an invalid response.",
            code="invalid_response",
        ) from exc