from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import (
    SimpleTestCase,
    override_settings,
)

from portfolios.ai.embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProviderError,
    InvalidEmbeddingResponseError,
    generate_embedding,
    generate_embeddings,
)


@override_settings(OPENAI_EMBEDDING_MODEL=("text-embedding-3-small"))
class EmbeddingServiceTests(SimpleTestCase):
    def setUp(self):
        self.client = Mock()

    def test_generates_single_embedding(
        self,
    ):
        embedding = [0.1] * EMBEDDING_DIMENSIONS

        self.client.embeddings.create.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(
                    index=0,
                    embedding=embedding,
                )
            ]
        )

        result = generate_embedding(
            text="Maximum drawdown.",
            client=self.client,
        )

        self.assertEqual(
            len(result),
            EMBEDDING_DIMENSIONS,
        )

        self.client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input=["Maximum drawdown."],
            dimensions=EMBEDDING_DIMENSIONS,
            encoding_format="float",
        )

    def test_generates_multiple_embeddings(
        self,
    ):
        first_embedding = [0.1] * EMBEDDING_DIMENSIONS

        second_embedding = [0.2] * EMBEDDING_DIMENSIONS

        self.client.embeddings.create.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(
                    index=0,
                    embedding=first_embedding,
                ),
                SimpleNamespace(
                    index=1,
                    embedding=second_embedding,
                ),
            ]
        )

        result = generate_embeddings(
            texts=[
                "Volatility.",
                "Diversification.",
            ],
            client=self.client,
        )

        self.assertEqual(
            len(result),
            2,
        )

        self.assertEqual(
            result[0][0],
            0.1,
        )

        self.assertEqual(
            result[1][0],
            0.2,
        )

    def test_embeddings_are_ordered_by_index(
        self,
    ):
        first_embedding = [0.1] * EMBEDDING_DIMENSIONS

        second_embedding = [0.2] * EMBEDDING_DIMENSIONS

        self.client.embeddings.create.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(
                    index=1,
                    embedding=second_embedding,
                ),
                SimpleNamespace(
                    index=0,
                    embedding=first_embedding,
                ),
            ]
        )

        result = generate_embeddings(
            texts=[
                "First text.",
                "Second text.",
            ],
            client=self.client,
        )

        self.assertEqual(
            result[0][0],
            0.1,
        )

        self.assertEqual(
            result[1][0],
            0.2,
        )

    def test_empty_batch_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_embeddings(
                texts=[],
                client=self.client,
            )

        self.client.embeddings.create.assert_not_called()

    def test_blank_text_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_embeddings(
                texts=[
                    "Valid text.",
                    "   ",
                ],
                client=self.client,
            )

        self.client.embeddings.create.assert_not_called()

    def test_invalid_embedding_dimension_is_rejected(
        self,
    ):
        self.client.embeddings.create.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(
                    index=0,
                    embedding=[0.1] * 10,
                )
            ]
        )

        with self.assertRaises(InvalidEmbeddingResponseError):
            generate_embedding(
                text="Risk.",
                client=self.client,
            )

    def test_missing_embedding_is_rejected(
        self,
    ):
        self.client.embeddings.create.return_value = SimpleNamespace(data=[])

        with self.assertRaises(InvalidEmbeddingResponseError):
            generate_embedding(
                text="Risk.",
                client=self.client,
            )

    def test_provider_error_is_translated(
        self,
    ):
        class FakeAPIError(Exception):
            pass

        with patch(
            "portfolios.ai.embeddings.APIError",
            FakeAPIError,
        ):
            self.client.embeddings.create.side_effect = FakeAPIError("Provider failed.")

            with self.assertRaises(EmbeddingProviderError):
                generate_embedding(
                    text="Risk.",
                    client=self.client,
                )
