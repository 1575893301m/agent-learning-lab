# Task 1 测试结果

## 环境

- Python 3.13
- Ollama 0.40.16
- 模型：`qwen2.5:3b`
- Python 包：`ollama`

## 自动化测试

测试文件：`tests/test_main.py`

覆盖内容：

- `+`、`-`、`*`、`/` 四种基本运算
- 除零和不支持的运算符
- ReAct Action 的解析、工具执行和 Final Answer 返回
- 工具错误回传给模型
- 错误格式和最大步骤限制

运行命令：

```text
python -m unittest discover -s tests -v
```

本次结果：6 个测试全部通过（`OK`）。

## 真实 Ollama 测试：乘法

输入：

```text
1234乘以456等于多少？
```

运行命令：

```text
python main.py
```

实际最终结果：

```text
562704.0
```

测试通过。本次运行中，模型第一轮在 Action 后还附带了一个错误答案 `564384`。程序检测到 Action 后仍然执行 Python 计算器，并将实际计算结果 `562704.0` 作为 Observation 传回；模型第二轮据此给出正确答案。这也验证了程序没有采信模型自行编造的 Observation 或答案。

自动化测试使用 mock，不依赖 Ollama；本节记录的是真实 Ollama 服务和 `qwen2.5:3b` 模型运行结果。
