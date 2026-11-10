# AGENT学习第4次任务



## 项目 6：并行工具调用 + 简单工具权限控制 Agent

### 新增知识点

- 并行工具调用：同一个思考轮次，一次性输出多个独立工具任务（无依赖任务并行执行，有依赖串行）
- 工具权限白名单：区分危险工具（删除文件）和安全工具（读取文件），高危操作强制二次确认
- 状态隔离：区分全局状态和单次任务状态

### 学习目标

- 手动实现并行工具调度：无依赖任务 asyncio.gather；有依赖则串行执行
- 工具权限白名单：安全工具直接跑，高危工具暂停，人工二次确认
- 状态隔离：全局状态（权限 / 配置）、单次任务状态（每个任务独立）
- 区分并行 / 串行：多文件读取可并行；读取完成后拿到文本，才能统计字数 / 提取关键词（依赖，下一轮）

```
import asyncio
import httpx
import json
import os
from typing import Dict, List, Any, Optional

# ====================== 1. 状态隔离定义 ======================
# 【全局状态】多任务共享，程序生命周期内常驻
GLOBAL_STATE = {
    "tool_permission": {
        "read_file": "safe",
        "count_words": "safe",
        "extract_keyword": "safe",
        "delete_file": "danger"
    },
    "workspace": "./workspace",
    "ollama_url": "http://127.0.0.1:11434/api/chat",
    "model_name": "llama3.1"
}

# 【单次任务状态】每个Agent任务独立，任务结束销毁
class TaskState:
    def __init__(self, user_prompt: str):
        self.messages: List[Dict[str, str]] = [{"role": "user", "content": user_prompt}]
        self.file_results: Dict[str, Dict[str, Any]] = {}  # 存储每个文件结果 {filename: {content, word_count, keywords}}
        self.pending_danger_tool: Optional[Dict[str, Any]] = None # 待确认高危工具

# ====================== 2. 工具实现 ======================
def _check_workspace_path(file_path: str) -> str:
    """路径白名单校验，禁止访问workspace之外"""
    full_path = os.path.abspath(os.path.join(GLOBAL_STATE["workspace"], file_path))
    workspace_abs = os.path.abspath(GLOBAL_STATE["workspace"])
    if not full_path.startswith(workspace_abs):
        raise PermissionError(f"禁止访问工作目录外路径：{file_path}")
    return full_path

async def read_file(file_path: str) -> str:
    """安全工具：读取文件"""
    await asyncio.sleep(0.1) # 模拟IO延迟
    try:
        fp = _check_workspace_path(file_path)
        with open(fp, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"read_file error: {str(e)}"

async def count_words(text: str) -> str:
    """安全工具：统计文本字数"""
    await asyncio.sleep(0.05)
    clean = text.replace("\n", "").replace(" ", "")
    return f"字数:{len(clean)}"

async def extract_keyword(text: str) -> str:
    """安全工具：提取最多5个关键词"""
    await asyncio.sleep(0.08)
    words = text.replace("\n", " ").split()
    kw = list(set([w.strip("，。；：,.") for w in words if len(w)>1]))[:5]
    return f"关键词:{kw}"

async def delete_file(file_path: str) -> str:
    """高危工具：真正删除动作放在确认分支"""
    await asyncio.sleep(0.05)
    fp = _check_workspace_path(file_path)
    os.remove(fp)
    return f"成功删除文件: {file_path}"

# 工具映射表
TOOL_MAP = {
    "read_file": read_file,
    "count_words": count_words,
    "extract_keyword": extract_keyword,
    "delete_file": delete_file
}

TOOL_SCHEMA_PROMPT = """
你是文件分析Agent。你可以调用下面工具，**一轮思考可以输出多个无依赖工具调用（数组形式）**
工具列表：
1. read_file(file_path:str):读取workspace下文本文件，安全工具
2. count_words(text:str):统计文本字数，安全工具
3. extract_keyword(text:str):提取5个关键词，安全工具
4. delete_file(file_path:str):删除文件，高危工具

规则：
- 如果多个工具互相没有数据依赖，一次性输出数组，并行执行。例：同时读取doc1.txt、doc2.txt
- 如果工具存在依赖（后面工具需要前面工具返回的文本），不能并行，分多轮调用
- 输出格式严格JSON，只返回{"tools": [{"name":"xxx","args":{}}]}，不要多余解释。
- 不需要工具时，直接写最终报告文本。
"""

# ====================== 3. LLM调用函数（原生HTTP，无框架） ======================
async def llm_think(messages: List[Dict]) -> str:
    payload = {
        "model": GLOBAL_STATE["model_name"],
        "messages": [{"role":"system","content":TOOL_SCHEMA_PROMPT}] + messages,
        "stream": False
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(GLOBAL_STATE["ollama_url"], json=payload)
        data = resp.json()
    return data["message"]["content"]

# ====================== 4. 权限校验模块 ======================
def check_tool_permissions(tool_calls: List[Dict]) -> tuple[List[Dict], Optional[Dict]]:
    """
    输入LLM输出的工具列表
    返回：安全工具列表、待确认高危工具（一次只处理1个高危，简化）
    """
    safe_list = []
    danger_tool = None
    for tc in tool_calls:
        t_name = tc["name"]
        perm = GLOBAL_STATE["tool_permission"][t_name]
        if perm == "safe":
            safe_list.append(tc)
        elif perm == "danger":
            danger_tool = tc
    return safe_list, danger_tool

# ====================== 5. 并行工具调度核心 ======================
async def execute_parallel_tools(tool_calls: List[Dict]) -> List[Dict]:
    """并行执行一组无依赖工具，返回每个工具的name+args+result"""
    tasks = []
    meta = []
    for tc in tool_calls:
        func = TOOL_MAP[tc["name"]]
        task = func(**tc["args"])
        tasks.append(task)
        meta.append(tc)
    # 并行等待全部完成
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)
    output = []
    for tc, res in zip(meta, results_raw):
        if isinstance(res, Exception):
            output.append({"name":tc["name"], "args":tc["args"], "result":f"Exception: {str(res)}"})
        else:
            output.append({"name":tc["name"], "args":tc["args"], "result":res})
    return output

# ====================== 6. Agent主循环 ======================
async def agent_loop(task_state: TaskState):
    max_round = 8 # 限制最大思考轮次，防止死循环
    for _ in range(max_round):
        # step1：LLM思考
        llm_out = await llm_think(task_state.messages)
        # step2：尝试解析工具调用JSON
        try:
            parsed = json.loads(llm_out)
            tool_calls = parsed.get("tools", [])
        except json.JSONDecodeError:
            # 解析失败，说明LLM直接输出最终报告，任务结束
            print("\n===== 最终报告 =====")
            print(llm_out)
            return llm_out

        if not tool_calls:
            print("\n===== 最终报告 =====")
            print(llm_out)
            return llm_out

        # step3：权限校验
        safe_tools, danger_tool = check_tool_permissions(tool_calls)
        # 高危工具处理
        if danger_tool is not None:
            print(f"\n⚠️ 高危操作：{danger_tool['name']}, 参数 {danger_tool['args']}")
            confirm = input("确认执行？输入 yes / no：").strip().lower()
            if confirm == "yes":
                # 执行高危工具
                res = await TOOL_MAP[danger_tool["name"]](**danger_tool["args"])
                task_state.messages.append({"role":"tool", "content":json.dumps({"tool":danger_tool,"result":res}, ensure_ascii=False)})
            else:
                print("已取消高危操作")
                task_state.messages.append({"role":"tool", "content":f"用户拒绝执行工具 {danger_tool}"})
            continue

        # step4：并行执行安全工具
        tool_results = await execute_parallel_tools(safe_tools)
        # step5：把工具结果追加进对话历史，进入下一轮思考
        task_state.messages.append({"role":"tool", "content":json.dumps(tool_results, ensure_ascii=False)})
        # 简单回填file_results（可选，用于报告汇总）
        for item in tool_results:
            if item["name"] == "read_file":
                fname = item["args"]["file_path"]
                task_state.file_results[fname] = {"content": item["result"]}
    print("达到最大思考轮次，终止")
    return None

# ====================== 7. 测试入口 ======================
async def main():
    # 初始化测试文件
    os.makedirs(GLOBAL_STATE["workspace"], exist_ok=True)
    if not os.path.exists("./workspace/doc1.txt"):
        with open("./workspace/doc1.txt","w",encoding="utf-8") as f:
            f.write("Agent可以并行调用多个独立工具，减少执行耗时。并行前提是任务之间不存在数据依赖。")
    if not os.path.exists("./workspace/doc2.txt"):
        with open("./workspace/doc2.txt","w",encoding="utf-8") as f:
            f.write("工具权限控制用来防止大模型误删文件，高危操作必须人工确认，保障系统安全。")

    # 测试1：并行读取两个文件，分析生成报告
    user_input = "读取workspace/doc1.txt 和 workspace/doc2.txt，统计每个文件字数，提取关键词，汇总成完整报告"
    state = TaskState(user_input)
    await agent_loop(state)

    # 测试2：高危删除文件（取消/确认），放开下面注释测试
    # user_input2 = "删除 workspace/doc1.txt"
    # state2 = TaskState(user_input2)
    # await agent_loop(state2)

if __name__ == "__main__":
    asyncio.run(main())

```

