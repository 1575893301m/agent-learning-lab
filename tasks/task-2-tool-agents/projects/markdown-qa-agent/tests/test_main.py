import unittest
from unittest.mock import patch

import main


class NoteLoadingTests(unittest.TestCase):
    def test_loads_markdown_recursively_and_ignores_other_files(self):
        notes = main.load_notes(main.NOTES_DIR)
        self.assertTrue(any(note["filename"] == "learning-log.md" for note in notes))
        self.assertFalse(any(note["filename"].endswith(".txt") for note in notes))

    def test_missing_directory_returns_empty_list(self):
        self.assertEqual(main.load_notes(main.PROJECT_ROOT / "does-not-exist"), [])


class NoteSearchTests(unittest.TestCase):
    def setUp(self):
        self.notes = [
            {
                "filename": "agent.md",
                "content": "ReAct计算器使用Python执行乘法，并把结果作为Observation返回。\n\nMarkdown问答Agent会检索本地笔记。",
            },
            {"filename": "cooking.md", "content": "红烧茄子需要茄子、大蒜和酱油。"},
        ]

    def test_returns_most_relevant_paragraph_first(self):
        results = main.search_relevant_notes("ReAct计算器如何处理乘法结果", self.notes)
        self.assertTrue(results)
        self.assertEqual(results[0]["filename"], "agent.md")
        self.assertIn("Python执行乘法", results[0]["content"])

    def test_no_notes_or_blank_question_returns_no_results(self):
        self.assertEqual(main.search_relevant_notes("问题", []), [])
        self.assertEqual(main.search_relevant_notes("  ", self.notes), [])

    def test_unrelated_question_is_below_threshold(self):
        self.assertEqual(
            main.search_relevant_notes("火星探测器的轨道参数", self.notes, threshold=0.8),
            [],
        )


class ReactAgentTests(unittest.TestCase):
    @patch("main.ollama.chat")
    @patch("main.load_notes")
    def test_searches_notes_then_returns_final_answer(self, load_notes, chat):
        load_notes.return_value = [
            {"filename": "agent.md", "content": "第二个项目是 Markdown 笔记问答 Agent。"}
        ]
        chat.side_effect = [
            {"message": {"content": "Action: search_notes"}},
            {"message": {"content": "Final Answer: Markdown 笔记问答 Agent"}},
        ]

        answer = main.react_agent("我的第二个项目是什么？")

        self.assertEqual(answer, "Markdown 笔记问答 Agent")
        self.assertEqual(chat.call_count, 2)
        second_turn = chat.call_args_list[1].kwargs["messages"]
        self.assertIn("Observation:", second_turn[-1]["content"])
        self.assertIn("第二个项目是 Markdown 笔记问答 Agent", second_turn[-1]["content"])

    @patch("main.ollama.chat")
    @patch("main.load_notes", return_value=[])
    def test_returns_direct_answer_when_model_does_not_request_search(self, _load_notes, chat):
        chat.return_value = {"message": {"content": "Final Answer: 你好"}}
        self.assertEqual(main.react_agent("你好"), "你好")
        self.assertEqual(chat.call_count, 1)

    @patch("main.ollama.chat")
    @patch("main.load_notes", return_value=[])
    def test_retries_when_model_violates_output_protocol(self, _load_notes, chat):
        chat.side_effect = [
            {"message": {"content": "我猜是计算器项目。"}},
            {"message": {"content": "Final Answer: 未能从笔记中确认。"}},
        ]

        answer = main.react_agent("我的第二个 Agent 项目是什么？")

        self.assertEqual(answer, "未能从笔记中确认。")
        self.assertEqual(chat.call_count, 2)
        self.assertIn("输出格式错误", chat.call_args_list[1].kwargs["messages"][-1]["content"])

    @patch("main.ollama.chat")
    @patch("main.search_relevant_notes")
    @patch("main.load_notes", return_value=[])
    def test_accepts_plain_answer_after_observation(self, _load_notes, search, chat):
        chat.side_effect = [
            {"message": {"content": "Action: search_notes"}},
            {"message": {"content": "你的第二个项目是 Markdown 笔记问答 Agent。"}},
        ]
        search.return_value = [
            {"filename": "learn-log.md", "content": "第二个项目是 Markdown 笔记问答 Agent。", "score": 0.8}
        ]

        answer = main.react_agent("我的第二个 Agent 项目是什么？")

        self.assertEqual(answer, "你的第二个项目是 Markdown 笔记问答 Agent。")
        self.assertEqual(search.call_count, 1)
        self.assertEqual(chat.call_count, 2)

    @patch("main.ollama.chat")
    @patch("main.search_relevant_notes")
    @patch("main.load_notes", return_value=[])
    def test_does_not_repeat_search_after_observation(self, _load_notes, search, chat):
        chat.side_effect = [
            {"message": {"content": "Action: search_notes"}},
            {"message": {"content": "Action: search_notes\nFinal Answer: 我需要再查一次"}},
            {"message": {"content": "Final Answer: 根据已提供的笔记，答案是 Markdown 问答 Agent。"}},
        ]
        search.return_value = []

        answer = main.react_agent("我的第二个 Agent 项目是什么？")

        self.assertEqual(answer, "根据已提供的笔记，答案是 Markdown 问答 Agent。")
        self.assertEqual(search.call_count, 1)
        self.assertEqual(chat.call_count, 3)
        self.assertIn("勿重复检索", chat.call_args_list[2].kwargs["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
