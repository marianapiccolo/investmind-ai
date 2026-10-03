from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from portfolios.models import Portfolio


class WebPortfolioTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="portfoliouser",
            password="test-password-123",
        )

        self.other_user = (
            user_model.objects.create_user(
                username="otherportfoliouser",
                password="test-password-123",
            )
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Main Portfolio",
            currency="EUR",
        )

        self.other_portfolio = (
            Portfolio.objects.create(
                user=self.other_user,
                name="Private Portfolio",
                currency="EUR",
            )
        )

        self.client.force_login(
            self.user
        )

    def test_portfolio_page_lists_only_owned_portfolios(
        self,
    ):
        response = self.client.get(
            reverse("web:portfolio")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "portfolios/portfolio.html",
        )

        self.assertContains(
            response,
            "Main Portfolio",
        )

        self.assertNotContains(
            response,
            "Private Portfolio",
        )

    def test_user_can_create_portfolio(
        self,
    ):
        response = self.client.post(
            reverse("web:portfolio"),
            {
                "name": "Growth Portfolio",
                "currency": "usd",
            },
        )

        created_portfolio = (
            Portfolio.objects.get(
                name="Growth Portfolio"
            )
        )

        self.assertEqual(
            created_portfolio.user,
            self.user,
        )

        self.assertEqual(
            created_portfolio.currency,
            "USD",
        )

        self.assertRedirects(
            response,
            (
                reverse("web:portfolio")
                + (
                    "?portfolio="
                    f"{created_portfolio.id}"
                )
            ),
        )

    def test_invalid_currency_does_not_create_portfolio(
        self,
    ):
        response = self.client.post(
            reverse("web:portfolio"),
            {
                "name": "Invalid Portfolio",
                "currency": "EURO",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertFalse(
            Portfolio.objects.filter(
                name="Invalid Portfolio"
            ).exists()
        )

        self.assertContains(
            response,
            "Enter a valid 3-letter currency code.",
        )

    def test_user_cannot_select_another_users_portfolio(
        self,
    ):
        response = self.client.get(
            reverse("web:portfolio"),
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
            reverse("web:portfolio")
        )

        self.assertEqual(
            response.status_code,
            302,
        )