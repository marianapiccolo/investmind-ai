from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from portfolios.models import Portfolio


class PortfolioAPITests(APITestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

        self.other_user = User.objects.create_user(
            username="otheruser",
            password="test123",
        )

        self.portfolio = Portfolio.objects.create(
            user=self.user,
            name="Long-Term Portfolio",
            currency="EUR",
        )

        Portfolio.objects.create(
            user=self.other_user,
            name="Other User Portfolio",
            currency="USD",
        )

        self.client.force_authenticate(user=self.user)

    def test_list_returns_only_authenticated_user_portfolios(self):
        url = reverse("portfolio-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["name"],
            "Long-Term Portfolio",
        )

    def test_create_portfolio_assigns_authenticated_user(self):
        url = reverse("portfolio-list")

        data = {
            "name": "Retirement Portfolio",
            "currency": "EUR",
        }

        response = self.client.post(
            url,
            data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        portfolio = Portfolio.objects.get(
            name="Retirement Portfolio"
        )

        self.assertEqual(portfolio.user, self.user)