from django.test import SimpleTestCase

from portfolios.ai.evals import (
    _evaluate_evidence,
    _resolve_context_path,
)


class AIEvidencePathTests(SimpleTestCase):
    def setUp(self):
        self.context = {
            "sections": {
                "composition": {
                    "data": {
                        "total_market_value": (
                            "333.6900"
                        ),
                        "top_holdings": [
                            {
                                "ticker": "AAPL",
                                "asset_name": (
                                    "Apple Inc."
                                ),
                                "allocation_percentage": (
                                    "100.00"
                                ),
                            }
                        ],
                        "sector_allocation": [
                            {
                                "label": (
                                    "Technology"
                                ),
                                "allocation_percentage": (
                                    "100.00"
                                ),
                            }
                        ],
                    }
                }
            }
        }

    def test_resolves_regular_dictionary_path(
        self,
    ):
        value = _resolve_context_path(
            context=self.context,
            path=(
                "sections.composition.data."
                "total_market_value"
            ),
        )

        self.assertEqual(
            value,
            "333.6900",
        )

    def test_resolves_list_index_path(
        self,
    ):
        value = _resolve_context_path(
            context=self.context,
            path=(
                "sections.composition.data."
                "top_holdings.0.ticker"
            ),
        )

        self.assertEqual(
            value,
            "AAPL",
        )

    def test_evidence_with_list_path_is_valid(
        self,
    ):
        result = _evaluate_evidence(
            context=self.context,
            report={
                "evidence": [
                    {
                        "metric_path": (
                            "sections.composition."
                            "data.top_holdings."
                            "0.ticker"
                        ),
                        "value": "AAPL",
                    },
                    {
                        "metric_path": (
                            "sections.composition."
                            "data.sector_allocation."
                            "0.label"
                        ),
                        "value": "Technology",
                    },
                ]
            },
        )

        self.assertTrue(
            result["passed"]
        )

        self.assertEqual(
            result["invalid_evidence"],
            [],
        )

    def test_invalid_list_index_raises_key_error(
        self,
    ):
        with self.assertRaises(
            KeyError
        ):
            _resolve_context_path(
                context=self.context,
                path=(
                    "sections.composition.data."
                    "top_holdings.99.ticker"
                ),
            )