## ✅ 项目6 学习要点

### 1. 并行工具调用（核心）

- LLM 一轮思考返回`{"tools": [tool1, tool2]}`数组，多个无依赖工具一次性提交
- `asyncio.gather`实现并行执行；`return_exceptions=True`，单个工具失败不打断其他并行任务
- 依赖关系自动由 LLM 判断：读取文件拿到文本之后，count_words/extract_keyword 需要文本输入 → 放到下一轮思考执行（串行）

> 和第 4 阶段串行 Agent 对比：第 4 阶段一轮只能调用 1 个工具，循环等待返回；本项目一轮可以批量调用多个独立工具。

### 2. 工具权限白名单

`check_tool_permissions`函数拦截工具列表

- safe：read_file /count_words/extract_keyword → 直接并行执行
- danger：delete_file → 剥离出来，暂停 Agent 循环，控制台等待用户`yes/no`确认，确认后才执行删除。 额外增加**路径白名单**：只允许操作`./workspace`，防止越权读取系统文件。

### 3. 状态隔离

- `GLOBAL_STATE`：全局配置，权限表、ollama 地址、工作目录，所有任务共用，程序启动创建，程序退出销毁
- `TaskState`：每个任务独立实例，保存对话消息、本次文件分析结果；每次新建任务创建，任务结束丢弃。多任务并发运行时，多个 TaskState 互不干扰。

## 🧪 测试用例操作指南

1. **并行读取文档**

```
读取workspace/doc1.txt 和 workspace/doc2.txt，统计每个文件字数，提取关键词，汇总成完整报告
```

LLM 输出 2 个 read_file 工具，asyncio 并行读取两个文件；工具结果返回，下一轮思考并行调用 count_words、extract_keyword，生成报告。

1. **高危删除测试**

```
删除 workspace/doc1.txt
```

