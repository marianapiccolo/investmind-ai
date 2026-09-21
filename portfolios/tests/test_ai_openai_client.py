import json
from unittest.mock import Mock, patch

from django.test import (
    SimpleTestCase,
    override_settings,
)

from portfolios.ai.openai_client import (
    generate_structured_response,
)


@override_settings(
    OPENAI_API_KEY="fake-key",
    OPENAI_MODEL="test-model",
    OPENAI_TIMEOUT_SECONDS=30,
    OPENAI_MAX_OUTPUT_TOKENS=500,
)
class OpenAIClientTests(
    SimpleTestCase
):
    @patch(
        "portfolios.ai.openai_client.OpenAI"
    )
    def test_generates_structured_response(
        self,
        mock_openai,
    ):
        mock_client = Mock()

        mock_openai.return_value = (
            mock_client
        )

        mock_response = Mock()

        mock_response.output_text = (
            json.dumps(
                {
                    "summary": "Test summary"
                }
            )
        )

        mock_client.responses.create.return_value = (
            mock_response
        )

        schema = {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                }
            },
            "required": [
                "summary"
            ],
            "additionalProperties": False,
        }

        result = generate_structured_response(
            instructions="Test instructions",
            input_text="Test input",
            schema_name="test_schema",
            schema=schema,
        )

        self.assertEqual(
            result,
            {
                "summary": "Test summary"
            },
        )

        mock_client.responses.create.assert_called_once()

        call_kwargs = (
            mock_client
            .responses
            .create
            .call_args
            .kwargs
        )

        self.assertEqual(
            call_kwargs["model"],
            "test-model",
        )

        self.assertFalse(
            call_kwargs["store"]
        )

        self.assertTrue(
            call_kwargs[
                "text"
            ][
                "format"
            ][
                "strict"
            ]
        )