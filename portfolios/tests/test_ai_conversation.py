from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from portfolios.ai.conversation import (
    MAX_CONVERSATION_HISTORY_MESSAGES,
    build_conversation_history,
    continue_ai_conversation,
    start_ai_conversation,
)
from portfolios.models import (
    AIConversation,
    AIMessage,
    Portfolio,
)


class AIConversationTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="conversationuser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Conversation Portfolio",
            currency="EUR",
        )

    @patch("portfolios.ai.conversation.answer_portfolio_question")
    def test_starts_conversation(
        self,
        mock_answer,
    ):
        mock_answer.return_value = "Your portfolio has moderate risk."

        conversation, answer = start_ai_conversation(
            portfolio=self.portfolio,
            question=("How risky is my portfolio?"),
        )

        self.assertEqual(
            conversation.portfolio,
            self.portfolio,
        )

        self.assertEqual(
            answer,
            "Your portfolio has moderate risk.",
        )

        messages = list(conversation.messages.all())

        self.assertEqual(
            len(messages),
            2,
        )

        self.assertEqual(
            messages[0].role,
            AIMessage.Role.USER,
        )

        self.assertEqual(
            messages[0].content,
            "How risky is my portfolio?",
        )

        self.assertEqual(
            messages[1].role,
            AIMessage.Role.ASSISTANT,
        )

        mock_answer.assert_called_once_with(
            question=("How risky is my portfolio?"),
            portfolio=self.portfolio,
            history=[],
        )

    @patch("portfolios.ai.conversation.answer_portfolio_question")
    def test_continues_conversation_with_history(
        self,
        mock_answer,
    ):
        conversation = AIConversation.objects.create(portfolio=self.portfolio)

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.USER,
            content=("How risky is my portfolio?"),
        )

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.ASSISTANT,
            content=("It has moderate risk."),
        )

        mock_answer.return_value = "Diversification is reasonable."

        answer = continue_ai_conversation(
            conversation=conversation,
            question=("And what about diversification?"),
        )

        self.assertEqual(
            answer,
            "Diversification is reasonable.",
        )

        mock_answer.assert_called_once_with(
            question=("And what about diversification?"),
            portfolio=self.portfolio,
            history=[
                {
                    "role": "user",
                    "content": ("How risky is my portfolio?"),
                },
                {
                    "role": "assistant",
                    "content": ("It has moderate risk."),
                },
            ],
        )

        self.assertEqual(
            conversation.messages.count(),
            4,
        )

    def test_history_is_returned_in_order(
        self,
    ):
        conversation = AIConversation.objects.create(portfolio=self.portfolio)

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.USER,
            content="Question 1",
        )

        AIMessage.objects.create(
            conversation=conversation,
            role=AIMessage.Role.ASSISTANT,
            content="Answer 1",
        )

        history = build_conversation_history(conversation)

        self.assertEqual(
            history,
            [
                {
                    "role": "user",
                    "content": "Question 1",
                },
                {
                    "role": "assistant",
                    "content": "Answer 1",
                },
            ],
        )

    def test_history_is_limited(
        self,
    ):
        conversation = AIConversation.objects.create(portfolio=self.portfolio)

        total_messages = MAX_CONVERSATION_HISTORY_MESSAGES + 4

        for index in range(total_messages):
            AIMessage.objects.create(
                conversation=conversation,
                role=AIMessage.Role.USER,
                content=f"Message {index}",
            )

        history = build_conversation_history(conversation)

        self.assertEqual(
            len(history),
            MAX_CONVERSATION_HISTORY_MESSAGES,
        )

        self.assertEqual(
            history[0]["content"],
            "Message 4",
        )

        self.assertEqual(
            history[-1]["content"],
            f"Message {total_messages - 1}",
        )