Agent 识别 delete_file 高危工具，弹出确认，输入 yes 执行删除；输入 no 直接取消操作。

1. **依赖串行场景**

```
读取 doc1.txt，提取关键词，然后删除 doc1.txt
```

执行顺序：读取 doc1（获取文本）→提取关键词（依赖文本）→删除文件（高危确认），分多轮串行。

## 📝 思考题（自测）

1. 当前代码一次只处理 1 个高危工具，如果 LLM 一轮同时返回 delete_file+read_file，逻辑会怎么处理？如何修改支持一轮同时存在安全工具 + 多个高危工具？
2. asyncio.gather 的`return_exceptions=True`容错机制，在生产环境有什么利弊？
3. 现在工具结果全部塞进 message 历史，长文档多次调用会造成上下文膨胀，怎么加缓存优化？

## 可选扩展方向（做完基础版后）

- 增加并发上限：限制同时并行工具数量，避免一次性发起大量 IO 请求
- 增加超时：给每个工具任务增加 asyncio 超时控制
- 工具调用日志记录
- 简单依赖图解析：代码侧增加依赖检查，不完全依赖 LLM 判断是否可以并行



## 项目7：分层规划 Agent（Plan & Solve，脱离基础 ReAct）

### 新增知识点

- 顶层规划器 + 底层执行器（双 Agent 架构，自己手写，无框架）
- 任务拆分：先由规划 Agent 把复杂大任务拆成子任务清单；执行 Agent 逐个执行子任务
- 子任务状态跟踪：记录哪些子任务完成、哪些失败

> 和 ReAct 区别：ReAct 是边想边做；Plan&Solve 是**先整体规划，再分步执行**。适合长任务。

### 项目任务：批量文档处理流水线 Agent

例子：用户指令：把`./notes`文件夹所有 md 文件，读取内容→提取摘要→保存摘要到新文件夹，统计所有文档总字数。 规划 Agent 输出子任务列表；执行 Agent 逐个执行，记录进度，子任务失败可以单独重跑。

