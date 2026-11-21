import unittest
from pathlib import Path
from unittest.mock import patch

import main


class FileToolTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent / "test-workspace"
        self.output = Path(__file__).parent / "test-output"
        self.root.mkdir(exist_ok=True)
        self.output.mkdir(exist_ok=True)
        (self.root / "notes.md").write_text(
            "Agent uses tools.\n\nPython can also parse JSON.\n\nA second Agent paragraph.", encoding="utf-8"
        )

    def tearDown(self):
        for folder in (self.root, self.output):
            for item in folder.iterdir():
                item.unlink()
            folder.rmdir()

    def test_list_read_and_filter(self):
        self.assertEqual(main.list_files(self.root), ["notes.md"])
        self.assertIn("Agent uses tools", main.read_file("notes.md", self.root))
        self.assertEqual(len(main.filter_paragraphs("notes.md", "agent", self.root)), 2)

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(ValueError):
            main.read_file("..\\outside.md", self.root)

    def test_write_refuses_overwrite_and_nested_path(self):
        main.write_summary("summary.md", "Summary", self.output)
        with self.assertRaises(FileExistsError):
            main.write_summary("summary.md", "Overwrite", self.output)
        with self.assertRaises(ValueError):
            main.write_summary("sub\\summary.md", "Nested", self.output)

    def test_dispatch_returns_tool_observation(self):
        result = main.execute_action({"action": "filter_paragraphs", "filename": "notes.md", "keyword": "Agent"}, self.root, self.output)
        self.assertIn("Agent uses tools", result)

    @patch("main.ollama.chat")
    def test_agent_orchestrates_tools_and_uses_model_only_for_summary(self, chat):
        second_file = self.root / "more.md"
        second_file.write_text("Agent planning uses observations.", encoding="utf-8")
        chat.return_value = {"message": {"content": "# Agent 学习总结\n\nAgent 使用工具并根据结果推进任务。"}}
        result = main.run_agent(
            "筛选 Agent 段落并保存为 result.md",
            work_dir=self.root,
            output_dir=self.output,
        )
        self.assertIn("已写入 result.md", result)
        self.assertEqual(chat.call_count, 1)
        summary_file = self.output / "result.md"
        self.assertIn("Agent 使用工具", summary_file.read_text(encoding="utf-8"))
        second_file.unlink()

    @patch("main.ollama.chat")
    def test_agent_writes_explanation_when_no_paragraph_matches(self, chat):
        (self.root / "notes.md").write_text("Nothing relevant here.", encoding="utf-8")
        result = main.run_agent(
            "筛选 Agent 段落并保存为 empty-result.md",
            work_dir=self.root,
            output_dir=self.output,
        )
        self.assertIn("已写入 empty-result.md", result)
        chat.assert_not_called()
        self.assertIn("没有找到", (self.output / "empty-result.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
