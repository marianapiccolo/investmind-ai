from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase


class APIErrorFormatTests(APITestCase):
    def test_unauthenticated_request_has_standard_error_format(
        self,
    ):
        url = reverse(
            "portfolio-list"
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.assertEqual(
            response.data["status_code"],
            401,
        )

        self.assertIn(
            "error",
            response.data,
        )

        self.assertIn(
            "details",
            response.data,
        )