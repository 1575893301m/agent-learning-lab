# File Reader Agent

这是 Task 1 的第二个实践项目：使用 ReAct 循环让模型选择文件读取工具，再由 Python 读取文件内容。

## 运行

```text
python main.py
```

需要本地 Ollama 服务和 `qwen2.5:3b` 模型。问题中的路径必须是相对于本项目目录的路径。

## 安全限制

- 只允许读取项目目录内的文件。
- 文件必须是 UTF-8 文本。
- 文件内容最多读取 10,000 个字符。
- 文件不存在或工具失败时，错误会作为 Observation 返回模型。

## 测试

```text
python -m unittest discover -s tests -v
```
