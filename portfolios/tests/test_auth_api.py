from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase


class JWTAuthenticationTests(APITestCase):
    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="test123",
        )

    def test_obtain_token_pair(self):
        url = reverse("token_obtain_pair")

        response = self.client.post(
            url,
            {
                "username": "testuser",
                "password": "test123",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_invalid_credentials_are_rejected(self):
        url = reverse("token_obtain_pair")

        response = self.client.post(
            url,
            {
                "username": "testuser",
                "password": "wrong-password",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_access_protected_endpoint_with_jwt(self):
        token_url = reverse("token_obtain_pair")

        token_response = self.client.post(
            token_url,
            {
                "username": "testuser",
                "password": "test123",
            },
            format="json",
        )

        access_token = token_response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        url = reverse("portfolio-list")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_refresh_token_returns_new_access_token(self):
        token_url = reverse("token_obtain_pair")

        token_response = self.client.post(
            token_url,
            {
                "username": "testuser",
                "password": "test123",
            },
            format="json",
        )

        refresh_token = token_response.data["refresh"]

        refresh_url = reverse("token_refresh")

        response = self.client.post(
            refresh_url,
            {
                "refresh": refresh_token,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("access", response.data)