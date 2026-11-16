import re  # 导入正则表达式模块，用来从模型回复中提取 Action。
import ollama  # 导入 Ollama Python 客户端，用来向本地模型发送对话。

MODEL = "qwen2.5:3b"  # 指定要调用的本地模型名称。


# 1. 工具：Python 负责实际计算，定义 calculator(a, b, op)。

def calculator(a: float, b: float, op: str) -> float:  # 定义计算函数；类型标注说明参数和返回值预期的类型。
    if op == "+":  # 如果运算符是加号……
        return a + b  # 返回 a 与 b 的和，并结束本次函数调用。
    if op == "-":  # 如果运算符是减号……
        return a - b  # 返回 a 减去 b 的结果。
    if op == "*":  # 如果运算符是乘号……
        return a * b  # 返回 a 与 b 的乘积。
    if op == "/":  # 如果运算符是除号……
        if b == 0:  # 除法中，除数不能为零。
            raise ZeroDivisionError("不能除以零")  # 抛出除零异常，停止函数并交给外层处理。
        return a / b  # 除数不为零时，返回 a 除以 b 的结果。
    raise ValueError(f"不支持的运算符: {op}")  # 不是四种支持的符号时，抛出参数错误。


# 2. 系统提示词：规定模型应该如何行动。
SYSTEM_PROMPT = """  # 用三引号保存一段可跨多行的字符串。
你是一个 ReAct 计算器 Agent。

必须严格遵守格式：

Thought: 你的简短思考
Action: calculator|数字1|数字2|运算符

运算符只能是 +、-、*、/。

拿到 Observation 后，如果已经知道答案，必须输出：

Final Answer: 最终答案

不要自己计算，必须先调用 calculator 工具。
"""  # 多行字符串结束；SYSTEM_PROMPT 变量保存了这段规则文本。

# 3. 上下文：messages 保存这次任务的对话历史。
def react_agent(user_query: str, max_steps: int = 5) -> str:  # 定义 Agent 主函数；最多向模型请求 max_steps 轮，最终返回字符串。
    # 创建消息列表；列表里的每个元素都是带 role 和 content 的字典。
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},  # system 消息提供规则。
        {"role": "user", "content": user_query},  # user 消息提供用户本次的问题。
    ]

    # 4. 调用模型：最多循环 max_steps 轮，让模型逐步完成任务。
    for step in range(max_steps):  # range(max_steps) 产生 0 到 max_steps-1 的轮次编号。
        # 把模型名和完整消息上下文发送给 Ollama，并等待完整回复。
        response = ollama.chat(
            model=MODEL,  # 使用上面配置的 qwen2.5:3b 模型。
            messages=messages,  # 把当前所有对话上下文交给模型。
            stream=False,  # 关闭流式输出，等完整回复返回后再处理。
        )

        content = response["message"]["content"]  # 从 Ollama 返回对象中取出模型回复正文。
        print(f"\n--- Step {step + 1} ---")  # 显示当前轮次；step 从 0 开始，所以展示时加 1。
        print(content)  # 把模型本轮原始回复打印到终端，便于观察 ReAct 过程。

        # 在回复文本中搜索符合约定格式的计算器 Action。
        match = re.search(
            r"Action:\s*calculator\|([^|\n]+)\|([^|\n]+)\|([+\-*/])",  # 捕获两个参数和一个合法运算符。
            content,  # 要搜索的文本是模型回复。
        )

        # 5. 解析 Action 并执行：有 Action 就由 Python 工具算，不采信模型附带的答案。
        if not match and "Final Answer:" in content:
            return content.split("Final Answer:", 1)[1].strip()  # 没有 Action 且有最终答案时，取出答案并结束 Agent。

        if not match:
            observation = "工具调用格式错误，请严格输出 Action: calculator|数字1|数字2|运算符"  # 格式不符合约定时，准备错误反馈。
        else:
            try:
                a = float(match.group(1).strip())  # 取出第一个参数，去掉首尾空格并转换为浮点数。
                b = float(match.group(2).strip())  # 取出第二个参数并转换为浮点数。
                op = match.group(3)  # 取出正则捕获到的运算符。
                observation = str(calculator(a, b, op))  # 执行 Python 计算器，并把结果转成文本。
            except (ValueError, ZeroDivisionError) as error:
                observation = f"工具执行错误: {error}"  # 捕获参数错误或除零错误，转成可反馈给模型的文字。

        # 将模型回复加入历史，让下一轮知道它刚才提出了什么行动。
        messages.append({"role": "assistant", "content": content})
        # 将工具执行结果作为 Observation 加入历史，下一轮模型就能看到结果或错误。
        messages.append(
            {
                "role": "user",  # Ollama 对话格式用 user 角色承载这条工具结果文本。
                "content": f"Observation: {observation}\n请继续处理。",  # 反馈观察结果并要求模型继续。
            }
        )

    return "超过最大步骤限制"  # 循环用完仍未得到 Final Answer 时，停止并返回提示。


if __name__ == "__main__":  # 只有直接运行本文件时，下面的交互入口才会执行；被导入时不会执行。
    question = input("请输入计算问题：")  # 在终端等待用户输入问题，并把输入内容保存到 question。
    result = react_agent(question)  # 把用户问题传给 Agent，接收它返回的最终结果。
    print("\n==== 最终结果 ====")  # 打印结果标题，让输出更清楚。
    print(result)  # 显示 Agent 的最终答案。
