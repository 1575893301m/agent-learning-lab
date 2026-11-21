# Todo Agent

一个本地待办管理 ReAct Agent。模型根据用户意图选择新增、查看、修改或删除工具；Python 校验参数并操作 `data/todos.json`，再把操作结果作为 Observation 交还模型。

## 结构

```text
todo-agent/
├── main.py
├── data/todos.json
├── tests/test_main.py
├── requirements.txt
├── README.md
└── RESULTS.md
```

## 安装和运行

确保 Ollama 正在运行且已下载 `qwen2.5:3b`，然后在本目录执行：

```powershell
python -m pip install -r requirements.txt
python main.py
```

示例输入：

```text
帮我新增一个明天下午 3 点学习 Agent 的待办
```

也可以尝试查看待办、修改编号为 1 的待办，或删除编号为 1 的待办。

自动化测试：

```powershell
python -m unittest discover -s tests -v
```

## 可用工具

- `add_todo(content, time)`：新增待办，自动分配编号，初始状态为未完成。
- `list_todos()`：列出所有待办。
- `update_todo(id, content?, time?, done?)`：修改指定待办的一个或多个字段。
- `delete_todo(id)`：删除指定待办。

数据保存在项目自己的 `data/todos.json`。直接执行 Python 工具函数时，它会立刻修改 JSON 文件；通过 Agent 执行时，模型先给出 JSON 工具请求，Python 校验后才执行。

## 设计边界

- 模型只能选择已注册的四种工具；未知工具、额外参数和错误类型会被拒绝。
- 每次最多执行 `MAX_STEPS` 次模型请求，避免无限循环。
- 工具执行结果作为 Observation 反馈给模型；最终回复应以 `Final Answer:` 开头。
- 本项目是本地单用户学习示例，不提供并发写入、身份验证或远程访问能力。
