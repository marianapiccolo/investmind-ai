from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from portfolios.models import (
    AIConversation,
    AIMessage,
    Portfolio,
)


class WebAIAnalystTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="aiuser",
            password="test-password-123",
        )

        self.other_user = (
            user_model.objects.create_user(
                username="otheraiuser",
                password="test-password-123",
            )
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="AI Portfolio",
            currency="EUR",
        )

        self.second_portfolio = (
            Portfolio.objects.create(
                user=self.user,
                name="Second Portfolio",
                currency="EUR",
            )
        )

        self.other_portfolio = (
            Portfolio.objects.create(
                user=self.other_user,
                name="Private Portfolio",
                currency="EUR",
            )
        )

        self.conversation = (
            AIConversation.objects.create(
                portfolio=self.portfolio
            )
        )

        AIMessage.objects.create(
            conversation=self.conversation,
            role=AIMessage.Role.USER,
            content=(
                "What are my main risks?"
            ),
        )

        AIMessage.objects.create(
            conversation=self.conversation,
            role=AIMessage.Role.ASSISTANT,
            content=(
                "Your portfolio risk analysis."
            ),
        )

        self.second_conversation = (
            AIConversation.objects.create(
                portfolio=self.second_portfolio
            )
        )

        AIMessage.objects.create(
            conversation=(
                self.second_conversation
            ),
            role=AIMessage.Role.USER,
            content=(
                "Second portfolio question"
            ),
        )

        self.other_conversation = (
            AIConversation.objects.create(
                portfolio=self.other_portfolio
            )
        )

        self.client.force_login(
            self.user
        )

    def test_page_lists_only_selected_portfolio_conversations(
        self,
    ):
        response = self.client.get(
            reverse("web:ai-analyst"),
            {
                "portfolio": (
                    self.portfolio.id
                )
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "portfolios/ai_analyst.html",
        )

        self.assertContains(
            response,
            "What are my main risks?",
        )

        self.assertNotContains(
            response,
            "Second portfolio question",
        )

    def test_selected_conversation_displays_messages(
        self,
    ):
        response = self.client.get(
            reverse("web:ai-analyst"),
            {
                "portfolio": (
                    self.portfolio.id
                ),
                "conversation": (
                    self.conversation.id
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "What are my main risks?",
        )

        self.assertContains(
            response,
            "Your portfolio risk analysis.",
        )

    @patch(
        "portfolios.web_views."
        "start_ai_conversation"
    )
    def test_user_can_start_conversation(
        self,
        mock_start,
    ):
        mock_start.return_value = (
            self.conversation,
            "AI answer",
        )

        response = self.client.post(
            (
                reverse("web:ai-analyst")
                + (
                    "?portfolio="
                    f"{self.portfolio.id}"
                )
            ),
            {
                "question": (
                    "How has my portfolio "
                    "performed?"
                ),
            },
        )

        mock_start.assert_called_once_with(
            portfolio=self.portfolio,
            question=(
                "How has my portfolio "
                "performed?"
            ),
        )

        self.assertRedirects(
            response,
            (
                reverse("web:ai-analyst")
                + (
                    "?portfolio="
                    f"{self.portfolio.id}"
                    "&conversation="
                    f"{self.conversation.id}"
                )
            ),
        )

    @patch(
        "portfolios.web_views."
        "continue_ai_conversation"
    )
    def test_user_can_continue_conversation(
        self,
        mock_continue,
    ):
        mock_continue.return_value = (
            "Updated answer"
        )

        response = self.client.post(
            (
                reverse("web:ai-analyst")
                + (
                    "?portfolio="
                    f"{self.portfolio.id}"
                )
            ),
            {
                "conversation": (
                    self.conversation.id
                ),
                "question": (
                    "Can you explain that?"
                ),
            },
        )

        mock_continue.assert_called_once_with(
            conversation=(
                self.conversation
            ),
            question=(
                "Can you explain that?"
            ),
        )

        self.assertRedirects(
            response,
            (
                reverse("web:ai-analyst")
                + (
                    "?portfolio="
                    f"{self.portfolio.id}"
                    "&conversation="
                    f"{self.conversation.id}"
                )
            ),
        )

    def test_conversation_cannot_be_accessed_through_another_portfolio(
        self,
    ):
        response = self.client.get(
            reverse("web:ai-analyst"),
            {
                "portfolio": (
                    self.portfolio.id
                ),
                "conversation": (
                    self.second_conversation.id
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_user_cannot_select_another_users_portfolio(
        self,
    ):
        response = self.client.get(
            reverse("web:ai-analyst"),
            {
                "portfolio": (
                    self.other_portfolio.id
                )
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_anonymous_user_is_redirected(
        self,
    ):
        self.client.logout()

        response = self.client.get(
            reverse("web:ai-analyst")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

def test_assistant_markdown_is_rendered(
    self,
):
    AIMessage.objects.create(
        conversation=self.conversation,
        role=AIMessage.Role.ASSISTANT,
        content=(
            "**Highly concentrated**\n\n"
            "### Main risks\n\n"
            "- Single-company risk\n"
            "- Sector risk"
        ),
    )

    response = self.client.get(
        reverse("web:ai-analyst"),
        {
            "portfolio": (
                self.portfolio.id
            ),
            "conversation": (
                self.conversation.id
            ),
        },
    )

    self.assertContains(
        response,
        "<strong>Highly concentrated</strong>",
        html=True,
    )

    self.assertContains(
        response,
        "<h3>Main risks</h3>",
        html=True,
    )

    self.assertContains(
        response,
        "<li>Single-company risk</li>",
        html=True,
    )

def test_assistant_markdown_strips_unsafe_html(
    self,
):
    AIMessage.objects.create(
        conversation=self.conversation,
        role=AIMessage.Role.ASSISTANT,
        content=(
            "<script>alert('unsafe')</script>"
            "**Safe content**"
        ),
    )

    response = self.client.get(
        reverse("web:ai-analyst"),
        {
            "portfolio": (
                self.portfolio.id
            ),
            "conversation": (
                self.conversation.id
            ),
        },
    )

    self.assertNotContains(
        response,
        "<script>",
    )

    self.assertContains(
        response,
        "<strong>Safe content</strong>",
        html=True,
    )