# AGENT学习第2次

## 任务1：本地MD文档问答 Agent

- 在计算器里的 ReAct 推理循环基础上，自定义两个工具：一个遍历读取本地 md 文件，一个做简单文本相似度检索，让大模型先判断要不要查文件、查哪篇、再提炼答案
- 巩固 ReAct 的思考 - 行动 - 观察闭环，实现 Agent 对私有数据的访问

```
import os
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 配置
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen:7b"
NOTES_FOLDER = "./notes"

# 工具1：扫描本地md笔记
def load_notes(folder_path):
    notes = []
    os.makedirs(folder_path, exist_ok=True)
    for filename in os.listdir(folder_path):
        if filename.endswith(".md"):
            with open(os.path.join(folder_path, filename), "r", encoding="utf-8") as f:
                content = f.read()
                notes.append({"filename": filename, "content": content})
    return notes

# 工具2：检索相关笔记片段
def search_relevant_notes(question, notes):
    if not notes:
        return "未找到任何笔记文件"
    corpus = [note["content"] for note in notes]
    corpus.append(question)
    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform(corpus)
    similarity = cosine_similarity(tfidf[-1], tfidf[:-1])[0]
    top_idx = similarity.argmax()
    return notes[top_idx]["content"] if similarity[top_idx] > 0.2 else "未找到相关笔记内容"

# 封装Ollama调用
def ollama_chat(messages):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False
    }
    resp = requests.post(OLLAMA_API_URL, json=payload).json()
    return resp["message"]["content"]

# ReAct核心循环
def react_agent(question):
    notes = load_notes(NOTES_FOLDER)
    system_prompt = """你是本地笔记问答Agent，严格遵循ReAct流程：
1. 先判断问题是否需要查询本地笔记内容
2. 需要查询就只输出 行动: search_notes
3. 拿到观察结果后，只基于笔记内容回答，不要编造信息"""
    
    # 思考步
    thought = ollama_chat([
        {"role":"system","content":system_prompt},
        {"role":"user","content":question}
    ])
    
    # 行动+观察步
    if "行动: search_notes" in thought:
        observation = search_relevant_notes(question, notes)
        final_ans = ollama_chat([
            {"role":"system","content":system_prompt},
            {"role":"user","content":f"问题：{question}\n观察：{observation}\n请给出答案"}
        ])
        return final_ans
    return thought

# 测试运行
if __name__ == "__main__":
    # 自动生成测试笔记
    test_note_path = os.path.join(NOTES_FOLDER, "learn_log.md")
    with open(test_note_path, "w", encoding="utf-8") as f:
        f.write("学习记录：从零做Agent，第一个项目是ReAct计算器，第二个是本地Markdown笔记问答，用Ollama跑本地大模型。")
    # 提问
    test_question = "我第二个Agent项目是什么"
    print(react_agent(test_question))

```

## 任务2：带多工具调度的本地待办管理 Agent

- 新增增删查改待办的 4 个本地工具，让 ReAct 循环学会判断 “该调用哪个工具、传什么参数”，比如用户说 “帮我记明天下午 3 点学 Agent”，模型要先思考选 add_todo 工具，再传时间和内容参数，拿到执行结果再反馈
- 把单工具检索升级成多工具决策，从 “读文件” 到 “能做事” 

