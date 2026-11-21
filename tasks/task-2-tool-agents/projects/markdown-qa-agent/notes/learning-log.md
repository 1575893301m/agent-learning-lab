# 学习记录

本周用 Python 和 Ollama 实现了 ReAct 计算器 Agent。模型提出 Action，Python 工具执行加减乘除，计算结果作为 Observation 返回模型。

Task 2 的第一个项目是本地 Markdown 笔记问答 Agent。它扫描本地 Markdown 笔记，检索相关段落，再让模型基于检索结果回答。

ReAct 表示 Reasoning and Acting，常用循环为 Thought、Action、Observation，直到模型给出 Final Answer。
