# Agent 学习项目 GitHub 执行指南

本指南用于把 D:\Desktop\agent 整理成一个可持续更新、可运行、可展示的 GitHub 学习项目。

项目定位：

> agent-learning-lab：从零手写 Agent 的学习、实践与进化记录

不要把它做成“代码堆放处”。每个阶段都要包含：理论理解、可运行代码、测试结果、失败记录和个人总结。

---

## 一、最终目标

最终 GitHub 仓库包含四个学习阶段：

| 阶段 | 主要内容 | 目标能力 |
|---|---|---|
| Task 1 | ReAct 计算器、文件读取 Agent | 理解 Agent 基础循环 |
| Task 2 | Markdown 问答、待办、多步骤文件处理 | 工具调用和任务拆解 |
| Task 3 | 短期记忆、JSON 重试、错误恢复 | 记忆与可靠性 |
| Task 4 | 并行、权限、Plan & Solve、RAG、反思 | 高级 Agent 工程能力 |

完成后的仓库不是一个单一应用，而是一个 Agent 学习实验室，里面包含多个相互递进的子项目。

---

## 二、准备软件

### 1. GitHub 账号

打开 https://github.com/ 注册并登录，记住自己的 GitHub 用户名。

### 2. 本地软件

在 PowerShell 执行：

~~~powershell
git --version
python --version
ollama --version
~~~

如果某条命令提示找不到，先安装对应软件。

### 3. Ollama 模型

查看已有模型：

~~~powershell
ollama list
~~~

启动服务：

~~~powershell
ollama serve
~~~

另开一个 PowerShell 窗口，按电脑资源选择模型。例如：

~~~powershell
ollama pull qwen2.5:7b
~~~

后面代码中的模型名必须和 ollama list 显示的名称完全一致，不要盲目照抄 qwen:7b。

---

## 三、创建 GitHub 仓库

1. 登录 GitHub，点击右上角加号。
2. 选择 New repository。
3. Repository name 填 agent-learning-lab。
4. Description 填：从零手写 Agent 的学习、实践与进化记录。
5. 选择 Public。
6. 不勾选自动创建 README、.gitignore 和 License。
7. 点击 Create repository。
8. 复制仓库的 HTTPS 地址，格式类似：

~~~text
https://github.com/你的用户名/agent-learning-lab.git
~~~

---

## 四、整理本地目录

进入本地仓库：

~~~powershell
Set-Location 'D:\Desktop\agent'
Get-ChildItem -Force
~~~

当前仓库已经存在 .git，不要再次执行 git init。

建议把原来的中文目录改成适合 GitHub 展示的英文目录。以下命令只移动文件夹，不会删除文件：

~~~powershell
New-Item -ItemType Directory -Force -Path '.\tasks' | Out-Null
New-Item -ItemType Directory -Force -Path '.\docs' | Out-Null

Move-Item -LiteralPath '.\task 1' -Destination '.\tasks\task-1-react-basics'
Move-Item -LiteralPath '.\task 2' -Destination '.\tasks\task-2-tool-agents'
Move-Item -LiteralPath '.\task 3' -Destination '.\tasks\task-3-memory-retry'
Move-Item -LiteralPath '.\task 4' -Destination '.\tasks\task-4-advanced-agents'
~~~

目标目录：

~~~text
agent-learning-lab/
├── README.md
├── ROADMAP.md
├── .gitignore
├── LICENSE
├── tasks/
│   ├── task-1-react-basics/
│   ├── task-2-tool-agents/
│   ├── task-3-memory-retry/
│   └── task-4-advanced-agents/
└── docs/
    ├── learning-log.md
    └── book-notes.md
~~~

原书 PDF 不要上传，除非确认许可证明确允许。保留自己的读书笔记即可。

---

## 五、创建 .gitignore

在 D:\Desktop\agent 根目录创建 .gitignore，内容如下：

~~~gitignore
__pycache__/
*.py[cod]
.venv/
venv/
env/

.env
.env.*
!.env.example
*.key
*.pem

workspace/
agent_workspace/
knowledge_base/
notes/
notes_summary/
todos.json
*.log
*.db
*.npy

*.pdf
*.zip
*.mp4

.vscode/
.idea/
.DS_Store
Thumbs.db
~~~

确认 PDF 会被忽略：

~~~powershell
git check-ignore -v '.\tasks\task-1-react-basics\AI-Agents-in-Depth-zh-CN.pdf'
~~~

如果输出了 .gitignore 规则，说明它不会被提交。

---

## 六、创建根目录文档

### 1. README.md

根目录 README 至少包含：

~~~markdown
# Agent Learning Lab