```
import asyncio
import httpx
import json
import os
from typing import Dict, List, Any, Optional

# ====================== 1. 全局状态（多任务共享配置） ======================
GLOBAL_STATE = {
    "ollama_url": "http://127.0.0.1:11434/api/chat",
    "model_name": "qwen2.5",
    "workspace": "./notes",
    "summary_output_dir": "./notes_summary",
}

# ====================== 2. 数据结构：子任务定义 & 任务状态跟踪 ======================
class SubTask:
    def __init__(self, task_id: str, description: str):
        self.task_id = task_id
        self.description = description
        self.status = "pending"  # pending / running / success / failed
        self.result: Optional[str] = None
        self.error: Optional[str] = None

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status,
            "result": self.result,
            "error": self.error
        }

# 单次主任务状态（隔离，每个流水线独立）
class PlanSolveTaskState:
    def __init__(self, user_prompt: str):
        self.user_prompt = user_prompt
        self.sub_tasks: List[SubTask] = []  # 规划器输出的子任务列表
        self.plan: Optional[str] = None     # 完整规划文本
        self.global_context: Dict[str, Any] = {} # 保存流水线中间结果（全部文档总字数等）

# ====================== 3. 工具函数（文档处理工具） ======================
def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

async def list_md_files(folder_path: str) -> str:
    """工具：列出文件夹下所有md文件"""
    await asyncio.sleep(0.1)
    if not os.path.exists(folder_path):
        return f"ERROR: 文件夹 {folder_path} 不存在"
    files = [f for f in os.listdir(folder_path) if f.endswith(".md")]
    return json.dumps(files, ensure_ascii=False)

async def read_md(file_path: str) -> str:
    """工具：读取md文件"""
    await asyncio.sleep(0.1)
    full_path = os.path.join(GLOBAL_STATE["workspace"], file_path)
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"ERROR read_md: {str(e)}"

async def generate_summary(text: str) -> str:
    """工具：调用LLM生成简短摘要"""
    await asyncio.sleep(0.2)
    prompt = f"对下面文本生成简短摘要，控制在100字以内：\n{text}"
    payload = {
        "model": GLOBAL_STATE["model_name"],
        "messages": [{"role":"user", "content": prompt}],
        "stream": False
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(GLOBAL_STATE["ollama_url"], json=payload)
        data = resp.json()
    return data["message"]["content"]

async def save_summary(file_name: str, summary_text: str) -> str:
    """工具：将摘要保存到输出目录"""
    await asyncio.sleep(0.1)
    ensure_dir(GLOBAL_STATE["summary_output_dir"])
    out_name = file_name.replace(".md", "_summary.txt")
    out_path = os.path.join(GLOBAL_STATE["summary_output_dir"], out_name)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(summary_text)
        return f"保存成功：{out_path}"
    except Exception as e:
        return f"ERROR save_summary: {str(e)}"

async def count_text_total(text: str) -> str:
    """工具：统计文本字符数"""
    await asyncio.sleep(0.05)
    clean = text.replace("\n", "").replace(" ", "")
    return str(len(clean))

# 工具映射表
TOOL_MAP = {
    "list_md_files": list_md_files,
    "read_md": read_md,
    "generate_summary": generate_summary,
    "save_summary": save_summary,
    "count_text_total": count_text_total,
}

TOOL_DESC = """
可用工具：
1. list_md_files(folder_path):列出目录所有md文件
2. read_md(file_path):读取md文件内容
3. generate_summary(text):生成文本摘要
4. save_summary(file_name, summary_text):保存摘要文件
5. count_text_total(text):统计文本有效字符数量
"""

# ====================== 4. 规划Agent（顶层 Planner：生成子任务清单） ======================
async def planner_agent(user_query: str) -> List[SubTask]:
    """顶层规划器：接收用户原始需求，输出结构化子任务列表"""
    system_prompt = f"""
你是任务规划Agent。不要执行任务，只做任务拆分。
{TOOL_DESC}
规则：
1. 将用户复杂任务拆分成有序子任务，子任务必须有先后依赖关系。
2. 输出严格JSON格式，只返回数组，每个子任务包含 task_id(序号字符串), description。
3. 不要输出多余解释，不要执行工具。
示例输出：
[
{{"task_id":"T1","description":"列出./notes文件夹下所有md文件"}},
{{"task_id":"T2","description":"循环读取每个md文件内容"}}
]
"""
    payload = {
        "model": GLOBAL_STATE["model_name"],
        "messages": [
            {"role":"system", "content": system_prompt},
            {"role":"user", "content": user_query}
        ],
        "stream": False
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(GLOBAL_STATE["ollama_url"], json=payload)
        data = resp.json()
    content = data["message"]["content"]
    try:
        task_list_raw = json.loads(content)
    except json.JSONDecodeError:
        raise RuntimeError(f"规划器输出JSON解析失败：{content}")

    sub_tasks = [SubTask(t["task_id"], t["description"]) for t in task_list_raw]
    return sub_tasks

# ====================== 5. 执行Agent（底层Solver：逐个执行子任务，跟踪状态） ======================
async def solver_agent(sub_task: SubTask, global_context: Dict[str, Any]) -> None:
    """执行Agent：接收单个子任务，理解目标，调用工具执行，回填子任务状态"""
    print(f"\n>>> 开始执行子任务 [{sub_task.task_id}] : {sub_task.description}")
    system_prompt = f"""
你是执行Agent，负责完成单个子任务。{TOOL_DESC}
你可以调用工具，工具返回结果存入全局上下文。
输入：子任务描述 + 当前全局上下文。
输出格式：JSON，二选一：
1. 调用工具：{{"action":"tool_call", "tool_name":"xxx", "args":{{}}}}
2. 任务完成：{{"action":"finish", "result":"任务结果文本"}}
"""
    user_msg = f"""
子任务：{sub_task.description}
当前全局上下文：{json.dumps(global_context, ensure_ascii=False)}
"""
    payload = {
        "model": GLOBAL_STATE["model_name"],
        "messages": [
            {"role":"system", "content": system_prompt},
            {"role":"user", "content": user_msg}
        ],
        "stream": False
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(GLOBAL_STATE["ollama_url"], json=payload)
            data = resp.json()
        llm_out = data["message"]["content"]
        action = json.loads(llm_out)
        sub_task.status = "running"

        if action["action"] == "tool_call":
            tool_func = TOOL_MAP[action["tool_name"]]
            tool_result = await tool_func(**action["args"])
            # 判断是否工具返回错误
            if tool_result.startswith("ERROR"):
                sub_task.status = "failed"
                sub_task.error = tool_result
                sub_task.result = None
            else:
                sub_task.status = "success"
                sub_task.result = tool_result
                # 把结果写入全局上下文，给后续子任务使用
                global_context[sub_task.task_id] = tool_result

        elif action["action"] == "finish":
            sub_task.status = "success"
            sub_task.result = action["result"]
            global_context[sub_task.task_id] = action["result"]

    except Exception as e:
        sub_task.status = "failed"
        sub_task.error = str(e)
        sub_task.result = None
    print(f"<<< 子任务 [{sub_task.task_id}] 状态: {sub_task.status} | result={sub_task.result}")

# ====================== 6. Plan & Solve 主调度器 ======================
async def plan_and_solve_main(user_prompt: str):
    task_state = PlanSolveTaskState(user_prompt)
    print("======= [阶段1] 规划Agent：生成任务清单 =======")
    task_state.sub_tasks = await planner_agent(user_prompt)
    print(f"规划完成，共 {len(task_state.sub_tasks)} 个子任务")
    for t in task_state.sub_tasks:
        print(f" - {t.task_id}: {t.description}")

    print("\n======= [阶段2] 执行Agent：顺序执行子任务 =======")
    # 顺序逐个执行子任务；流水线有依赖，不并行
    for sub_task in task_state.sub_tasks:
        await solver_agent(sub_task, task_state.global_context)
        # 子任务失败，可选：中断整个流水线 OR 继续执行其余任务
        if sub_task.status == "failed":
            print(f"子任务 {sub_task.task_id} 失败，错误信息：{sub_task.error}")
            # 这里可以切换策略：break终止 or continue继续后面任务
            # break

    print("\n======= [阶段3] 流水线全部执行完毕，汇总报告 =======")
    print("子任务状态汇总：")
    for t in task_state.sub_tasks:
        print(f"{t.task_id} | {t.status} | result: {t.result}")
    print(f"全局上下文：{json.dumps(task_state.global_context, ensure_ascii=False, indent=2)}")
    return task_state

# ====================== 7. 测试入口 ======================
async def main():
    # 准备测试目录和md样例文件
    os.makedirs(GLOBAL_STATE["workspace"], exist_ok=True)
    if not os.path.exists("./notes/doc1.md"):
        with open("./notes/doc1.md", "w", encoding="utf-8") as f:
            f.write("Plan & Solve Agent分为规划器和执行器，先整体规划任务清单，再分步执行。适合长任务流水线。")
    if not os.path.exists("./notes/doc2.md"):
        with open("./notes/doc2.md", "w", encoding="utf-8") as f:
            f.write("ReAct是边思考边行动，没有预先完整任务清单。Plan and Solve预先拆分任务，可跟踪每个子任务状态，失败子任务支持单独重试。")

    user_req = "把./notes文件夹所有 md 文件，读取内容→提取摘要→保存摘要到新文件夹，统计所有文档总字数。"
    await plan_and_solve_main(user_req)

if __name__ == "__main__":
    asyncio.run(main())

```

