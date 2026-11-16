# ReAct Calculator Agent

这是 Task 1 的第一个实践项目：使用 Python 和 Ollama 手写一个最小 ReAct Agent。

## 学习目标

- 理解 Agent = LLM + 上下文 + 工具
- 理解 Thought -> Action -> Observation -> Final Answer
- 使用 Ollama 调用本地大模型
- 手写工具注册、工具执行和模型输出解析
- 处理错误参数、除零和最大步骤限制

## 项目结构

```text
react-calculator/
├── main.py
├── README.md
├── requirements.txt
├── RESULTS.md
└── tests/
    └── test_main.py
```

## 安装和运行

```text
pip install -r requirements.txt
python main.py
```

运行前需要启动 Ollama，并准备 `qwen2.5:3b` 模型。模型名称可以在 `main.py` 顶部的 `MODEL` 常量中调整。

## 运行测试

自动化测试使用 mock，不需要启动 Ollama：

```text
python -m unittest discover -s tests -v
```

测试详情和手动运行说明见 `RESULTS.md`。

