from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase

from portfolios.ai.tool_calling import (
    InvalidAIToolResponseError,
    ToolCallingLimitError,
    answer_portfolio_question,
    get_openai_portfolio_tools,
)


class PortfolioAIToolCallingTests(SimpleTestCase):
    def setUp(self):
        self.portfolio = Mock()
        self.client = Mock()

    def test_openai_tool_definitions_are_strict(
        self,
    ):
        tools = get_openai_portfolio_tools()

        self.assertEqual(
            len(tools),
            4,
        )

        for tool in tools:
            self.assertEqual(
                tool["type"],
                "function",
            )

            self.assertTrue(tool["strict"])

            self.assertEqual(
                tool["parameters"]["properties"],
                {},
            )

            self.assertEqual(
                tool["parameters"]["required"],
                [],
            )

    def test_model_can_answer_without_tool(
        self,
    ):
        response = SimpleNamespace(
            id="resp_1",
            output=[],
            output_text=("This is a general explanation."),
        )

        self.client.responses.create.return_value = response

        result = answer_portfolio_question(
            question=("What does diversification mean?"),
            portfolio=self.portfolio,
            client=self.client,
        )

        self.assertEqual(
            result,
            "This is a general explanation.",
        )

        self.assertEqual(
            self.client.responses.create.call_count,
            1,
        )

    @patch("portfolios.ai.tool_calling.execute_portfolio_tool")
    def test_executes_requested_tool(
        self,
        mock_execute_tool,
    ):
        tool_call = SimpleNamespace(
            type="function_call",
            name="get_portfolio_risk",
            arguments="{}",
            call_id="call_123",
        )

        first_response = SimpleNamespace(
            id="resp_1",
            output=[tool_call],
            output_text="",
        )

        final_response = SimpleNamespace(
            id="resp_2",
            output=[],
            output_text=("The portfolio has moderate historical volatility."),
        )

        self.client.responses.create.side_effect = [
            first_response,
            final_response,
        ]

        mock_execute_tool.return_value = {"annualized_volatility": "18.25"}

        result = answer_portfolio_question(
            question=("How risky is my portfolio?"),
            portfolio=self.portfolio,
            client=self.client,
        )

        mock_execute_tool.assert_called_once_with(
            tool_name="get_portfolio_risk",
            portfolio=self.portfolio,
            arguments={},
        )

        self.assertEqual(
            result,
            ("The portfolio has moderate historical volatility."),
        )

        self.assertEqual(
            self.client.responses.create.call_count,
            2,
        )

    @patch("portfolios.ai.tool_calling.execute_portfolio_tool")
    def test_tool_result_is_returned_to_model(
        self,
        mock_execute_tool,
    ):
        tool_call = SimpleNamespace(
            type="function_call",
            name="get_portfolio_composition",
            arguments="{}",
            call_id="call_456",
        )

        first_response = SimpleNamespace(
            id="resp_1",
            output=[tool_call],
            output_text="",
        )

        final_response = SimpleNamespace(
            id="resp_2",
            output=[],
            output_text="Final answer.",
        )

        self.client.responses.create.side_effect = [
            first_response,
            final_response,
        ]

        mock_execute_tool.return_value = {"top_holding": "AAPL"}

        answer_portfolio_question(
            question=("What is my largest holding?"),
            portfolio=self.portfolio,
            client=self.client,
        )

        second_call = self.client.responses.create.call_args_list[1]

        input_data = second_call.kwargs["input"]

        tool_outputs = [
            item
            for item in input_data
            if isinstance(item, dict) and item.get("type") == "function_call_output"
        ]

        self.assertEqual(
            len(tool_outputs),
            1,
        )

        self.assertEqual(
            tool_outputs[0]["call_id"],
            "call_456",
        )

        self.assertIn(
            "AAPL",
            tool_outputs[0]["output"],
        )

    @patch("portfolios.ai.tool_calling.execute_portfolio_tool")
    def test_executes_multiple_tools_in_same_round(
        self,
        mock_execute_tool,
    ):
        risk_call = SimpleNamespace(
            type="function_call",
            name="get_portfolio_risk",
            arguments="{}",
            call_id="call_risk",
        )

        diversification_call = SimpleNamespace(
            type="function_call",
            name=("get_portfolio_diversification"),
            arguments="{}",
            call_id="call_diversification",
        )

        first_response = SimpleNamespace(
            id="resp_1",
            output=[
                risk_call,
                diversification_call,
            ],
            output_text="",
        )

        final_response = SimpleNamespace(
            id="resp_2",
            output=[],
            output_text=("Risk and diversification were analyzed together."),
        )

        self.client.responses.create.side_effect = [
            first_response,
            final_response,
        ]

        mock_execute_tool.side_effect = [
            {"annualized_volatility": ("18.25")},
            {"average_correlation": "0.42"},
        ]

        result = answer_portfolio_question(
            question=("Analyze my risk and diversification."),
            portfolio=self.portfolio,
            client=self.client,
        )

        self.assertEqual(
            mock_execute_tool.call_count,
            2,
        )

        mock_execute_tool.assert_has_calls(
            [
                call(
                    tool_name=("get_portfolio_risk"),
                    portfolio=self.portfolio,
                    arguments={},
                ),
                call(
                    tool_name=("get_portfolio_diversification"),
                    portfolio=self.portfolio,
                    arguments={},
                ),
            ]
        )

        second_request = self.client.responses.create.call_args_list[1]

        input_data = second_request.kwargs["input"]

        tool_outputs = [
            item
            for item in input_data
            if isinstance(item, dict) and item.get("type") == "function_call_output"
        ]

        self.assertEqual(
            len(tool_outputs),
            2,
        )

        self.assertEqual(
            {item["call_id"] for item in tool_outputs},
            {
                "call_risk",
                "call_diversification",
            },
        )

        self.assertEqual(
            result,
            ("Risk and diversification were analyzed together."),
        )

    @patch("portfolios.ai.tool_calling.execute_portfolio_tool")
    def test_supports_multiple_tool_calling_rounds(
        self,
        mock_execute_tool,
    ):
        risk_call = SimpleNamespace(
            type="function_call",
            name="get_portfolio_risk",
            arguments="{}",
            call_id="call_risk",
        )

        composition_call = SimpleNamespace(
            type="function_call",
            name="get_portfolio_composition",
            arguments="{}",
            call_id="call_composition",
        )

        first_response = SimpleNamespace(
            id="resp_1",
            output=[risk_call],
            output_text="",
        )

        second_response = SimpleNamespace(
            id="resp_2",
            output=[composition_call],
            output_text="",
        )

        final_response = SimpleNamespace(
            id="resp_3",
            output=[],
            output_text="Combined analysis.",
        )

        self.client.responses.create.side_effect = [
            first_response,
            second_response,
            final_response,
        ]

        mock_execute_tool.side_effect = [
            {"annualized_volatility": ("18.25")},
            {"top_holding": "AAPL"},
        ]

        result = answer_portfolio_question(
            question=("Analyze the structure and risk of my portfolio."),
            portfolio=self.portfolio,
            client=self.client,
        )

        self.assertEqual(
            mock_execute_tool.call_count,
            2,
        )

        self.assertEqual(
            self.client.responses.create.call_count,
            3,
        )

        self.assertEqual(
            result,
            "Combined analysis.",
        )

    def test_invalid_tool_arguments_are_rejected(
        self,
    ):
        tool_call = SimpleNamespace(
            type="function_call",
            name="get_portfolio_risk",
            arguments="{invalid-json",
            call_id="call_bad",
        )

        response = SimpleNamespace(
            id="resp_1",
            output=[tool_call],
            output_text="",
        )

        self.client.responses.create.return_value = response

        with self.assertRaises(InvalidAIToolResponseError):
            answer_portfolio_question(
                question=("How risky is my portfolio?"),
                portfolio=self.portfolio,
                client=self.client,
            )

    def test_empty_question_is_rejected(self):
        with self.assertRaises(ValueError):
            answer_portfolio_question(
                question="   ",
                portfolio=self.portfolio,
                client=self.client,
            )

    def test_empty_final_response_is_rejected(
        self,
    ):
        response = SimpleNamespace(
            id="resp_1",
            output=[],
            output_text="",
        )

        self.client.responses.create.return_value = response

        with self.assertRaises(InvalidAIToolResponseError):
            answer_portfolio_question(
                question="Explain my portfolio.",
                portfolio=self.portfolio,
                client=self.client,
            )

    @patch("portfolios.ai.tool_calling.execute_portfolio_tool")
    def test_tool_calling_limit_is_enforced(
        self,
        mock_execute_tool,
    ):
        responses = []

        for index in range(5):
            tool_call = SimpleNamespace(
                type="function_call",
                name="get_portfolio_risk",
                arguments="{}",
                call_id=f"call_{index}",
            )

            responses.append(
                SimpleNamespace(
                    id=f"resp_{index}",
                    output=[tool_call],
                    output_text="",
                )
            )

        self.client.responses.create.side_effect = responses

        mock_execute_tool.return_value = {"annualized_volatility": "18.25"}

        with self.assertRaises(ToolCallingLimitError):
            answer_portfolio_question(
                question=("Keep analyzing my portfolio."),
                portfolio=self.portfolio,
                client=self.client,
            )

        self.assertEqual(
            mock_execute_tool.call_count,
            4,
        )