## ✅ 代码对应阶段 7 核心知识点梳理

### 1. 双 Agent 架构：顶层规划器 + 底层执行器

- **规划 Agent（Planner）**：只做任务拆解，**不调用工具、不执行任何操作**，输出有序子任务列表。一次性完成全局规划。
- **执行 Agent（Solver）**：每次只接收**单个子任务**，读取全局上下文，调用工具完成这个子任务；更新子任务状态。

> 和 ReAct 核心差异：ReAct 没有前置完整任务清单，每一轮思考都动态决定下一步动作；Plan & Solve 先一次性生成完整计划，再按计划执行。

### 2. 子任务状态跟踪

`SubTask`对象自带状态：`pending / running / success / failed`，保存 result/error。 流水线执行后可以查看每个子任务的执行结果。支持特性：**失败子任务单独重跑**（只需要把失败 task 状态重置为 pending，重新送入 solver_agent，不需要从头跑全部流水线）。

### 3. 状态隔离

- `GLOBAL_STATE`：全局配置，所有任务共享。
- `PlanSolveTaskState`：单次流水线任务独立状态，保存用户指令、子任务列表、全局中间上下文；多个流水线任务实例互不干扰。

## 🧪 测试用例说明

用户输入：`把./notes文件夹所有 md 文件，读取内容→提取摘要→保存摘要到新文件夹，统计所有文档总字数。` 规划 Agent 自动拆分成类似下面子任务：

1. T1：列出./notes 文件夹下所有 md 文件
2. T2：依次读取每个 md 文档内容
3. T3：对每个文档生成摘要
4. T4：把摘要保存到./notes_summary
5. T5：统计全部文档总字符数
6. T6：汇总输出最终报告

执行 Agent 按顺序逐个执行，每个子任务状态会被记录。如果某个子任务失败，可以单独重试该子任务。

## 📌 自测思考题（检验掌握程度）

1. Plan & Solve 有什么短板？什么场景不适合用 Plan & Solve，更适合 ReAct？
2. 当前代码是顺序执行子任务；如果子任务之间无依赖，如何改造，让无依赖子任务并行执行？
3. 当前规划是一次性生成固定清单，如果执行中途发现环境变化（文件丢失），如何增加**动态重规划**能力？

## 扩展方向（做完基础版）

1. 增加子任务重试机制：子任务失败自动重试 N 次
2. 增加动态重规划：执行过程中如果出现重大意外，调用 Planner 重新生成剩余任务清单
3. 增加子任务依赖图：标记哪些子任务可以并行，哪些必须串行，结合项目6 并行工具能力







## 阶段 8：简易向量检索 Agent（RAG，纯手写，不调用 LlamaIndex/Chroma 框架）（第 8 个项目）

### 新增知识点

- 手写简易向量库：用 numpy 做向量存储、余弦相似度计算（**不使用向量数据库框架**）
- 文本分块、简单文本清洗
- 检索增强：先检索本地文本片段，再把片段塞给 Ollama 做回答

> 0 框架关键点：嵌入模型依旧调用 Ollama 的 embedding 接口；向量、相似度全部 numpy 手写，不引入任何 RAG 框架。

### 项目任务：私有知识库问答 Agent

任务：加载一堆本地文档，文本分块，生成向量；用户提问，先检索最相关片段，再交给大模型回答。

