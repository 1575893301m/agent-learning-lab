# AGENT学习第3次

## 任务1：带短期记忆 + 错误重试的Agent

目标：本地文档整理Agent  

新增能力：  

- 维护对话短期记忆（Thought/Action/Observation全链路记录）
- 模型输出JSON格式错误自动重试 
- 捕获工具执行异常，把错误作为观察值回传给LLM，自动重试 

*工具： list_dir (列出目录文件)、 read_file (读取文本文件)* 

*依赖：仅安装 requests ，ollama本地模型*

```
import requests
import json
import os

# ===================== 配置区 =====================
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:7b"  # 换成你本地ollama模型
MAX_RETRY = 3  # LLM输出格式错误最大重试次数
# ==================================================

# ---------------------- 工具定义（纯函数） ----------------------
def list_dir(folder_path: str) -> str:
    """列出文件夹下txt/md文件，工具"""
    try:
        if not os.path.exists(folder_path):
            return f"【错误】路径不存在：{folder_path}"
        files = []
        for f in os.listdir(folder_path):
            if f.endswith((".txt", ".md")):
                files.append(f)
        return f"目录 {folder_path} 内文本文件：{files}"
    except Exception as e:
        return f"【工具异常】list_dir执行失败: {str(e)}"

def read_file(file_path: str) -> str:
    """读取单个文本文件，返回摘要（只取前300字符，避免超长）"""
    try:
        if not os.path.exists(file_path):
            return f"【错误】文件不存在：{file_path}"
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        summary = content[:300]
        return f"文件{file_path}片段内容：\n{summary}"
    except Exception as e:
        return f"【工具异常】read_file执行失败: {str(e)}"

# 工具注册表：名字映射函数 + 参数说明
TOOL_REGISTRY = {
    "list_dir": {
        "func": list_dir,
        "desc": "列出文件夹下txt/md文件，参数：folder_path 字符串"
    },
    "read_file": {
        "func": read_file,
        "desc": "读取文本文件，返回内容摘要，参数：file_path 字符串"
    }
}

# ---------------------- LLM调用函数 ----------------------
def call_ollama(prompt: str) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    resp = requests.post(OLLAMA_URL, json=payload)
    return resp.json()["response"]

# ---------------------- JSON解析 + 重试包装 ----------------------
def parse_llm_output(raw_text: str) -> dict | None:
    """尝试解析LLM输出的JSON，失败返回None"""
    try:
        # 简单清理：提取```json ... ```代码块
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0]
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        return None

# ---------------------- ReAct Agent主类（带记忆+重试） ----------------------
class DocumentAgent:
    def __init__(self):
        # 短期记忆：保存完整历史 [{"thought":..., "action":..., "observation":...}]
        self.memory = []

    def build_prompt(self, user_query: str) -> str:
        """构造prompt，把历史记忆全部塞进去，实现上下文记忆"""
        tool_desc = "\n".join([f"{k}:{v['desc']}" for k, v in TOOL_REGISTRY.items()])
        memory_text = ""
        # 把之前每一轮的思考、动作、观察拼入prompt
        for turn in self.memory:
            memory_text += f"""
Thought: {turn["thought"]}
Action: {json.dumps(turn["action"])}
Observation: {turn["observation"]}
"""
        system_prompt = f"""
你是ReAct Agent。你可以使用下面工具：
{tool_desc}

输出规则：
必须输出JSON，只能包含三个key：thought, action。
- thought：你的思考，分析用户需求，决定下一步动作
- action：{{"name":"工具名","args":{{参数}}}}，不需要工具就name="finish"，args写结果

禁止额外文字，只输出JSON！

历史对话：
{memory_text}

用户当前请求：{user_query}
"""
        return system_prompt

    def run(self, user_query: str):
        print(f"\n==== 用户请求：{user_query} ====")
        for retry_round in range(MAX_RETRY):
            prompt = self.build_prompt(user_query)
            llm_raw = call_ollama(prompt)
            parsed = parse_llm_output(llm_raw)

            if parsed is None:
                print(f">>> LLM输出格式错误，重试 {retry_round+1}/{MAX_RETRY}")
                continue
            # 拿到思考和动作
            thought = parsed.get("thought", "")
            action = parsed.get("action", {})
            tool_name = action.get("name")
            tool_args = action.get("args", {})

            print(f"Thought: {thought}")
            print(f"Action: {json.dumps(action)}")

            # 任务完成，结束Agent
            if tool_name == "finish":
                final_result = tool_args.get("result")
                print(f"\n✅任务完成：{final_result}")
                self.memory.append({
                    "thought": thought,
                    "action": action,
                    "observation": f"任务结束，结果：{final_result}"
                })
                return

            # 执行工具
            if tool_name in TOOL_REGISTRY:
                tool_func = TOOL_REGISTRY[tool_name]["func"]
                obs = tool_func(**tool_args)
                print(f"Observation: {obs}")
                # 存入记忆，下一轮思考会读取这个observation
                self.memory.append({
                    "thought": thought,
                    "action": action,
                    "observation": obs
                })
                # 递归继续下一轮ReAct循环
                return self.run(user_query)
            else:
                obs = f"【错误】不存在这个工具：{tool_name}"
                print(f"Observation: {obs}")
                self.memory.append({
                    "thought": thought,
                    "action": action,
                    "observation": obs
                })
                return self.run(user_query)
        print("❌ 达到最大重试次数，任务失败")

if __name__ == "__main__":
    agent = DocumentAgent()
    # 测试样例1：读取目录，看文件
    agent.run("列出当前目录下所有md和txt文件")
    # 测试样例2：接着提问，测试记忆（会记住上一轮目录结果）
    agent.run("读取其中第一个文件，给我摘要")

```



## 核心要点说明（学习目标）

1. **短期记忆**：`self.memory`列表，每一轮 Thought/Action/Observation 全部保存，每次构造 prompt 都带上历史，模型能记住本轮对话前面信息。
2. **LLM 输出重试**：`parse_llm_output`捕获 JSON 解析失败，最多重试 3 次，解决模型乱输出、markdown 多余文字的问题。
3. **工具异常捕获**：工具函数内部捕获文件不存在、IO 异常，把异常文本包装成`Observation`传回 LLM，Agent 能感知错误并自动调整下一步动作。
4. **0 框架**：没有任何 Agent/RAG 框架，ReAct 循环、记忆管理、工具调度全部手写。

## 测试玩法

1. 正常流程：先列出目录，再读取文件，**连续两轮对话，Agent 能记住前面查到的文件名（记忆生效）**
2. 错误测试：让它读取一个不存在的文件名，工具返回错误，LLM 会收到错误观察，尝试修正。
3. 破坏测试：故意让模型输出非 JSON，代码自动重试。

## 可选改造点（深入练习）

- 限制记忆长度：防止上下文无限膨胀，只保留最近 N 轮记录（滑动窗口记忆）
- 增加日志输出，把每一轮内容保存到本地日志文件
- 新增更多工具，比如统计文件行数
