from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from portfolios.models import Portfolio


class WebPortfolioSelectionTests(TestCase):
    session_key = "selected_portfolio_id"

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="selection-owner")
        self.other_user = user_model.objects.create_user(username="selection-other")
        self.older = Portfolio.objects.create(user=self.user, name="Older Portfolio")
        self.newer = Portfolio.objects.create(user=self.user, name="Newer Portfolio")
        self.private = Portfolio.objects.create(
            user=self.other_user, name="Private Portfolio"
        )
        self.client.force_login(self.user)

    def remember(self, portfolio_id):
        session = self.client.session
        session[self.session_key] = portfolio_id
        session.save()

    def select(self, portfolio):
        return self.client.get(
            reverse("web:portfolio"), {"portfolio": portfolio.pk}
        )

    def test_first_visit_defaults_to_latest_owned_portfolio(self):
        response = self.client.get(reverse("web:portfolio"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_portfolio"], self.newer)
        self.assertEqual(self.client.session[self.session_key], self.newer.pk)

    def test_selection_is_remembered_when_navigating_between_pages(self):
        self.assertEqual(self.select(self.older).status_code, 200)

        for name in ["transactions", "portfolio"]:
            with self.subTest(page=name):
                response = self.client.get(reverse(f"web:{name}"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["selected_portfolio"], self.older)

    def test_explicit_selection_replaces_remembered_selection(self):
        self.remember(self.older.pk)

        response = self.select(self.newer)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_portfolio"], self.newer)
        self.assertEqual(self.client.session[self.session_key], self.newer.pk)

    def test_explicit_selection_cannot_access_another_users_portfolio(self):
        self.remember(self.older.pk)

        response = self.select(self.private)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.session[self.session_key], self.older.pk)

    def test_remembered_selection_is_checked_against_current_user(self):
        self.remember(self.private.pk)

        response = self.client.get(reverse("web:portfolio"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_portfolio"], self.newer)
        self.assertEqual(self.client.session[self.session_key], self.newer.pk)

    def test_deleted_selection_falls_back_to_latest_owned_portfolio(self):
        self.remember(self.older.pk)
        self.older.delete()

        response = self.client.get(reverse("web:portfolio"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_portfolio"], self.newer)
        self.assertEqual(self.client.session[self.session_key], self.newer.pk)

    def test_no_owned_portfolios_clears_remembered_selection(self):
        self.remember(self.older.pk)
        Portfolio.objects.filter(user=self.user).delete()

        response = self.client.get(reverse("web:portfolio"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["selected_portfolio"])
        self.assertNotIn(self.session_key, self.client.session)
        self.assertTrue(Portfolio.objects.filter(pk=self.private.pk).exists())

    def test_invalid_explicit_selection_does_not_change_session(self):
        self.remember(self.older.pk)

        response = self.client.get(
            reverse("web:portfolio"), {"portfolio": "not-an-id"}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.session[self.session_key], self.older.pk)