```
import asyncio
import httpx
import json
import os
import re
import numpy as np
from typing import List, Tuple, Dict, Any

# ====================== 全局配置（GLOBAL_STATE） ======================
GLOBAL_STATE = {
    "ollama_base_url": "http://127.0.0.1:11434/api",
    "llm_model": "qwen2.5",
    "embed_model": "nomic-embed-text",
    "chunk_size": 200,        # 单块字符长度
    "chunk_overlap": 30,      # 块重叠字符
    "top_k": 3,               # 检索返回最相关top3片段
}

# ====================== 手写内存向量库 ======================
class SimpleVectorStore:
    def __init__(self):
        self.text_chunks: List[str] = []    # 保存文本块
        self.embeddings: np.ndarray = np.array([]) # 向量矩阵 shape=(num_chunks, dim)

    def add(self, text_chunk: str, embedding: np.ndarray):
        """添加单个文本块+向量"""
        self.text_chunks.append(text_chunk)
        vec = embedding.reshape(1, -1)
        if self.embeddings.size == 0:
            self.embeddings = vec
        else:
            self.embeddings = np.vstack([self.embeddings, vec])

    def cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """手写余弦相似度"""
        dot_product = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def search(self, query_embedding: np.ndarray, top_k: int) -> List[Tuple[float, str]]:
        """检索，返回 [(相似度分数, 文本块)]，按分数降序"""
        scores = []
        for idx in range(self.embeddings.shape[0]):
            score = self.cosine_similarity(query_embedding, self.embeddings[idx])
            scores.append((score, self.text_chunks[idx]))
        # 降序排序，取topK
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[:top_k]

# ====================== 文本预处理模块：清洗 + 滑动窗口分块 ======================
def clean_text(raw: str) -> str:
    """简单文本清洗：去除多余换行、空格"""
    raw = re.sub(r"\n+", "\n", raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()

def split_text(raw_text: str, chunk_size: int, overlap: int) -> List[str]:
    """滑动窗口文本分块"""
    chunks = []
    start = 0
    text_len = len(raw_text)
    while start < text_len:
        end = start + chunk_size
        chunk = raw_text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks

# ====================== Ollama API 封装（嵌入向量 + LLM问答） ======================
async def get_embedding(text: str) -> np.ndarray:
    """调用Ollama embedding接口获取向量"""
    url = f"{GLOBAL_STATE['ollama_base_url']}/embeddings"
    payload = {
        "model": GLOBAL_STATE["embed_model"],
        "prompt": text
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload)
        data = resp.json()
    vec = np.array(data["embedding"], dtype=np.float32)
    return vec

async def llm_answer(question: str, context_chunks: List[str]) -> str:
    """把检索到的上下文和问题一起交给LLM生成答案"""
    context_text = "\n---\n".join(context_chunks)
    system_prompt = """
你是知识库问答助手，只能基于下面【参考上下文】回答用户问题。
如果上下文没有相关信息，直接回答：知识库中没有找到相关信息，不要编造内容。
"""
    user_prompt = f"""
【参考上下文】
{context_text}

【用户问题】
{question}
"""
    url = f"{GLOBAL_STATE['ollama_base_url']}/chat"
    payload = {
        "model": GLOBAL_STATE["llm_model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload)
        data = resp.json()
    return data["message"]["content"]

# ====================== RAG Agent 主类 ======================
class RAGAgent:
    def __init__(self):
        self.vector_store = SimpleVectorStore()

    async def load_document(self, file_path: str):
        """加载单个文档，清洗、分块、生成向量存入向量库"""
        print(f"\n📄 加载文档：{file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
        clean = clean_text(raw)
        chunks = split_text(clean, GLOBAL_STATE["chunk_size"], GLOBAL_STATE["chunk_overlap"])
        print(f"文档分块完成，总块数：{len(chunks)}")
        for idx, chunk in enumerate(chunks):
            emb = await get_embedding(chunk)
            self.vector_store.add(chunk, emb)
            print(f"  块{idx+1}向量入库")

    async def ask(self, question: str) -> str:
        """用户提问：向量化问题 -> 检索topK上下文 -> LLM生成答案"""
        print(f"\n❓ 用户问题：{question}")
        print("🔍 正在检索知识库...")
        q_emb = await get_embedding(question)
        top_results = self.vector_store.search(q_emb, GLOBAL_STATE["top_k"])
        print("✅ 检索结果：")
        ctx_list = []
        for score, text in top_results:
            print(f"相似度={score:.4f} | 片段：{text[:100]}...")
            ctx_list.append(text)
        answer = await llm_answer(question, ctx_list)
        return answer

# ====================== 测试入口 ======================
async def main():
    # 创建知识库目录和测试文档
    kb_dir = "./knowledge_base"
    os.makedirs(kb_dir, exist_ok=True)
    doc1_path = os.path.join(kb_dir, "agent_intro.txt")
    if not os.path.exists(doc1_path):
        with open(doc1_path, "w", encoding="utf-8") as f:
            f.write("""
ReAct Agent：思考+行动循环，边想边做，适合动态探索类任务。
Plan & Solve Agent：先一次性规划完整任务清单，再执行任务，适合固定流水线。
动态重规划Agent：Plan&Solve基础上，执行失败或者环境变化时，可以重新修改剩余任务计划。
RAG检索增强：把私有文档向量化存储，用户提问时检索相关片段，把片段送入大模型，减少幻觉。
""")
    doc2_path = os.path.join(kb_dir, "rag_note.txt")
    if not os.path.exists(doc2_path):
        with open(doc2_path, "w", encoding="utf-8") as f:
            f.write("""
RAG分为两个阶段：索引阶段 和 查询阶段。
索引阶段：文档加载、文本清洗、分块、生成embedding向量，存入向量库。
查询阶段：用户问题向量化，向量库相似度检索，拿到相关上下文，和问题一起提交给大模型。
余弦相似度：用来衡量两个向量在空间中的夹角，越接近1代表语义越接近。
""")

    # 初始化RAG Agent
    agent = RAGAgent()
    # 加载知识库文档
    await agent.load_document(doc1_path)
    await agent.load_document(doc2_path)

    # 问答测试
    ans = await agent.ask("ReAct Agent和Plan&Solve Agent有什么区别？")
    print("\n🤖 最终回答：")
    print(ans)

    ans2 = await agent.ask("RAG包含哪两个阶段？")
    print("\n🤖 最终回答：")
    print(ans2)

if __name__ == "__main__":
    asyncio.run(main())

```

## ✅ 项目 8 知识点对应

1. 手写简易向量库 `SimpleVectorStore`

   - 向量直接存 numpy 数组，内存存储，无外部向量数据库
   - `cosine_similarity` 完全手写实现，不调用任何第三方相似度库
   - 支持添加文本块、向量、topK 检索

2. 文本分块与清洗

   - `clean_text`：去除多余换行、空白字符
   - `split_text`：滑动窗口分块，设置 chunk_size + overlap，避免语义被粗暴截断

3. **Ollama Embedding 接口** 调用 Ollama `/api/embeddings` 接口得到文本向量，仅使用 Ollama 做向量生成，向量管理完全自己写。

4. **完整 RAG 链路**

   > 索引阶段：文档加载 → 清洗 → 分块 → embedding → 存入内存向量库 查询阶段：问题 embedding → 余弦相似度检索 topK 片段 → 上下文拼接送入 LLM → 返回答案

## 🧪 测试操作

