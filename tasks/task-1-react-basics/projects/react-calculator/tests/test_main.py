import unittest
from unittest.mock import patch

from main import calculator, react_agent


class CalculatorTests(unittest.TestCase):
    def test_supported_operations(self):
        self.assertEqual(calculator(2, 3, "+"), 5)
        self.assertEqual(calculator(5, 3, "-"), 2)
        self.assertEqual(calculator(2, 3, "*"), 6)
        self.assertEqual(calculator(6, 3, "/"), 2)

    def test_division_by_zero(self):
        with self.assertRaisesRegex(ZeroDivisionError, "不能除以零"):
            calculator(1, 0, "/")

    def test_unknown_operator(self):
        with self.assertRaisesRegex(ValueError, "不支持的运算符"):
            calculator(1, 2, "%")


class ReactAgentTests(unittest.TestCase):
    @staticmethod
    def response(content):
        return {"message": {"content": content}}

    @patch("main.ollama.chat")
    def test_executes_action_and_returns_final_answer(self, chat):
        chat.side_effect = [
            self.response("Thought: 需要计算\nAction: calculator|1234|456|*"),
            self.response("Final Answer: 562704"),
        ]

        result = react_agent("1234乘以456等于多少？")

        self.assertEqual(result, "562704")
        self.assertEqual(chat.call_count, 2)
        messages = chat.call_args_list[1].kwargs["messages"]
        self.assertIn("Observation: 562704", messages[-1]["content"])

    @patch("main.ollama.chat")
    def test_reports_tool_error_to_model(self, chat):
        chat.side_effect = [
            self.response("Action: calculator|1|0|/"),
            self.response("Final Answer: 无法除以零"),
        ]

        result = react_agent("1除以0是多少？")

        self.assertEqual(result, "无法除以零")
        messages = chat.call_args_list[1].kwargs["messages"]
        self.assertIn("工具执行错误: 不能除以零", messages[-1]["content"])

    @patch("main.ollama.chat")
    def test_reports_malformed_action_and_stops_at_limit(self, chat):
        chat.return_value = self.response("Thought: 格式不正确")

        result = react_agent("随便算一下", max_steps=2)

        self.assertEqual(result, "超过最大步骤限制")
        self.assertEqual(chat.call_count, 2)
        messages = chat.call_args_list[1].kwargs["messages"]
        self.assertIn("工具调用格式错误", messages[-1]["content"])


if __name__ == "__main__":
    unittest.main()
