# Task 2 项目 1：本地 Markdown 问答 Agent

## 1. 本次学习目标

在 Task 1 的 ReAct 计算器 Agent 基础上，增加一个能够访问本地资料的工具。

本项目要学会的核心能力是：

> 模型先判断是否需要查资料，Python 工具负责检索真实内容，模型再根据检索结果回答。

这也是一个简化版的检索增强生成（RAG）流程。

## 2. 项目做了什么

用户输入一个关于本地学习笔记的问题，例如：

```text
我的第二个 Agent 项目是什么？
```

Agent 会：

1. 读取 `notes/` 目录下的 Markdown 文件；
2. 找到与问题最相关的笔记段落；
3. 把检索结果作为 `Observation` 交给模型；
4. 让模型根据笔记内容生成最终答案。

项目目录：

```text
markdown-qa-agent/
├── main.py              # Agent、检索工具和主程序
├── notes/                # 本地 Markdown 笔记
│   └── learning-log.md
├── tests/                # 自动化测试
├── README.md
├── RESULTS.md
└── requirements.txt
```

## 3. 完整运行流程

整体流程如下：

```text
用户问题
  ↓
System Prompt 告诉模型：涉及个人记录时必须先检索
  ↓
模型输出 Action: search_notes
  ↓
Python 识别 Action 并执行搜索工具
  ↓
工具读取 Markdown、切分段落、计算相关性
  ↓
搜索结果作为 Observation 回填消息
  ↓
模型根据 Observation 输出 Final Answer
  ↓
程序提取并显示最终答案
```

## 4. 用实际问题走一遍

输入：

```text
我的第二个 Agent 项目是什么？
```

### 第 1 步：模型决定行动

模型看到这是一个关于学习记录的问题，因此输出：

```text
Action: search_notes
```

这一步只由模型完成。模型还没有读取文件，也没有得到答案，它只是决定调用哪个工具。

### 第 2 步：Python 执行检索

程序识别到 `search_notes` 后调用：

```python
results = search_relevant_notes(question, notes)
```

这一步由 Python 完成，不是模型完成。它会：

1. 读取 `notes/learning-log.md`；
2. 按空行把文档切成段落；
3. 把问题和段落转换成字符级 TF-IDF 特征；
4. 用余弦相似度计算相关程度；
5. 按相似度排序，返回最相关的段落。

可能找到的内容是：

```text
文件：learning-log.md
Task 2 的第一个项目是本地 Markdown 笔记问答 Agent。
它扫描本地 Markdown 笔记，检索相关段落，再让模型基于检索结果回答。
```

### 第 3 步：Observation 回填

程序把搜索结果包装成：

```text
Observation:
文件：learning-log.md
Task 2 的第一个项目是本地 Markdown 笔记问答 Agent。
它扫描本地 Markdown 笔记，检索相关段落，再让模型基于检索结果回答。
请基于以上笔记回答原问题。
```

Observation 的意思是“工具观察结果”。它把 Python 工具实际找到的事实交还给模型，作为模型下一轮回答的上下文。

### 第 4 步：模型生成最终答案

模型根据 Observation 输出：

```text
Final Answer: 我的第二个 Agent 项目是本地 Markdown 笔记问答 Agent。
这个项目扫描本地 Markdown 笔记，检索相关段落，再由模型基于检索结果回答。
```

程序识别 `Final Answer:`，提取后面的文字并显示给用户。

## 5. 模型、工具和 Agent 的分工

| 部分 | 负责什么 |
|---|---|
| 模型（Qwen） | 理解问题、决定是否调用工具、组织自然语言答案 |
| `search_relevant_notes()` | 读取和检索本地 Markdown 内容 |
| `Observation` | 把工具结果反馈给模型 |
| `react_agent()` | 维护消息、循环调用模型、解析 Action 和 Final Answer |

模型没有直接读取文件，也没有计算 TF-IDF。模型只提出行动并使用工具返回的结果。

## 6. 和 Task 1 计算器 Agent 的本质区别

两者共享同一套 Agent 控制框架：

```text
问题 → Action → Python 工具 → Observation → Final Answer
```

真正的区别是工具能力和数据类型：

| 对比 | Task 1 计算器 Agent | Task 2 项目 1 Markdown Agent |
|---|---|---|
| 工具 | `calculator` | `search_notes` |
| 处理对象 | 数字和运算符 | 文件和自然语言段落 |
| 工具结果 | 精确数值 | 相关资料片段 |
| 主要能力 | 执行确定计算 | 从外部资料获取依据 |
| 典型风险 | 除零、参数格式错误 | 找不到资料、检索不相关、编造答案 |

所以第二个项目不是重复练习，而是把 Agent 从“会执行计算”扩展到“会访问外部知识”。

## 7. 关键代码理解

### 7.1 读取笔记

```python
notes = load_notes()
```

递归扫描 `notes/` 下的 `.md` 文件，读取文件名和内容，形成供检索使用的数据。

### 7.2 搜索相关内容

```python
results = search_relevant_notes(question, notes)
```

这是本项目的核心工具调用。它不是让模型搜索，而是由 Python 执行文本检索。

### 7.3 发送工具结果

```python
messages.append({
    "role": "user",
    "content": f"Observation:\n{observation}\n请基于以上笔记回答原问题。",
})
```

把搜索结果加入消息历史，让模型下一轮能够看到工具结果。

### 7.4 提取最终答案

```python
if "Final Answer:" in content:
    return content.split("Final Answer:", 1)[1].strip()
```

找到最终答案标记后，删除标记前面的内容，只返回真正的答案文字。

## 8. 这类 Agent 的实际应用

- 企业内部制度和知识库问答；
- 个人学习笔记助手；
- 项目 README 和代码库问答；
- 客服文档问答；
- 合同、论文和技术资料检索；
- 本地文件搜索和总结。

只要把 `search_notes()` 换成数据库搜索、网页搜索或代码搜索，整体 Agent 框架仍然可以复用。

## 9. 本次运行结果

运行命令：

```powershell
python main.py
```

输入：

```text
我的第二个 Agent 项目是什么？
```

实际结果：

```text
--- Agent step ---
Action: search_notes

--- Agent step ---
Final Answer: 我的第二个 Agent 项目是本地 Markdown 笔记问答 Agent。
这个项目扫描本地 Markdown 笔记，检索相关段落，再由模型基于检索结果回答。
```

这说明单工具 ReAct 流程已经正常运行。

## 10. 本次学习结论

1. Agent 不等于模型本身，而是模型、工具和控制循环的组合。
2. 模型负责决定做什么，Python 工具负责真正执行。
3. `Observation` 是工具返回给模型的事实依据。
4. Markdown 问答 Agent 是“检索后回答”的最小实践。
5. Task 1 学的是调用工具执行动作；Task 2 项目 1 学的是调用工具获取外部信息。
6. 后续项目将在此基础上继续增加多工具选择和多步骤任务执行。

## 11. 如何验证

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

运行程序：

```powershell
python main.py
```

运行测试：

```powershell
python -m unittest discover -s tests -v
```
