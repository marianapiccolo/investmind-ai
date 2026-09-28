from django.test import SimpleTestCase

from portfolios.ai.chunking import (
    TextChunk,
    chunk_markdown,
    count_tokens,
)


class KnowledgeChunkingTests(SimpleTestCase):
    def test_counts_tokens(self):
        result = count_tokens("Portfolio risk.")

        self.assertGreater(
            result,
            0,
        )

    def test_splits_markdown_by_headings(
        self,
    ):
        markdown = """
# Portfolio Risk

General risk introduction.

## Volatility

Volatility measures return dispersion.

## Drawdown

Drawdown measures peak-to-trough decline.
"""

        chunks = chunk_markdown(markdown)

        self.assertEqual(
            len(chunks),
            3,
        )

        self.assertEqual(
            chunks[0].section_title,
            "Portfolio Risk",
        )

        self.assertEqual(
            chunks[1].section_title,
            "Volatility",
        )

        self.assertEqual(
            chunks[2].section_title,
            "Drawdown",
        )

    def test_chunk_contains_content(
        self,
    ):
        markdown = """
## Diversification

Diversification spreads exposure across
different investments.
"""

        chunks = chunk_markdown(markdown)

        self.assertEqual(
            len(chunks),
            1,
        )

        self.assertIsInstance(
            chunks[0],
            TextChunk,
        )

        self.assertIn(
            "Diversification spreads",
            chunks[0].content,
        )

        self.assertGreater(
            chunks[0].token_count,
            0,
        )

    def test_long_section_is_split(
        self,
    ):
        repeated_text = " ".join(["portfolio"] * 100)

        markdown = f"## Risk\n\n{repeated_text}"

        chunks = chunk_markdown(
            markdown,
            token_limit=20,
            overlap_tokens=5,
        )

        self.assertGreater(
            len(chunks),
            1,
        )

        for chunk in chunks:
            self.assertLessEqual(
                chunk.token_count,
                20,
            )

    def test_long_chunks_keep_section_title(
        self,
    ):
        repeated_text = " ".join(["diversification"] * 100)

        markdown = f"## Diversification\n\n{repeated_text}"

        chunks = chunk_markdown(
            markdown,
            token_limit=20,
            overlap_tokens=5,
        )

        for chunk in chunks:
            self.assertEqual(
                chunk.section_title,
                "Diversification",
            )

    def test_overlap_repeats_context(
        self,
    ):
        markdown = (
            "## Risk\n\n"
            "one two three four five six "
            "seven eight nine ten eleven "
            "twelve thirteen fourteen"
        )

        chunks = chunk_markdown(
            markdown,
            token_limit=8,
            overlap_tokens=3,
        )

        self.assertGreaterEqual(
            len(chunks),
            2,
        )

        first_words = set(chunks[0].content.split())

        second_words = set(chunks[1].content.split())

        self.assertTrue(first_words & second_words)

    def test_blank_markdown_is_rejected(
        self,
    ):
        with self.assertRaises(ValueError):
            chunk_markdown("   ")

    def test_invalid_token_limit_is_rejected(
        self,
    ):
        with self.assertRaises(ValueError):
            chunk_markdown(
                "Some content.",
                token_limit=0,
            )

    def test_overlap_must_be_smaller_than_limit(
        self,
    ):
        with self.assertRaises(ValueError):
            chunk_markdown(
                "Some content.",
                token_limit=10,
                overlap_tokens=10,
            )
