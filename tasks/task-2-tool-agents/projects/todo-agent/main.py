from datetime import datetime
import json
from pathlib import Path
import re
from typing import TypedDict

import ollama

MODEL = "qwen2.5:3b"
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_FILE = PROJECT_ROOT / "data" / "todos.json"
MAX_STEPS = 3


class Todo(TypedDict):
    id: int
    content: str
    time: str
    done: bool


SYSTEM_PROMPT = """
你是本地待办管理 Agent。根据用户意图选择一个工具。
如果用户询问你支持哪些指令或能力，直接用中文说明新增、查看、修改、删除待办，不调用工具。
要操作待办时，只允许输出一个 JSON 对象，不要 Markdown 代码块或额外解释。一次只能选择一个工具，绝不同时输出多个 JSON 对象。
新增：{"action":"add_todo","content":"待办内容","time":"时间"}
查看：{"action":"list_todos"}
修改：{"action":"update_todo","id":1,"content":"新内容","time":"新时间","done":false}
删除：{"action":"delete_todo","id":1}
用户只提供部分修改字段时，只输出要修改的字段。
收到 Observation 后，以 Final Answer: 开头向用户说明工具执行结果；不得声称工具没有返回的结果。
""".strip()


def _read_todos(data_file: Path = DATA_FILE) -> list[Todo]:
    path = Path(data_file)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"待办数据文件无法读取：{error}") from error
    if not isinstance(data, list):
        raise ValueError("待办数据格式错误：根数据必须是列表")
    return data


def _write_todos(todos: list[Todo], data_file: Path = DATA_FILE) -> None:
    path = Path(data_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(todos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_todo(content: str, time: str, data_file: Path = DATA_FILE) -> str:
    content = content.strip()
    time = time.strip()
    if not content or not time:
        return "新增失败：待办内容和时间都不能为空。"
    todos = _read_todos(data_file)
    next_id = max((todo["id"] for todo in todos), default=0) + 1
    todo: Todo = {"id": next_id, "content": content, "time": time, "done": False}
    todos.append(todo)
    _write_todos(todos, data_file)
    return f"已新增待办：编号 {next_id}，内容“{content}”，时间“{time}”。"


def list_todos(data_file: Path = DATA_FILE) -> str:
    todos = _read_todos(data_file)
    if not todos:
        return "当前没有待办事项。"
    return "\n".join(
        f"编号 {todo['id']}：{todo['content']}；时间：{todo['time']}；状态：{'已完成' if todo['done'] else '未完成'}"
        for todo in todos
    )


def update_todo(
    todo_id: int,
    *,
    content: str | None = None,
    time: str | None = None,
    done: bool | None = None,
    data_file: Path = DATA_FILE,
) -> str:
    if content is None and time is None and done is None:
        return "修改失败：没有提供要修改的字段。"
    if content is not None and not content.strip():
        return "修改失败：待办内容不能为空。"
    if time is not None and not time.strip():
        return "修改失败：待办时间不能为空。"
    todos = _read_todos(data_file)
    for todo in todos:
        if todo["id"] == todo_id:
            if content is not None:
                todo["content"] = content.strip()
            if time is not None:
                todo["time"] = time.strip()
            if done is not None:
                todo["done"] = done
            _write_todos(todos, data_file)
            return f"已修改待办 {todo_id}。"
    return f"修改失败：没有编号为 {todo_id} 的待办。"


def delete_todo(todo_id: int, data_file: Path = DATA_FILE) -> str:
    todos = _read_todos(data_file)
    remaining = [todo for todo in todos if todo["id"] != todo_id]
    if len(remaining) == len(todos):
        return f"删除失败：没有编号为 {todo_id} 的待办。"
    _write_todos(remaining, data_file)
    return f"已删除待办 {todo_id}。"


def _parse_action(content: str) -> dict:
    candidate = content.strip()
    candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    try:
        action = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise ValueError("模型输出不是有效 JSON。") from error
    if not isinstance(action, dict) or not isinstance(action.get("action"), str):
        raise ValueError("工具调用必须是包含 action 字段的 JSON 对象。")
    return action


def execute_action(action: dict, data_file: Path = DATA_FILE) -> str:
    name = action.get("action")
    if name == "add_todo":
        if set(action) != {"action", "content", "time"}:
            return "调用失败：add_todo 需要且只接受 content、time 参数。"
        if not isinstance(action["content"], str) or not isinstance(action["time"], str):
            return "调用失败：content 和 time 必须是文本。"
        return add_todo(action["content"], action["time"], data_file)
    if name == "list_todos":
        if set(action) != {"action"}:
            return "调用失败：list_todos 不接受参数。"
        return list_todos(data_file)
    if name == "update_todo":
        allowed = {"action", "id", "content", "time", "done"}
        if not set(action).issubset(allowed) or "id" not in action:
            return "调用失败：update_todo 需要 id，可选 content、time、done。"
        todo_id = action["id"]
        if isinstance(todo_id, bool) or not isinstance(todo_id, int):
            return "调用失败：id 必须是整数。"
        for key, expected in (("content", str), ("time", str), ("done", bool)):
            if key in action and not isinstance(action[key], expected):
                return f"调用失败：{key} 参数类型错误。"
        return update_todo(
            todo_id,
            content=action.get("content"),
            time=action.get("time"),
            done=action.get("done"),
            data_file=data_file,
        )
    if name == "delete_todo":
        if set(action) != {"action", "id"}:
            return "调用失败：delete_todo 需要且只接受 id 参数。"
        todo_id = action["id"]
        if isinstance(todo_id, bool) or not isinstance(todo_id, int):
            return "调用失败：id 必须是整数。"
        return delete_todo(todo_id, data_file)
    return f"调用失败：未知工具 {name!r}。"


def _format_tool_observation(result: str) -> str:
    return f"工具执行结果：\n{result}"


def react_todo_agent(user_input: str, max_steps: int = MAX_STEPS) -> str:
    help_patterns = ("可以输入", "有哪些指令", "能做什么", "支持什么", "怎么使用", "使用帮助")
    if any(pattern in user_input for pattern in help_patterns):
        return (
            "我可以帮你管理本地待办：\n"
            "1. 新增：帮我新增一个明天下午 3 点学习 Agent 的待办\n"
            "2. 查看：看看我有哪些待办\n"
            "3. 修改：把编号 1 的待办改成明天下午 4 点学习多工具 Agent\n"
            "4. 删除：删除编号 1 的待办"
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    observation_received = False

    for _ in range(max_steps):
        response = ollama.chat(model=MODEL, messages=messages, stream=False)
        content = response["message"]["content"].strip()
        print(f"\n--- Agent step ---\n{content}")

        if content.startswith("Final Answer:"):
            return content.split("Final Answer:", 1)[1].strip()

        if observation_received:
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": "请根据已有 Observation 直接给出 Final Answer，不要再调用工具。",
            })
            continue

        try:
            action = _parse_action(content)
        except ValueError as error:
            return f"模型工具调用格式错误：{error}。本轮没有执行任何待办操作，请重新输入指令。"

        try:
            observation = execute_action(action)
        except (OSError, ValueError) as error:
            observation = f"工具执行错误：{error}"

        messages.append({"role": "assistant", "content": content})
        messages.append({
            "role": "user",
            "content": f"Observation: {_format_tool_observation(observation)}\n请基于工具结果回复用户。",
        })
        observation_received = True

    return "超过最大步骤限制"


if __name__ == "__main__":
    user_input = input("请输入待办管理指令：")
    print("\n==== 最终回答 ====\n" + react_todo_agent(user_input))
