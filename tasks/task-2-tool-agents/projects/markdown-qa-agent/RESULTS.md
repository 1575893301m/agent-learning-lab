# Markdown QA Agent 测试结果

## 测试环境

- Python 3.13
- 模型：`qwen2.5:3b`
- 检索：scikit-learn TF-IDF，字符 n-gram `(1, 3)`

## 自动化测试

运行命令：

```powershell
python -m unittest discover -s tests -v
```

覆盖 Markdown 递归扫描、缺失目录、相关段落排序、空查询、低相似度过滤，以及 ReAct 检索和 Observation 回填。

本次结果：10 个测试全部通过（`OK`）。

## 真实 Ollama 测试

测试问题：`我的第二个 Agent 项目是什么？`

实际流程：

1. 初次运行时，模型曾直接猜答案，未输出 `Action`；另一次运行中，它在 Observation 后漏掉 `Final Answer:`，随后重复请求检索。
2. Prompt 加入本地笔记问答示例；程序也调整为在 Observation 已回填后接受普通文本作为最终回答，并阻止重复检索。
3. 修复后再次运行，模型先输出 `Action: search_notes`；程序检索 `notes/learning-log.md` 并回填 Observation。
4. 模型随后输出 `Final Answer`，正确回答本地 Markdown 笔记问答 Agent。另一次真实运行中模型漏写标记但给出正确答案，程序也能正常结束。

结论：修复后的真实链路测试通过。模型仍可能违反文本协议；程序会在已收到 Observation 后把无 Action 的回复视作最终回答，因此仍应对照 Observation 验证答案内容。