1. 拉取嵌入模型：`ollama pull nomic-embed-text`
2. 启动 ollama 服务，运行代码
3. 测试问题：
   - ReAct Agent 和 Plan&Solve Agent 有什么区别？
   - RAG 分为哪两个阶段？

## 📝 自测思考题

1. 当前向量库全部放在内存，程序退出数据丢失；如何增加向量持久化保存（保存到本地 json/npy 文件）？
2. 现在使用滑动窗口固定字符分块；如何改成**基于句子语义分块**？
3. 余弦相似度检索会返回无关文本，如何增加重排（rerank）步骤，进一步提升检索精度？



## 项目 9：基础反思（Self-Reflection）Agent

### 新增知识点

- 自我反思循环：任务执行完成之后，额外增加一轮反思步骤，评估任务结果有没有缺陷
- 结果校验：Agent 自己检查工具输出、回答是否满足用户原始需求，有问题自动修正

### 项目任务：带自检的数据分析 Agent

任务：读取本地 csv，统计数据；执行完成后，反思：计算是否正确、有没有遗漏需求，发现问题自动重新调用工具修正。

------

> 核心知识点：
>
> 1. **Self-Reflection 自我反思循环**：完成一轮任务执行之后，单独调用 LLM 做反思，评估输出结果是否满足原始用户需求
> 2. 结果自检：LLM 作为评审者，检查：计算是否正确、需求是否遗漏、结果是否有错误
> 3. 自动修正：反思发现缺陷 → 重新调用工具执行修正，直到通过自检，或达到最大反思轮次 0 框架：纯原生 Python + asyncio + Ollama HTTP 接口，无 LangChain/LangGraph 等任何 Agent 框架 项目场景：本地 CSV 数据分析 Agent，读取 csv，做统计计算，执行完成后自我反思校验，有错自动重算

## 

```
import asyncio
import httpx
import json
import os
import csv
from typing import Dict, List, Any, Optional

# ====================== 全局配置 GLOBAL_STATE ======================
GLOBAL_STATE = {
    "ollama_url": "http://127.0.0.1:11434/api/chat",
    "model_name": "qwen2.5",
    "max_reflect_round": 3,  # 最大反思修正轮次，防止无限循环
}

# ====================== 单次任务状态（隔离） ======================
class TaskState:
    def __init__(self, user_prompt: str):
        self.user_prompt = user_prompt
        self.raw_data: List[Dict[str, Any]] = []    # 加载的csv数据
        self.execution_result: Optional[str] = None # 执行工具得到的结果
        self.reflection: Optional[str] = None       # 反思评语
        self.need_fix: bool = False                 # 是否需要修正
        self.reflect_round: int = 0                 # 当前反思轮数

# ====================== 工具集合：CSV数据分析工具 ======================
async def load_csv(file_path: str) -> str:
    """工具：读取csv文件，返回json序列化后的行数据"""
    await asyncio.sleep(0.1)
    rows = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)
        return json.dumps(rows, ensure_ascii=False)
    except Exception as e:
        return f"ERROR load_csv: {str(e)}"

async def calc_sum(data_json: str, col_name: str) -> str:
    """工具：对指定列求和"""
    await asyncio.sleep(0.05)
    data = json.loads(data_json)
    total = 0.0
    for row in data:
        try:
            val = float(row[col_name])
            total += val
        except:
            pass
    return f"列[{col_name}]总和 = {total:.2f}"

async def calc_avg(data_json: str, col_name: str) -> str:
    """工具：对指定列求平均值"""
    await asyncio.sleep(0.05)
    data = json.loads(data_json)
    values = []
    for row in data:
        try:
            val = float(row[col_name])
            values.append(val)
        except:
            pass
    if len(values) == 0:
        return f"列[{col_name}]平均值：无有效数据"
    avg = sum(values)/len(values)
    return f"列[{col_name}]平均值 = {avg:.2f}"

async def count_rows(data_json: str) -> str:
    """工具：统计总行数"""
    await asyncio.sleep(0.05)
    data = json.loads(data_json)
    return f"总行数：{len(data)}"

TOOL_MAP = {
    "load_csv": load_csv,
    "calc_sum": calc_sum,
    "calc_avg": calc_avg,
    "count_rows": count_rows
}

TOOL_DESC = """
可用工具：
1. load_csv(file_path):读取csv文件，返回json行数据
2. calc_sum(data_json, col_name):指定列求和
3. calc_avg(data_json, col_name):指定列求平均值
4. count_rows(data_json):统计数据总行数
输出格式二选一：
  调用工具：{"action":"tool_call","tool_name":"xxx","args":{}}
  任务完成：{"action":"finish","result":"结果文本"}
"""

# ====================== 执行Agent：执行数据分析任务 ======================
async def execution_agent(user_prompt: str, context: Dict[str, Any]) -> str:
    """执行Agent：理解需求，调用工具，输出数据分析结果"""
    system_prompt = f"""
你是数据分析执行Agent。{TOOL_DESC}
根据用户需求，调用工具完成计算；上下文存放已获取的数据。
输出严格JSON，只允许 tool_call / finish 两种动作。
"""
    msg = f"""用户需求：{user_prompt}
当前上下文：{json.dumps(context, ensure_ascii=False)}"""
    payload = {
        "model": GLOBAL_STATE["model_name"],
        "messages": [{"role":"system","content":system_prompt}, {"role":"user","content":msg}],
        "stream": False
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(GLOBAL_STATE["ollama_url"], json=payload)
    llm_out = resp.json()["message"]["content"]
    action = json.loads(llm_out)

    if action["action"] == "tool_call":
        func = TOOL_MAP[action["tool_name"]]
        res = await func(**action["args"])
        # 工具结果存入上下文
        context[action["tool_name"]] = res
        return res
    elif action["action"] == "finish":
        return action["result"]
    return "执行无结果"

# ====================== 反思Agent Self-Reflection（新增核心模块） ======================
async def reflection_agent(user_prompt: str, exec_result: str, context: Dict[str, Any]) -> tuple[str, bool]:
    """
    反思Agent：评审执行结果
    输入：原始用户需求、执行得到的结果、中间上下文
    返回：反思文本，是否需要修正（True=需要重新执行）
    """
    system_prompt = """
你是结果评审反思Agent。你的工作：检查数据分析结果是否满足用户原始需求。
评审维度：
1. 是否完整满足用户全部要求，有没有遗漏需求
2. 计算逻辑是否合理，结果是否存在明显错误
3. 数据是否缺失，有没有异常
输出JSON格式：{"reflection":"反思评语","need_fix":true/false}
只输出JSON，不要多余文字。
need_fix=true：发现缺陷，需要重新执行修正；false：结果合格，可以交付。
"""
    user_msg = f"""
【用户原始需求】
{user_prompt}
【执行Agent输出结果】
{exec_result}
【中间上下文】
{json.dumps(context, ensure_ascii=False)}
"""
    payload = {
        "model": GLOBAL_STATE["model_name"],
        "messages": [{"role":"system","content":system_prompt}, {"role":"user","content":user_msg}],
        "stream": False
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(GLOBAL_STATE["ollama_url"], json=payload)
    llm_out = resp.json()["message"]["content"]
    data = json.loads(llm_out)
    return data["reflection"], data["need_fix"]

# ====================== Self-Reflection 主调度循环 ======================
async def self_reflection_main(user_prompt: str):
    task_state = TaskState(user_prompt)
    context: Dict[str, Any] = {}

    print("====== 开始执行数据分析任务 ======")
    while True:
        # 1. 执行阶段
        task_state.execution_result = await execution_agent(user_prompt, context)
        print(f"\n✅ 本次执行结果：{task_state.execution_result}")

        # 2. 反思自检阶段
        print("\n🔍 启动Self-Reflection反思评审...")
        task_state.reflection, task_state.need_fix = await reflection_agent(
            user_prompt, task_state.execution_result, context
        )
        print(f"📝 反思报告：{task_state.reflection}")
        print(f"🔧 是否需要修正：{task_state.need_fix}")

        task_state.reflect_round +=1
        # 终止条件：不需要修正 OR 达到最大反思轮次
        if not task_state.need_fix or task_state.reflect_round >= GLOBAL_STATE["max_reflect_round"]:
            if task_state.reflect_round >= GLOBAL_STATE["max_reflect_round"] and task_state.need_fix:
                print(f"\n⚠️ 达到最大反思轮次 {GLOBAL_STATE['max_reflect_round']}，停止修正！")
            break
        print(f"\n🔄 发现问题，重新执行任务进行修正，当前反思轮次：{task_state.reflect_round}")

    print("\n======= 任务最终交付结果 =======")
    print(task_state.execution_result)
    return task_state

# ====================== 测试入口 & 准备测试CSV ======================
async def main():
    # 准备测试csv
    csv_path = "./sales_data.csv"
    if not os.path.exists(csv_path):
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["产品","销量","单价"])
            writer.writerow(["A产品","100","20"])
            writer.writerow(["B产品","200","30"])
            writer.writerow(["C产品","150","25"])
    # 用户需求示例：统计总销量、销量平均值、总行数
    user_req = "读取sales_data.csv，计算销量列总和，销量平均值，并且统计一共有多少行数据。"
    await self_reflection_main(user_req)

if __name__ == "__main__":
    asyncio.run(main())
```

