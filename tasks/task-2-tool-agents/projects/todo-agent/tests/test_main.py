import json
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class TodoToolTests(unittest.TestCase):
    def setUp(self):
        self.data_file = Path(__file__).parent / "test-data" / "todos.json"
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text("[]\n", encoding="utf-8")

    def tearDown(self):
        self.data_file.unlink(missing_ok=True)

    def test_add_list_update_and_delete(self):
        added = main.add_todo("學 Agent", "明天下午 3 點", self.data_file)
        self.assertIn("编号 1", added)
        self.assertIn("學 Agent", main.list_todos(self.data_file))

        updated = main.update_todo(1, content="學多工具 Agent", done=True, data_file=self.data_file)
        self.assertIn("已修改", updated)
        listing = main.list_todos(self.data_file)
        self.assertIn("學多工具 Agent", listing)
        self.assertIn("已完成", listing)

        deleted = main.delete_todo(1, self.data_file)
        self.assertIn("已删除", deleted)
        self.assertEqual(main.list_todos(self.data_file), "当前没有待办事项。")

    def test_ids_remain_unique_after_deleting_last_item(self):
        main.add_todo("A", "今天", self.data_file)
        main.add_todo("B", "明天", self.data_file)
        main.delete_todo(2, self.data_file)
        main.add_todo("C", "後天", self.data_file)
        todos = json.loads(self.data_file.read_text(encoding="utf-8"))
        self.assertEqual([todo["id"] for todo in todos], [1, 2])

    def test_validates_missing_fields_and_ids(self):
        self.assertIn("不能为空", main.add_todo(" ", "明天", self.data_file))
        self.assertIn("没有编号", main.update_todo(9, content="x", data_file=self.data_file))
        self.assertIn("没有编号", main.delete_todo(9, self.data_file))
        self.assertIn("没有提供", main.update_todo(1, data_file=self.data_file))

    def test_action_validation(self):
        self.assertIn("未知工具", main.execute_action({"action": "unknown"}, self.data_file))
        self.assertIn("必须是整数", main.execute_action({"action": "delete_todo", "id": True}, self.data_file))
        self.assertIn("不接受参数", main.execute_action({"action": "list_todos", "id": 1}, self.data_file))

    def test_parse_action_accepts_json_fence_and_rejects_invalid_json(self):
        self.assertEqual(main._parse_action('```json\n{"action":"list_todos"}\n```'), {"action": "list_todos"})
        with self.assertRaises(ValueError):
            main._parse_action("not json")


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.data_file = Path(__file__).parent / "test-data" / "todos.json"
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text("[]\n", encoding="utf-8")

    def tearDown(self):
        self.data_file.unlink(missing_ok=True)

    @patch("main.ollama.chat")
    def test_help_question_lists_commands_without_calling_model(self, chat):
        answer = main.react_todo_agent("我可以输入哪些指令")
        self.assertIn("新增", answer)
        self.assertIn("查看", answer)
        self.assertIn("修改", answer)
        self.assertIn("删除", answer)
        chat.assert_not_called()

    @patch("main.ollama.chat")
    def test_multiple_json_actions_are_rejected_without_tool_execution(self, chat):
        chat.return_value = {
            "message": {
                "content": '{"action":"add_todo","content":"A","time":"今天"}\n'
                '{"action":"list_todos"}'
            }
        }
        with patch("main.execute_action") as execute:
            answer = main.react_todo_agent("新增待办")
        self.assertIn("本轮没有执行任何待办操作", answer)
        execute.assert_not_called()
        chat.assert_called_once()

    @patch("main.ollama.chat")
    def test_routes_tool_and_returns_final_answer(self, chat):
        chat.side_effect = [
            {"message": {"content": '{"action":"add_todo","content":"學 Agent","time":"明天下午 3 點"}'}},
            {"message": {"content": "Final Answer: 已幫你新增待辦。"}},
        ]
        with patch("main.execute_action", return_value="已新增待办：编号 1。") as execute:
            answer = main.react_todo_agent("幫我新增明天下午 3 點學 Agent", max_steps=2)
        self.assertEqual(answer, "已幫你新增待辦。")
        self.assertEqual(execute.call_count, 1)
        second_messages = chat.call_args_list[1].kwargs["messages"]
        self.assertIn("Observation:", second_messages[-1]["content"])

    @patch("main.ollama.chat")
    def test_rejects_bad_action_format_without_executing_tool(self, chat):
        chat.return_value = {"message": {"content": "I will add a todo"}}
        with patch("main.execute_action") as execute:
            answer = main.react_todo_agent("新增待办", max_steps=2)
        self.assertIn("模型工具调用格式错误", answer)
        execute.assert_not_called()
        chat.assert_called_once()


if __name__ == "__main__":
    unittest.main()
