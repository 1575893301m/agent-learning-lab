from pathlib import Path
import re
from typing import TypedDict

import ollama
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MODEL = "qwen2.5:3b"
PROJECT_ROOT = Path(__file__).resolve().parent
NOTES_DIR = PROJECT_ROOT / "notes"
MAX_STEPS = 3


class Note(TypedDict):
    filename: str
    content: str


class SearchResult(TypedDict):
    filename: str
    content: str
    score: float


def load_notes(folder_path: Path = NOTES_DIR) -> list[Note]:
    """Read Markdown notes recursively from the selected notes directory."""
    folder = Path(folder_path).resolve()
    if not folder.is_dir():
        return []

    notes: list[Note] = []
    for path in sorted(folder.rglob("*.md")):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8").strip()
        if content:
            notes.append({
                "filename": path.relative_to(folder).as_posix(),
                "content": content,
            })
    return notes


def _split_into_chunks(notes: list[Note]) -> list[SearchResult]:
    chunks: list[SearchResult] = []
    for note in notes:
        for paragraph in re.split(r"\n\s*\n", note["content"]):
            text = paragraph.strip()
            if text:
                chunks.append({"filename": note["filename"], "content": text, "score": 0.0})
    return chunks


def search_relevant_notes(
    question: str,
    notes: list[Note],
    top_k: int = 3,
    threshold: float = 0.08,
) -> list[SearchResult]:
    """Rank note paragraphs using character n-gram TF-IDF similarity."""
    if not question.strip() or top_k <= 0 or not notes:
        return []

    chunks = _split_into_chunks(notes)
    if not chunks:
        return []

    corpus = [chunk["content"] for chunk in chunks] + [question.strip()]
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(1, 3))
    matrix = vectorizer.fit_transform(corpus)
    scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()

    ranked = sorted(
        (
            {**chunk, "score": float(scores[index])}
            for index, chunk in enumerate(chunks)
            if scores[index] >= threshold
        ),
        key=lambda result: result["score"],
        reverse=True,
    )
    return ranked[:top_k]


SYSTEM_PROMPT = """
你是本地 Markdown 笔记问答 Agent。
判断用户是否在询问本地笔记中的个人记录、项目内容或学习历史。
这类问题必须先检索，不要用模型自身知识猜测。需要检索时，只输出：Action: search_notes
与本地笔记无关的一般知识问题可以直接回答，并以 Final Answer: 开头。
收到 Observation 后，只能依据其中的笔记片段回答；如果片段没有答案，明确说明没有查到，不要编造。

示例：
用户：我第二个 Agent 项目是什么？
助手：Action: search_notes
用户：Observation: 文件 learn-log.md 记录“第二个项目是本地 Markdown 笔记问答 Agent”。
助手：Final Answer: 你的第二个 Agent 项目是本地 Markdown 笔记问答 Agent。
"""


def _format_observation(results: list[SearchResult]) -> str:
    if not results:
        return "没有找到与问题足够相关的笔记内容。"
    return "\n\n".join(
        f"文件：{result['filename']}（相似度 {result['score']:.3f}）\n{result['content']}"
        for result in results
    )


def react_agent(question: str, max_steps: int = MAX_STEPS) -> str:
    notes = load_notes()
    observation_received = False
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for _ in range(max_steps):
        response = ollama.chat(model=MODEL, messages=messages, stream=False)
        content = response["message"]["content"].strip()
        print(f"\n--- Agent step ---\n{content}")

        match = re.search(r"Action:\s*search_notes\b", content, re.IGNORECASE)
        if match and observation_received:
            observation = "笔记检索结果已经提供，请勿重复检索；请直接基于已有 Observation 回答原问题。"
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": f"Observation: {observation}"})
            continue

        if match:
            results = search_relevant_notes(question, notes)
            observation = _format_observation(results)
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": f"Observation:\n{observation}\n请基于以上笔记回答原问题。",
            })
            observation_received = True
            continue

        if "Final Answer:" in content:
            return content.split("Final Answer:", 1)[1].strip()
        if observation_received and content:
            return content
        else:
            observation = "输出格式错误。需要查询笔记时只输出 Action: search_notes；最终回答请以 Final Answer: 开头。"
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": f"Observation: {observation}"})

    return "超过最大步骤限制"


if __name__ == "__main__":
    question = input("请输入关于本地 Markdown 笔记的问题：")
    print("\n==== 最终回答 ====\n" + react_agent(question))