## ✅ 项目 9 核心知识点对照

### 1. Self-Reflection 自我反思双阶段

- **执行阶段**：执行 Agent 调用工具完成数据分析，输出结果
- **反思阶段**：独立的反思 Agent，把「原始需求 + 执行结果 + 上下文」一起送入 LLM 评审 反思 Agent 独立于执行 Agent，相当于 Agent 内置的评审官。

> 流程：执行 → 反思评估 → 有缺陷 → 重新执行；合格 → 输出最终答案。

### 2. 结果校验

反思 Agent 从 3 个维度自检：

1. 是否遗漏用户需求
2. 计算结果是否明显错误
3. 数据是否缺失

### 3. 自动修正机制

反思返回`need_fix=True`，自动回到执行环节重新跑；增加`max_reflect_round`上限，防止死循环无限修正。

### 4. 状态隔离

- `GLOBAL_STATE`：全局配置，多任务共享
- `TaskState`：单次任务独立状态，保存 prompt、执行结果、反思记录、反思轮数

## 🧪 测试玩法

1. 正常需求：`读取sales_data.csv，计算销量列总和，销量平均值，并且统计一共有多少行数据。` 执行一次，反思判断结果完整，直接交付。
2. 制造缺陷场景（修改用户需求） 用户需求改为：`读取sales_data.csv，计算销量总和、销量平均值，统计总行数，还要计算单价总和。` 如果执行 Agent 漏掉单价总和，反思 Agent 会识别需求遗漏，返回`need_fix=true`，自动重新执行补齐计算。

## 📝 自测思考题

1. 当前反思是**任务整体完成后**才评审；如何改成**每一步工具调用之后都做局部反思**？
2. 现在反思 Agent 只返回布尔标记 + 评语；如何把反思结论直接反馈给执行 Agent，指导它针对性修正，而不是完整重跑全部流程？
3. 反思很容易出现 “自我美化幻觉”，自己看不出错误；有什么办法降低反思幻觉？