```
import os
import json
import requests
from datetime import datetime

# 配置
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen:7b"
TODO_FILE = "./todos.json"

# 初始化待办存储
if not os.path.exists(TODO_FILE):
    with open(TODO_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

# 待办工具集
def load_todos():
    with open(TODO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_todos(todos):
    with open(TODO_FILE, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)

def add_todo(content, time):
    todos = load_todos()
    new_todo = {"id": len(todos)+1, "content": content, "time": time, "done": False}
    todos.append(new_todo)
    save_todos(todos)
    return f"已新增待办：{content}，时间{time}"

def list_todos():
    todos = load_todos()
    if not todos:
        return "暂无待办"
    return "\n".join([f"{t['id']}. {t['content']} 时间{t['time']} 完成：{t['done']}" for t in todos])

def done_todo(todo_id):
    todos = load_todos()
    for t in todos:
        if t["id"] == int(todo_id):
            t["done"] = True
            save_todos(todos)
            return f"已标记待办{todo_id}为完成"
    return "未找到该待办"

# Ollama调用封装
def ollama_chat(messages):
    payload = {"model": OLLAMA_MODEL, "messages": messages, "stream": False}
    resp = requests.post(OLLAMA_API_URL, json=payload).json()
    return resp["message"]["content"]

# ReAct多工具调度核心
def react_todo_agent(user_input):
    system_prompt = """你是本地待办Agent，严格按ReAct执行：
1. 先判断用户意图，可选工具：add_todo(内容,时间)、list_todos()、done_todo(编号)
2. 决定用哪个工具后，输出格式固定为 行动:工具名(参数)，比如 行动:add_todo(学Agent,2026-09-28 15:00)
3. 拿到工具返回的观察结果后，用自然语言告诉用户结果，不要编造"""
    
    # 思考步
    thought = ollama_chat([
        {"role":"system","content":system_prompt},
        {"role":"user","content":user_input}
    ])
    
    # 行动分发
    if "行动:add_todo" in thought:
        # 解析参数
        param_str = thought.split("行动:add_todo(")[-1].rstrip(")")
        content, time = param_str.split(",")
        obs = add_todo(content.strip(), time.strip())
    elif "行动:list_todos" in thought:
        obs = list_todos()
    elif "行动:done_todo" in thought:
        todo_id = thought.split("行动:done_todo(")[-1].rstrip(")")
        obs = done_todo(todo_id)
    else:
        return thought
    
    # 基于观察生成最终回复
    final_resp = ollama_chat([
        {"role":"system","content":system_prompt},
        {"role":"user","content":f"用户输入：{user_input}\n工具执行结果：{obs}\n请回复用户"}
    ])
    return final_resp

# 测试
if __name__ == "__main__":
    print("测试新增待办：", react_todo_agent("帮我记明天下午3点学多工具Agent"))
    print("测试查看待办：", react_todo_agent("看看我有哪些待办"))

```

## 任务3：本地多步骤推理的文件批处理 Agent

- 在多工具调度基础上，核心练 ReAct 的 “多轮思考 - 多步行动”，比如你说 “把 notes 文件夹里所有 md 笔记里带‘Agent’的段落摘出来，整理成一个新的学习总结 md”，模型要先拆成三步：先扫描所有笔记、再逐篇检索目标段落、最后生成并写入新文件，中间会自己做多次思考和工具调用，不再是单步决策
- 在单工具、多工具基础上，了解 Agent “拆解复杂任务并串行执行” 的核心能力



### 多步骤文件批处理 Agent（基于 Ollama + Python）

