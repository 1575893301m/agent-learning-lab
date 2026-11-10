# AGENT学习第1次

任务1：学习李博杰的《深入理解AGENT》

任务2：安装Ollama模型

任务3：实战Ollama+react Agent----手写原生：计算器（要求尽可能完全手写，并搞懂每一句，对其中的参数也要很清楚）

```
#---手写原生：计算器，react Agent
import ollama
import re

# ========== 工具集 ==========
def calculator(a, b, op):
    if op == "+": return a + b
    if op == "-": return a - b
    if op == "*": return a * b
    if op == "/": return a / b
    return None

# 工具映射
tools = {
    "calculator": calculator
}

# ReAct系统提示词（固定格式）
system_prompt = """
你是ReAct智能体，必须严格输出下面格式，不要多余文字：
Thought: 你的思考，判断是否需要调用工具
Action: 工具名|参数1|参数2|运算符
Observation: 工具返回结果（这一行由程序填充，你不要输出）
当已经拿到足够答案，输出：Final Answer: xxx

可用工具：
calculator(a,b,op): 计算，op只能 + - * /
"""

def react_agent(user_query, max_step=5):
    messages = [{"role":"system", "content":system_prompt}, {"role":"user", "content":user_query}]
    for step in range(max_step):
        resp = ollama.chat(model="qwen:7b", messages=messages, stream=False)
        content = resp["message"]["content"]
        print(f"\n---Step {step+1}---\n{content}")

        # 判断是否结束
        if "Final Answer:" in content:
            return content.split("Final Answer:")[-1].strip()
        
        # 解析Action
        match = re.search(r"Action:\s*(\w+)\|(.*)", content)
        if not match:
            messages.append({"role":"assistant", "content":content})
            messages.append({"role":"user", "Observation: 工具调用格式错误"})
            continue
        
        tool_name, args_str = match.groups()
        args = args_str.split("|")
        fn = tools.get(tool_name)
        if fn is None:
            obs = "工具不存在"
        else:
            res = fn(float(args[0]), float(args[1]), args[2])
            obs = str(res)
        # 把Observation塞回上下文
        messages.append({"role":"assistant", "content":content})
        messages.append({"role":"user", "content":f"Observation: {obs}"})
    return "超过最大步骤"

if __name__ == "__main__":
    ans = react_agent("1234乘以456等于多少？")
    print("\n====最终结果====\n", ans)
```



**ReAct = Reasoning（推理）+ Acting（行动）**

```
# -*- coding: utf-8 -*-
"""
react_calculator_annotated.py
手写原生 ReAct Agent：计算器工具版（带详细中文注释版）
——本文件在原程序基础上：1) 修复了一处语法错误；2) 加了详细注释；3) 加了少量健壮性保险。

依赖：需要 pip install ollama（官方 Python SDK，只是一个“API 客户端”，
不是 LangChain 那种 agent 框架，所以仍属于“0 框架”路线）。
"""

import ollama   # Ollama 官方 Python 客户端，用来和本地大模型对话
import re       # 正则表达式，用来从模型输出里“解析”出 Action 指令

# ========== 工具集：Agent 的“手”（能实际执行动作的部分）==========
def calculator(a, b, op):
    """最简单的计算器工具：两个数 + 一个运算符。"""
    if op == "+": return a + b
    if op == "-": return a - b
    if op == "*": return a * b
    if op == "/": return a / b
    return None  # 不支持的运算符

# 工具映射表：工具名 -> 对应函数（模型只输出名字，程序按名字来找真身）
tools = {
    "calculator": calculator,
}

# ========== ReAct 系统提示词：定义模型的“行为协议” ==========
# 关键点：要求模型严格输出固定文本格式，程序用正则去解析。
# 这种“用文本格式代替原生 function calling”的方式，
# 好处是几乎任何模型都能用，坏处是解析脆弱、容易出错。
system_prompt = """
你是ReAct智能体，必须严格输出下面格式，不要多余文字：
Thought: 你的思考，判断是否需要调用工具
Action: 工具名|参数1|参数2|运算符
Observation: 工具返回结果（这一行由程序填充，你不要输出）
当已经拿到足够答案，输出：Final Answer: xxx

可用工具：
calculator(a,b,op): 计算，op只能 + - * /
"""


def react_agent(user_query, max_step=5):
    # Agent 的“短期记忆”：消息列表，每次对话都发给模型，模型靠它记住上下文
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    # ================= ReAct 主循环（最多 max_step 轮） =================
    # 每一轮模型输出“Thought(想) -> 是否 Action(做)”，
    # 程序解析并执行工具得到 Observation(观察结果)，
    # 把观察结果喂回给模型，直到模型输出 Final Answer（想清楚了）。
    for step in range(max_step):
        # 1) 调用大模型，拿到本轮输出
        resp = ollama.chat(model="qwen:7b", messages=messages, stream=False)
        content = resp["message"]["content"]
        print(f"\n---Step {step+1}---\n{content}")

        # 2) 判断是否该结束：模型认为答案已足够，输出 Final Answer: xxx
        if "Final Answer:" in content:
            return content.split("Final Answer:")[-1].strip()

        # 3) 没结束，说明模型想要调用工具：用正则解析 Action 这一行
        #    格式约定：Action: 工具名|参数1|参数2|运算符
        match = re.search(r"Action:\s*(\w+)\|(.*)", content)
        if not match:
            # 模型没按格式输出（例如没人 Thought 或 Action 格式不对）
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "Observation: 工具调用格式错误"})
            continue

        # 4) 解析出：工具名 + 参数串（如 "1234|456|*"）
        tool_name, args_str = match.groups()
        args = args_str.split("|")   # -> ["1234", "456", "*"]

        # 5) 执行工具
        fn = tools.get(tool_name)
        if fn is None:
            obs = "工具不存在"       # 模型调用了没登记的工具
        else:
            try:
                res = fn(float(args[0]), float(args[1]), args[2])
                obs = str(res)
            except (IndexError, ValueError):
                obs = "参数格式错误"  # 参数数量不对或不是数字

        # 6) 【关键一步】把 Observation 塞回上下文：
        #    让模型“看到”它上一个 Action 的结果，它才能继续推理。
        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": f"Observation: {obs}"})

        # 回到循环顶部 -> 模型基于 Observation 继续 Thought -> ...
    return "超过最大步骤"   # 循环了 max_step 轮还没出 Final Answer


if __name__ == "__main__":
    ans = react_agent("1234乘以456等于多少？")
    print("\n====最终结果====\n", ans)
```



极简程序

```
import ollama
import re

def read_file(filepath:str):
    with open(filepath,"r",encoding="utf-8") as f:
        return f.read()

tools = {"read_file": read_file}

system_prompt = """
ReAct格式：
Thought:
Action: read_file|filepath
Observation:（程序填充）
拿到信息后输出 Final Answer: xxx
"""

def react_file_agent(user_query, max_step=3):
    messages = [{"role":"system","content":system_prompt},{"role":"user","content":user_query}]
    for _ in range(max_step):
        resp = ollama.chat(model="qwen:7b", messages=messages)
        text = resp["message"]["content"]
        print(text)
        if "Final Answer:" in text:
            return text
        match = re.search(r"Action:\s*read_file\|(.+)", text)
        if match:
            fp = match.group(1).strip()
            obs = read_file(fp)
        else:
            obs = "无法解析工具"
        messages.append({"role":"assistant","content":text})
        messages.append({"role":"user","content":f"Observation:{obs}"})
    return "超出最大步数"

if __name__ == "__main__":
    react_file_agent("读取test.txt，告诉我里面写了什么")

```

