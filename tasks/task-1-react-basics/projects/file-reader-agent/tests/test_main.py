import unittest
from pathlib import Path
from unittest.mock import patch

import main


class ReadFileTests(unittest.TestCase):
    def setUp(self):
        self.root = main.PROJECT_ROOT

    def test_reads_utf8_file(self):
        self.assertIn("File Reader Agent", main.read_file("README.md"))

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            main.read_file("missing.txt")

    def test_blocks_path_outside_project(self):
        with self.assertRaises(PermissionError):
            main.read_file("../outside.txt")

    def test_rejects_oversized_file(self):
        with patch.object(Path, "is_file", return_value=True), patch.object(
            Path, "read_text", return_value="a" * (main.MAX_CONTENT_LENGTH + 1)
        ):
            with self.assertRaises(ValueError):
                main.read_file("README.md")


class AgentTests(unittest.TestCase):
    @patch("main.ollama.chat")
    def test_returns_answer_after_reading(self, chat):
        chat.side_effect = [
            {"message": {"content": "Action: read_file|README.md"}},
            {"message": {"content": "Final Answer: 文件说明"}},
        ]
        result = main.react_file_agent("读取 README.md 并总结")
        self.assertEqual(result, "文件说明")
        self.assertIn("Observation:", chat.call_args_list[1].kwargs["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
