import re
import time
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_milvus import Milvus
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.ops.metrics import observe_model_failure, observe_retrieval
from app.rag.catalog import find_knowledge_base
from app.rag.retriever import Passage, load_passages, query_document

logger = get_logger(__name__)

SYSTEM_PROMPT = """你是文档问答助手，只根据给定材料用简体中文回答。
必须遵守：
1. 先依据检索材料回答，不要跳过材料自行发挥。
2. 材料里没有的内容不要编造，直接说明所选文档集中没有相关约定。材料写明不约定、不适用或不收取时，按没有该项约定回答。
3. 每条事实后面只标注支撑该句的材料编号，格式为 [1]、[2]。编号必须来自给定材料，没有用到的材料不要标注。
不要使用 Markdown 标题、加粗或代码块。"""

MATERIAL_LIMIT = 1200


class ModelNotConfiguredError(RuntimeError):
    pass


class ModelCallError(RuntimeError):
    pass


class CitationMissingError(RuntimeError):
    pass


@dataclass(frozen=True)
class Answer:
    answer: str
    citations: list[Passage]


def _model() -> ChatOpenAI:
    api_key = (settings.llm.api_key or "").strip()
    if not api_key or api_key == "your_deepseek_api_key":
        raise ModelNotConfiguredError
    return ChatOpenAI(
        model=settings.llm.model,
        api_key=api_key,
        base_url=settings.llm.base_url,
        temperature=0,
        max_tokens=1200,
        extra_body={"thinking": {"type": "disabled"}},
    )


def _materials(passages: list[Passage]) -> str:
    blocks: list[str] = []
    for passage in passages:
        section = " / ".join(passage.section_path) or "正文"
        content = passage.content.strip()
        if len(content) > MATERIAL_LIMIT:
            content = content[:MATERIAL_LIMIT] + "…"
        blocks.append(
            f"[{passage.number}] {passage.document_name} / {section}\n{content}"
        )
    return "\n\n".join(blocks)


async def answer_question(store: Milvus, kb_id: str, question: str) -> Answer:
    knowledge_base = find_knowledge_base(kb_id)
    if knowledge_base is None:
        raise KeyError(kb_id)
    started = time.perf_counter()
    parent_ids = query_document(store, kb_id, question)
    passages = await load_passages(kb_id, parent_ids)
    elapsed_ms = (time.perf_counter() - started) * 1000
    observe_retrieval(elapsed_ms, empty=not passages)
    logger.info(
        "检索完成",
        kb_id=kb_id,
        hits=len(passages),
        elapsed_ms=round(elapsed_ms, 1),
        empty=not passages,
    )
    if not passages:
        logger.warning("召回为空", kb_id=kb_id, question=question.strip()[:80])
        return Answer(
            answer=f"在「{knowledge_base.kb_name}」中无相关约定。",
            citations=[],
        )
    try:
        response = await _model().ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        f"文档集：{knowledge_base.kb_name}\n"
                        f"问题：{question.strip()}\n\n"
                        f"检索材料：\n{_materials(passages)}"
                    )
                ),
            ]
        )
    except ModelNotConfiguredError:
        raise
    except Exception as exc:
        observe_model_failure()
        logger.exception("模型调用失败", kb_id=kb_id)
        raise ModelCallError("对话模型调用失败") from exc
    answer = _message_text(response.content).strip()
    used = _used_passages(answer, passages)
    if not used:
        logger.warning("引用缺失", kb_id=kb_id)
        raise CitationMissingError("回答未标注有效引用，已拒答")
    return Answer(answer=answer, citations=used)


def _used_passages(answer: str, passages: list[Passage]) -> list[Passage]:
    numbers = {int(item) for item in re.findall(r"\[(\d+)\]", answer)}
    valid = {passage.number for passage in passages}
    if numbers - valid:
        logger.warning("引用编号不在材料中", kb_id=passages[0].document_name, numbers=sorted(numbers - valid))
    return [passage for passage in passages if passage.number in numbers]


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    return str(content or "")
