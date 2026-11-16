from pathlib import Path
import re

import ollama

MODEL = "qwen2.5:3b"
PROJECT_ROOT = Path(__file__).resolve().parent
MAX_CONTENT_LENGTH = 10_000


def read_file(filepath: str) -> str:
    path = (PROJECT_ROOT / filepath).resolve()
    try:
        path.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise PermissionError("不允许读取项目目录之外的文件") from error

    if not path.is_file():
        raise FileNotFoundError(f"文件不存在: {filepath}")

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise UnicodeError("文件不是有效的 UTF-8 文本") from error

    if len(content) > MAX_CONTENT_LENGTH:
        raise ValueError(f"文件内容超过 {MAX_CONTENT_LENGTH} 个字符")
    return content


SYSTEM_PROMPT = """
你是一个 ReAct 文件读取 Agent。
需要读取文件时，严格输出：Action: read_file|相对文件路径
拿到 Observation 后，如果已经知道答案，输出：Final Answer: 最终答案
不要自己编造文件内容，必须先调用 read_file 工具。
"""


def react_file_agent(user_query: str, max_steps: int = 5) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    for step in range(max_steps):
        response = ollama.chat(model=MODEL, messages=messages, stream=False)
        content = response["message"]["content"]
        print(f"\n--- Step {step + 1} ---\n{content}")

        match = re.search(r"Action:\s*read_file\|([^\n]+)", content)
        if not match and "Final Answer:" in content:
            return content.split("Final Answer:", 1)[1].strip()

        if not match:
            observation = "工具调用格式错误，请输出 Action: read_file|相对文件路径"
        else:
            try:
                observation = read_file(match.group(1).strip())
            except (FileNotFoundError, PermissionError, UnicodeError, ValueError) as error:
                observation = f"工具执行错误: {error}"

        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": f"Observation: {observation}\n请继续处理。"})

    return "超过最大步骤限制"


if __name__ == "__main__":
    question = input("请输入文件读取问题：")
    print("\n==== 最终结果 ====\n" + react_file_agent(question))
