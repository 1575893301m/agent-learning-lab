# Markdown QA Agent

本项目让 Ollama 模型根据本地 Markdown 笔记回答问题。Python 扫描笔记并用字符级 TF-IDF 检索相关段落，再把检索结果作为 Observation 交回模型。

## 项目结构

```text
markdown-qa-agent/
├── main.py
├── requirements.txt
├── notes/
│   └── learning-log.md
├── tests/
│   └── test_main.py
├── README.md
└── RESULTS.md
```

## 安装

确保本地 Ollama 服务可用，并已下载 `qwen2.5:3b`。然后安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

## 运行

```powershell
python main.py
```

输入关于本地笔记的问题，例如“ReAct 计算器如何处理工具结果？”。若问题需要查询笔记，模型会请求 `search_notes`，程序将相似段落作为 Observation 回传。

把自己的 `.md` 笔记放入 `notes/`，子目录也会递归扫描。非 Markdown 文件和空文件会忽略。

## 测试

自动化测试用 mock 模拟 Ollama，不需要启动模型：

```powershell
python -m unittest discover -s tests -v
```

## 当前边界

- 检索使用字符级 TF-IDF 和余弦相似度，是轻量基线，不是语义向量检索。
- 文档按空行分段；超长段落目前作为单个片段处理。
- 最终回答仍由模型生成，应核对是否忠实于 Observation。
