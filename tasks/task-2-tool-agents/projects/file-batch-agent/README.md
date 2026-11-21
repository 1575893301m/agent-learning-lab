# File Batch Agent

本地多步骤 Markdown 文件处理 Agent。Harness 按固定顺序调用工具：列出文件、逐个读取并筛选段落；每一步在终端显示 Action/Observation。模型只负责根据所有命中段落生成总结，Python 校验总结非空后写入新文件。

本项目有意让 Python 控制流程顺序，而不是让小模型自由连续生成工具 Action。这样仍能学习多步骤工具执行、Observation 汇总、模型生成和状态控制，同时避免模型跳步、重复调用或提交空参数。

## 安全范围

- 只读取 `agent_workspace/` 的 Markdown 直接子文件。
- 只向 `output/` 写入新的 Markdown 文件。
- 拒绝路径穿越和覆盖已有输出文件。
- 依据文件数量检查所需步骤是否超过 `MAX_STEPS`。

## 运行

确保 Ollama 正在运行且 `qwen2.5:3b` 可用，在项目目录运行：

```powershell
python -m pip install -r requirements.txt
python main.py
```

示例任务：

```text
找出 agent_workspace 中所有 Markdown 文件里包含“Agent”的段落，整理成学习总结并保存为 agent-summary.md。
```

测试：

```powershell
python -m unittest discover -s tests -v
```

完成后到 `output/` 检查生成的 Markdown 文件。输出文件已存在时程序拒绝覆盖；请在任务中指定另一个文件名。
