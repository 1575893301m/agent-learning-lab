import json
from pathlib import Path
import re

import ollama

MODEL = "qwen2.5:3b"
PROJECT_ROOT = Path(__file__).resolve().parent
WORK_DIR = PROJECT_ROOT / "agent_workspace"
OUTPUT_DIR = PROJECT_ROOT / "output"
MAX_STEPS = 16


def _safe_child(root: Path, filename: str) -> Path:
    base = Path(root).resolve()
    candidate = (base / filename).resolve()
    if candidate.parent != base:
        raise ValueError("只能访问指定目录的直接子文件。")
    return candidate


def list_files(work_dir: Path = WORK_DIR) -> list[str]:
    root = Path(work_dir).resolve()
    if not root.is_dir():
        return []
    return sorted(path.name for path in root.glob("*.md") if path.is_file())


def read_file(filename: str, work_dir: Path = WORK_DIR) -> str:
    path = _safe_child(work_dir, filename)
    if path.suffix.lower() != ".md" or not path.is_file():
        raise ValueError("只能读取工作区中存在的 Markdown 文件。")
    return path.read_text(encoding="utf-8")


def filter_paragraphs(filename: str, keyword: str, work_dir: Path = WORK_DIR) -> list[str]:
    if not keyword.strip():
        raise ValueError("筛选关键词不能为空。")
    content = read_file(filename, work_dir)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    return [paragraph for paragraph in paragraphs if keyword.casefold() in paragraph.casefold()]


def write_summary(output_name: str, content: str, output_dir: Path = OUTPUT_DIR) -> str:
    if not output_name.lower().endswith(".md") or Path(output_name).name != output_name:
        raise ValueError("输出名称必须是单层 Markdown 文件名。")
    if not content.strip():
        raise ValueError("总结内容不能为空。")
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = _safe_child(root, output_name)
    if target.exists():
        raise FileExistsError(f"目标文件已存在，为避免覆盖未写入：{output_name}")
    target.write_text(content.rstrip() + "\n", encoding="utf-8")
    return f"已写入 {output_name}（{target.stat().st_size} 字节）。"


def execute_action(action: dict, work_dir: Path = WORK_DIR, output_dir: Path = OUTPUT_DIR) -> str:
    name = action.get("action")
    if name == "list_files" and set(action) == {"action"}:
        files = list_files(work_dir)
        return "工作区没有 Markdown 文件。" if not files else "\n".join(files)
    if name == "read_file" and set(action) == {"action", "filename"}:
        return read_file(_require_text(action, "filename"), work_dir)
    if name == "filter_paragraphs" and set(action) == {"action", "filename", "keyword"}:
        matches = filter_paragraphs(
            _require_text(action, "filename"), _require_text(action, "keyword"), work_dir
        )
        return "没有找到匹配段落。" if not matches else "\n\n".join(matches)
    if name == "write_summary" and set(action) == {"action", "output_name", "content"}:
        return write_summary(
            _require_text(action, "output_name"), _require_text(action, "content"), output_dir
        )
    if name not in {"list_files", "read_file", "filter_paragraphs", "write_summary"}:
        return f"工具调用失败：未知工具 {name!r}。"
    return f"工具调用失败：{name} 的参数不符合要求。"


def _require_text(action: dict, field: str) -> str:
    value = action.get(field)
    if not isinstance(value, str):
        raise ValueError(f"参数 {field} 必须是文本。")
    return value


def _output_name_from_task(task: str) -> str:
    match = re.search(r"(?:保存为|写入|保存到|输出为)\s*[`\"']?([A-Za-z0-9_-]+\.md)", task)
    return match.group(1) if match else "agent-summary.md"


def _summarize_matches(matches: list[dict[str, str]]) -> str:
    if not matches:
        return "# Agent 学习总结\n\n没有找到包含关键词“Agent”的段落。"
    source_text = "\n\n".join(
        f"来源文件：{item['filename']}\n段落：\n{item['content']}" for item in matches
    )
    response = ollama.chat(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": "你负责整理资料摘要。只根据用户提供的段落写一份简洁、忠实的中文 Markdown 总结，不补充来源中没有的事实。",
            },
            {
                "role": "user",
                "content": f"请整理以下筛选出的段落，保留关键概念并合并重复信息：\n\n{source_text}",
            },
        ],
        stream=False,
    )
    summary = response["message"]["content"].strip()
    if summary.startswith("Final Answer:"):
        summary = summary.split("Final Answer:", 1)[1].strip()
    if not summary:
        raise ValueError("模型返回了空总结，没有写入文件。")
    return summary


def run_agent(
    task: str,
    max_steps: int = MAX_STEPS,
    work_dir: Path = WORK_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> str:
    files = list_files(work_dir)
    print(f"\n--- Tool step ---\nAction: list_files\nObservation: {json.dumps(files, ensure_ascii=False)}")
    required_steps = 2 * len(files) + 3
    if required_steps > max_steps:
        return f"工作区有 {len(files)} 个文件，需要 {required_steps} 步，超过上限 {max_steps}；未写入总结。"

    matches = []
    for filename in files:
        content = read_file(filename, work_dir)
        print(f"\n--- Tool step ---\nAction: read_file({filename})\nObservation: 已读取 {len(content)} 个字符")
        paragraphs = filter_paragraphs(filename, "Agent", work_dir)
        print(f"\n--- Tool step ---\nAction: filter_paragraphs({filename}, Agent)\nObservation: 命中 {len(paragraphs)} 个段落")
        matches.extend({"filename": filename, "content": paragraph} for paragraph in paragraphs)

    print(f"\n--- Model step ---\n基于 {len(matches)} 个命中段落生成总结")
    summary = _summarize_matches(matches)
    output_name = _output_name_from_task(task)
    result = write_summary(output_name, summary, output_dir)
    print(f"\n--- Tool step ---\nAction: write_summary({output_name})\nObservation: {result}")
    return result


if __name__ == "__main__":
    task = input("请输入文件批处理任务：")
    try:
        result = run_agent(task)
    except ollama.ResponseError as error:
        print(f"\nOllama 请求失败（HTTP {error.status_code}）：{error.error or error}。请检查 Ollama 服务、模型和当前 PowerShell 的连接/代理设置后重试。")
    except (ConnectionError, TimeoutError) as error:
        print(f"\n无法连接 Ollama：{error}。请确认 Ollama 正在运行并监听本机地址。")
    else:
        print("\n==== 最终结果 ====\n" + result)
