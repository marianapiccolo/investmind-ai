from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.ai.openai_client import (
    AIProviderError,
)
from portfolios.ai.tool_calling import (
    InvalidAIToolResponseError,
)
from portfolios.models import (
    AIConversation,
    AIMessage,
    Portfolio,
)


class AIConversationAPITests(APITestCase):
    def setUp(self):
        cache.clear()

        User = get_user_model()

        self.user = User.objects.create_user(
            username="conversationapiuser",
            password="test123",
        )

        self.other_user = User.objects.create_user(
            username="otherconversationuser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Conversation Portfolio",
            currency="EUR",
        )

        self.other_portfolio = Portfolio.objects.create(
            user=self.other_user,
            name="Other Portfolio",
            currency="EUR",
        )

        self.client.force_authenticate(user=self.user)

    @patch("portfolios.ai.conversation.answer_portfolio_question")
    def test_starts_conversation(
        self,
        mock_answer,
    ):
        mock_answer.return_value = "Your portfolio has moderate risk."

        url = reverse(
            "portfolio-ai-conversations",
            args=[self.portfolio.id],
        )

        response = self.client.post(
            url,
            {"question": ("How risky is my portfolio?")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["portfolio_id"],
            self.portfolio.id,
        )

        self.assertEqual(
            len(response.data["messages"]),
            2,
        )

        self.assertEqual(
            response.data["messages"][0]["role"],
            AIMessage.Role.USER,
        )

        self.assertEqual(
            response.data["messages"][1]["role"],
            AIMessage.Role.ASSISTANT,
        )

        self.assertEqual(
            AIConversation.objects.count(),
            1,
        )

        mock_answer.assert_called_once_with(
            question=("How risky is my portfolio?"),
            portfolio=self.portfolio,
            history=[],
        )

    @patch("portfolios.ai.conversation.answer_portfolio_question")
    def test_cannot_start_conversation_for_other_user(
        self,
        mock_answer,
    ):
        url = reverse(
            "portfolio-ai-conversations",
            args=[self.other_portfolio.id],
        )

        response = self.client.post(
            url,
            {"question": ("Analyze this portfolio.")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        mock_answer.assert_not_called()

    @patch("portfolios.ai.conversation.answer_portfolio_question")
    def test_start_requires_authentication(
        self,
        mock_answer,
    ):
        self.client.force_authenticate(user=None)

        url = reverse(
            "portfolio-ai-conversations",
            args=[self.portfolio.id],
        )

        response = self.client.post(
            url,
            {"question": ("Analyze my portfolio.")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        mock_answer.assert_not_called()

    @patch("portfolios.ai.conversation.answer_portfolio_question")
    def test_blank_question_is_rejected(
        self,
        mock_answer,
    ):
        url = reverse(
            "portfolio-ai-conversations",
            args=[self.portfolio.id],
        )

        response = self.client.post(
            url,
            {
                "question": "   ",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        mock_answer.assert_not_called()

    def test_lists_only_own_conversations(self):
        own_conversation = AIConversation.objects.create(portfolio=self.portfolio)

        AIConversation.objects.create(portfolio=self.other_portfolio)

        url = reverse("ai-conversation-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        if isinstance(
            response.data,
            dict,
        ):
            items = response.data.get(
                "results",
                [],
            )
        else:
            items = response.data

        ids = {item["id"] for item in items}

        self.assertEqual(
            ids,
            {
                own_conversation.id,
            },
        )

    def test_retrieves_conversation_history(
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

        url = reverse(
            "ai-conversation-detail",
            args=[conversation.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["messages"]),
            2,
        )

        self.assertEqual(
            response.data["messages"][0]["content"],
            "Question 1",
        )

        self.assertEqual(
            response.data["messages"][1]["content"],
            "Answer 1",
        )

    def test_cannot_retrieve_other_users_conversation(
        self,
    ):
        conversation = AIConversation.objects.create(portfolio=self.other_portfolio)

        url = reverse(
            "ai-conversation-detail",
            args=[conversation.id],
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    @patch("portfolios.ai.conversation.answer_portfolio_question")
    def test_continues_conversation(
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

        url = reverse(
            "ai-conversation-messages",
            args=[conversation.id],
        )

        response = self.client.post(
            url,
            {"question": ("And what about diversification?")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["messages"]),
            4,
        )

        self.assertEqual(
            response.data["messages"][-2]["content"],
            ("And what about diversification?"),
        )

        self.assertEqual(
            response.data["messages"][-1]["content"],
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

    @patch("portfolios.ai.conversation.answer_portfolio_question")
    def test_provider_failure_does_not_create_conversation(
        self,
        mock_answer,
    ):
        mock_answer.side_effect = AIProviderError("Provider unavailable.")

        url = reverse(
            "portfolio-ai-conversations",
            args=[self.portfolio.id],
        )

        response = self.client.post(
            url,
            {"question": ("Analyze my portfolio.")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )

        self.assertEqual(
            AIConversation.objects.count(),
            0,
        )

    @patch("portfolios.ai.conversation.answer_portfolio_question")
    def test_invalid_ai_response_returns_502(
        self,
        mock_answer,
    ):
        mock_answer.side_effect = InvalidAIToolResponseError("Invalid AI response.")

        url = reverse(
            "portfolio-ai-conversations",
            args=[self.portfolio.id],
        )

        response = self.client.post(
            url,
            {"question": ("Analyze my portfolio.")},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_502_BAD_GATEWAY,
        )

        self.assertEqual(
            AIConversation.objects.count(),
            0,
        )