从零手写 Agent 的学习、实践与进化记录。

## 学习路线

- Task 1：ReAct 基础
- Task 2：工具调用与多步骤任务
- Task 3：记忆、重试与错误恢复
- Task 4：并行、权限、规划、RAG 与反思

## 原则

- 尽量使用原生 Python
- 不依赖 LangChain 等 Agent 框架完成核心循环
- 每个项目必须可运行、可测试、可解释
- 记录失败原因和修复过程

## 当前进度

| 阶段 | 状态 |
|---|---|
| Task 1 | 未开始 |
| Task 2 | 未开始 |
| Task 3 | 未开始 |
| Task 4 | 未开始 |
~~~

### 2. ROADMAP.md

写清楚四个阶段、每个子项目、完成标准和状态。状态只使用：

~~~text
未开始 / 进行中 / 已完成 / 需要重做
~~~

### 3. 第一次提交

~~~powershell
git status
git add .
git commit -m "docs: add agent learning project skeleton"
~~~

如果 Git 提示没有设置身份：

~~~powershell
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
~~~

然后重新提交。

---

## 七、连接 GitHub 并推送

把地址换成自己的仓库地址：

~~~powershell
git remote add origin 'https://github.com/你的用户名/agent-learning-lab.git'
git branch -M main
git push -u origin main
~~~

如果提示 origin already exists，先查看：

~~~powershell
git remote -v
~~~

不要在没有确认的情况下删除远程地址。

打开 GitHub 仓库页面，确认能看到 README、ROADMAP、tasks 和 docs。

---

## 八、每个子项目的固定工作流

每个项目都按照以下 7 步执行。

### 第 1 步：创建 Issue

例如：

~~~text
[Task 1] 手写 ReAct 计算器 Agent
~~~

Issue 中写清目标和验收标准：

~~~markdown
## 目标
手写一个不依赖 Agent 框架的 ReAct 计算器。

## 验收标准
- 能调用本地 Ollama
- 能正确解析 Action
- 能执行加减乘除
- 能把 Observation 放回上下文
- 能输出 Final Answer
- 能处理格式错误和除零错误
~~~

### 第 2 步：创建分支

~~~powershell
git switch main
git pull origin main
git switch -c feature/task-1-react-calculator
~~~

命名规则：

~~~text
feature/功能名称
fix/问题名称
docs/文档名称
test/测试名称
~~~

### 第 3 步：准备项目文件

每个项目至少包含：

~~~text
README.md
main.py
requirements.txt
tests/
examples/
RESULTS.md
~~~

README 必须说明：

1. 解决什么问题。
2. 输入、思考、工具、观察和输出是什么。
3. 如何安装依赖。
4. 如何运行。
5. 测试输入和实际输出。
6. 当前已知问题。
7. 自己学到了什么。

### 第 4 步：运行和测试

~~~powershell
python --version
ollama list
python main.py
~~~

每个项目至少测试：

- 正常输入
- 错误工具名
- 错误参数
- 文件不存在
- 模型输出格式错误
- 工具执行异常
- 超过最大步骤
- 危险操作是否被拦截

### 第 5 步：提交

~~~powershell
git status
git diff --stat
git add .
git commit -m "feat(task-1): implement handwritten react calculator"
~~~

一次提交只做一类事情，不要把多个项目混在一个提交中。

### 第 6 步：推送并创建 Pull Request

~~~powershell
git push -u origin feature/task-1-react-calculator
~~~

在 GitHub 页面点击 Compare & pull request，填写：

- What changed：完成了什么。
- How tested：用什么命令测试。
- Known issues：还存在什么问题。

检查后点击 Merge pull request。

### 第 7 步：合并后打标签

~~~powershell
git switch main
git pull origin main
git tag -a v0.1-react-basics -m "complete React basics"
git push origin v0.1-react-basics
~~~

---

## 九、四个阶段的具体执行内容

### Task 1：ReAct 基础

建立两个子项目：

~~~text
tasks/task-1-react-basics/projects/react-calculator/
tasks/task-1-react-basics/projects/file-reader-agent/
~~~

计算器必须真正理解：

- calculator(a, b, op)
- 工具注册表
- 系统提示词
- messages 上下文
- ollama.chat
- Action 正则解析
- 工具执行
- Observation 回填
- 最大步骤限制

完成标准：成功完成 1234 * 456，并能解释主要参数。

文件读取 Agent 要处理：

- 文件不存在
- 编码错误
- 路径限制
- 内容过长
- 不允许读取工作区外文件

### Task 2：工具调用升级

建立三个子项目：

~~~text
projects/markdown-qa-agent/
projects/todo-agent/
projects/file-batch-agent/
~~~

