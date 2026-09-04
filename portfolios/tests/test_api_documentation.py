from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase


class APIDocumentationTests(APITestCase):
    def test_openapi_schema_is_available(self):
        url = reverse("schema")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_swagger_ui_is_available(self):
        url = reverse("swagger-ui")

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )