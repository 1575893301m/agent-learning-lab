# 文件读取 Agent 测试结果

## 自动化测试

测试覆盖：正常读取、文件不存在、项目目录外路径、超长文件，以及 ReAct 工具调用后的最终回答。

运行命令：

```text
python -m unittest discover -s tests -v
```

真实 Ollama 测试需要后续准备示例文本文件后运行。