```
import os
import shutil
import ollama
from typing import List, Dict

# ====================== 配置区 ======================
MODEL_NAME = "qwen2.5:7b"          # ollama模型名
WORK_DIR = "./agent_workspace"     # Agent工作目录，操作文件都在这里
MAX_STEP = 6                       # 最多允许执行几步，防止死循环
# ====================================================

# 工具函数：Agent可以调用的文件操作工具
def list_files(folder: str) -> List[str]:
    """列出目录下所有文件（不含子文件夹递归）"""
    if not os.path.exists(folder):
        return ["目录不存在"]
    return os.listdir(folder)

def move_file(src: str, dst: str) -> str:
    """移动文件，src源路径，dst目标路径"""
    try:
        shutil.move(src, dst)
        return f"成功：{src} -> {dst}"
    except Exception as e:
        return f"失败：{str(e)}"

def rename_file(old_path: str, new_name: str) -> str:
    """重命名文件"""
    try:
        dirname = os.path.dirname(old_path)
        new_path = os.path.join(dirname, new_name)
        os.rename(old_path, new_path)
        return f"重命名成功：{old_path} -> {new_path}"
    except Exception as e:
        return f"失败：{str(e)}"

def get_file_info(filepath: str) -> str:
    """获取文件大小"""
    if not os.path.isfile(filepath):
        return "不是有效文件"
    size = os.path.getsize(filepath)
    return f"文件大小：{size} bytes"

# 工具注册表：把函数交给大模型，让模型知道可用工具
TOOLS_DESC = """
可用工具：
1. list_files(folder): 返回文件夹内文件列表
2. move_file(src, dst): 移动文件
3. rename_file(old_path, new_name): 重命名文件
4. get_file_info(filepath): 获取文件大小

输出格式要求：
思考：你现在需要做什么
动作：工具名(参数)
完成：任务是否结束，true/false
"""

def call_tool(action_str: str) -> str:
    """解析模型输出的动作字符串，调用对应工具"""
    try:
        # 简单解析，生产环境建议用json格式
        if action_str.startswith("list_files"):
            path = action_str.split("(")[1].split(")")[0].strip('"')
            res = list_files(path)
        elif action_str.startswith("move_file"):
            args = action_str.split("(")[1].split(")")[0].split(",")
            src = args[0].strip('" ')
            dst = args[1].strip('" ')
            res = move_file(src, dst)
        elif action_str.startswith("rename_file"):
            args = action_str.split("(")[1].split(")")[0].split(",")
            old = args[0].strip('" ')
            new = args[1].strip('" ')
            res = rename_file(old, new)
        elif action_str.startswith("get_file_info"):
            path = action_str.split("(")[1].split(")")[0].strip('"')
            res = get_file_info(path)
        else:
            res = "无法识别的动作"
        return f"工具返回结果：{res}"
    except Exception as e:
        return f"调用工具解析异常：{str(e)}"


def file_batch_agent(user_task: str):
    """
    Agent主循环：ReAct 多步骤循环
    user_task: 用户下达的文件批处理任务
    """
    print(f"===== Agent启动，任务：{user_task} =====\n")
    history = []  # 保存对话历史，给模型上下文

    for step_idx in range(MAX_STEP):
        print(f"\n---------- 第 {step_idx+1} 轮思考 ----------")
        # 拼接提示词
        prompt = f"""
{TOOLS_DESC}
历史记录：{history}
用户任务：{user_task}
当前工作目录：{WORK_DIR}

你需要一步步完成任务。严格按下面格式输出，不要多余文字：
思考：xxx
动作：xxx()
完成：true / false
"""
        # 请求Ollama大模型
        resp = ollama.generate(model=MODEL_NAME, prompt=prompt)
        llm_out = resp["response"].strip()
        print(f"模型输出：\n{llm_out}")

        # 解析模型输出三行：思考、动作、完成标记
        lines = llm_out.splitlines()
        think = ""
        action = ""
        done_flag = "false"
        for line in lines:
            if line.startswith("思考："):
                think = line.replace("思考：", "")
            elif line.startswith("动作："):
                action = line.replace("动作：", "")
            elif line.startswith("完成："):
                done_flag = line.replace("完成：", "").strip().lower()

        # 执行工具动作
        tool_result = call_tool(action)
        print(f"工具执行结果：{tool_result}")

        # 把本轮思考+动作+结果存入历史，下一轮模型能看到
        history.append({
            "think": think,
            "action": action,
            "result": tool_result
        })

        # 判断任务结束
        if done_flag == "true":
            print("\n===== Agent 判断任务完成，退出循环 =====")
            return

    print("\n===== 达到最大步骤限制，强制结束 =====")


if __name__ == "__main__":
    # 先创建工作目录
    os.makedirs(WORK_DIR, exist_ok=True)

    # 示例任务，你可以修改这里
    task = f"列出{WORK_DIR}下所有文件，查看第一个文件大小"
    file_batch_agent(task)

```

### 小结

四个零框架、本地 Ollama 示例学习效果：

- 第一个 ReAct 计算器，特征是无外部工具、单步纯推理，只练思考 - 行动 - 观察的基础闭环，不碰外部数据
- 第二个本地笔记问答 Agent，加了单检索工具、单次行动调用，第一次让 Agent 读取本地私有文件，把推理和外部信息结合
- 第三个多工具待办管理 Agent，支持多工具调度、单步选工具传参，学会根据用户意图挑工具、带参数执行
- 第四个是多步骤文件批处理 Agent，核心是多轮思考、多步串行行动，能把复杂任务拆成多步工具调用，完成跨步骤的连贯任务