验收重点：

- Markdown 问答能从本地文件检索答案。
- 待办 Agent 能新增、查询和完成待办。
- 文件批处理 Agent 能连续调用多个工具。

### Task 3：记忆和重试

建立：

~~~text
projects/memory-retry-agent/
~~~

必须测试：

1. 第一轮列出文件。
2. 第二轮读取上一轮发现的文件。
3. 人为制造非法 JSON。
4. 读取不存在的文件。
5. 确认错误会进入 Observation，并触发下一步调整。

注意：不要用无限递归实现 Agent 循环，应改成有上限的 while 或 for 循环。

### Task 4：高级 Agent

建立四个项目：

~~~text
projects/parallel-permission-agent/
projects/plan-solve-agent/
projects/handwritten-rag-agent/
projects/self-reflection-agent/
~~~

完成顺序：

~~~text
并行与权限
→ Plan & Solve
→ 手写 RAG
→ Self-Reflection
~~~

后面的项目依赖前面已经学会的状态管理、工具调度和结果验证。

---

## 十、每个项目的验收报告

在每个项目目录创建 RESULTS.md：

~~~markdown
# 实验结果

## 运行环境
- Windows:
- Python:
- Ollama:
- 模型:

## 测试命令
python main.py

## 测试输入

## 实际输出

## 是否达到预期

## 遇到的问题

## 我是怎么修复的

## 本次真正理解的三个知识点

## 下一步改进
~~~

不要伪造输出。如果模型没有成功运行，就记录失败原因。

---

## 十一、推荐提交信息

~~~text
docs: add agent learning roadmap
docs(task-1): record Agent and ReAct concepts
feat(task-1): implement handwritten react calculator
test(task-1): add calculator error cases
feat(task-1): add safe file reader agent
docs(task-1): record experiments and lessons
feat(task-2): add markdown note retrieval agent
feat(task-2): add local todo tools
feat(task-2): add multi-step file batch agent
feat(task-3): add short-term memory and retry
feat(task-4): add parallel tool execution
feat(task-4): add tool permission confirmation
feat(task-4): add plan and solve workflow
feat(task-4): add handwritten vector retrieval
feat(task-4): add self-reflection loop
~~~

---

## 十二、安全和版权检查

每次提交前执行：

~~~powershell
git status --short
git diff --stat
~~~

确认没有加入：

- API Key、密码、Cookie、Token。
- .env 文件。
- Ollama 模型文件。
- 个人隐私数据和真实业务数据。
- 未确认许可的原书 PDF。
- 大型生成文件和临时日志。

如果密钥已经提交到 GitHub，不能只删除本地文件，必须立即撤销并重新生成密钥。

---

## 十三、最终作品集整理

根目录 README 中加入项目表：

| 项目 | 能力 | 状态 | 演示 |
|---|---|---|---|
| React Calculator | 基础 ReAct | 已完成 | 运行截图 |
| Markdown QA | 本地知识检索 | 进行中 | 示例输出 |
| Todo Agent | 多工具调度 | 未开始 | - |
| RAG Agent | 向量检索 | 未开始 | - |
| Self-Reflection | 自动校验和修正 | 未开始 | - |

准确表述项目定位：

> 这是一个以原生 Python 和 Ollama 为基础、逐步实现 Agent 核心能力的学习与实验项目。

不要包装成生产级系统。

---

## 十四、每次学习结束后的清单

~~~text
[ ] 代码能运行
[ ] 至少有一个成功测试
[ ] 至少有一个失败测试
[ ] 写了 RESULTS.md
[ ] 更新了根目录 README
[ ] 更新了 ROADMAP
[ ] 提交了 Git commit
[ ] 推送到了 GitHub
[ ] 创建或更新了 Pull Request
[ ] 合并后打了版本标签
[ ] 写下下一步计划
~~~

---

## 十五、第一轮实际操作顺序

现在按下面顺序执行，不要一次跳到所有任务：

1. 在 GitHub 创建 agent-learning-lab 空仓库。
2. 整理本地目录并创建 .gitignore。
3. 创建根目录 README.md 和 ROADMAP.md。
4. 完成第一次 commit 并 push 到 GitHub。
5. 创建 Task 1 的 Issue 和分支。
6. 把计算器代码整理成 main.py。
7. 安装并确认 Ollama 模型。
8. 运行计算器 Agent。
9. 修复错误并补充测试。
10. 写 RESULTS.md，提交、推送、创建 PR、合并并打 v0.1-react-basics 标签。
11. 再开始 Task 1 的文件读取 Agent。

完成这十一步后，再继续 Task 2。不要跳过版本控制练习。

