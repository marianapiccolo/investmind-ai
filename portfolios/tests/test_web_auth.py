from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class WebAuthenticationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.user = user_model.objects.create_user(
            username="webuser",
            password="test-password-123",
        )

    def test_dashboard_redirects_anonymous_user_to_login(
        self,
    ):
        response = self.client.get(
            reverse("web:dashboard")
        )

        self.assertRedirects(
            response,
            (
                f"{reverse('login')}"
                f"?next={reverse('web:dashboard')}"
            ),
        )

    def test_authenticated_user_can_access_dashboard(
        self,
    ):
        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse("web:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "portfolios/dashboard.html",
        )

    def test_login_page_is_available(
        self,
    ):
        response = self.client.get(
            reverse("login")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "registration/login.html",
        )

    def test_logout_ends_authenticated_session(
        self,
    ):
        self.client.force_login(
            self.user
        )

        response = self.client.post(
            reverse("logout")
        )

        self.assertRedirects(
            response,
            reverse("login"),
        )

        dashboard_response = self.client.get(
            reverse("web:dashboard")
        )

        self.assertEqual(
            dashboard_response.status_code,
            302,
        )