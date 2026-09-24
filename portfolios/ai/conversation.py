from django.db import transaction
from django.utils import timezone

from portfolios.models import (
    AIConversation,
    AIMessage,
    Portfolio,
)

from .tool_calling import (
    answer_portfolio_question,
)

MAX_CONVERSATION_HISTORY_MESSAGES = 12


def build_conversation_history(
    conversation: AIConversation,
) -> list[dict[str, str]]:
    """
    Build a compact conversation history for the LLM.

    Only user and assistant natural-language messages are
    persisted between turns. Tool calls are executed again
    when current portfolio data is required.
    """
    messages = list(
        conversation.messages.order_by(
            "-created_at",
            "-id",
        )[:MAX_CONVERSATION_HISTORY_MESSAGES]
    )

    messages.reverse()

    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in messages
    ]


def _persist_exchange(
    *,
    conversation: AIConversation,
    question: str,
    answer: str,
) -> None:
    with transaction.atomic():
        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.USER,
            content=question,
        )

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.ASSISTANT,
            content=answer,
        )

        AIConversation.objects.filter(pk=conversation.pk).update(
            updated_at=timezone.now()
        )

        conversation.refresh_from_db(fields=["updated_at"])


def start_ai_conversation(
    *,
    portfolio: Portfolio,
    question: str,
) -> tuple[AIConversation, str]:
    """
    Start a new portfolio conversation.

    The conversation is persisted only after the AI turn
    completes successfully, avoiding empty conversations
    when the provider fails.
    """
    question = question.strip()

    answer = answer_portfolio_question(
        question=question,
        portfolio=portfolio,
        history=[],
    )

    with transaction.atomic():
        conversation = AIConversation.objects.create(portfolio=portfolio)

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.USER,
            content=question,
        )

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.ASSISTANT,
            content=answer,
        )

    return conversation, answer


def continue_ai_conversation(
    *,
    conversation: AIConversation,
    question: str,
) -> str:
    """
    Continue an existing portfolio conversation.
    """
    question = question.strip()

    history = build_conversation_history(conversation)

    answer = answer_portfolio_question(
        question=question,
        portfolio=conversation.portfolio,
        history=history,
    )

    _persist_exchange(
        conversation=conversation,
        question=question,
        answer=answer,
    )

    return answer
