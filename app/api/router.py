from fastapi import APIRouter, HTTPException, Request

from app.rag.answer import ModelNotConfiguredError, answer_question
from app.rag.catalog import list_knowledge_bases
from app.rag.retriever import Passage, UnknownKnowledgeBaseError, get_passage

from .schemas import (
    CitationResponse,
    DocumentResponse,
    KnowledgeBaseResponse,
    PassageResponse,
    QueryRequest,
    QueryResponse,
)

router = APIRouter(prefix="/api")
EXCERPT_LIMIT = 160


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseResponse])
async def knowledge_bases() -> list[KnowledgeBaseResponse]:
    return [
        KnowledgeBaseResponse(
            kb_id=base.kb_id,
            kb_name=base.kb_name,
            documents=[
                DocumentResponse(
                    document_name=document.document_name,
                    doc_type=document.doc_type,
                )
                for document in base.documents
            ],
            prompts=list(base.prompts),
        )
        for base in list_knowledge_bases()
    ]


@router.post("/query", response_model=QueryResponse)
async def query(body: QueryRequest, request: Request) -> QueryResponse:
    try:
        result = await answer_question(request.app.state.store, body.kb_id, body.question)
    except KeyError:
        raise HTTPException(status_code=404, detail="文档集不存在") from None
    except UnknownKnowledgeBaseError:
        raise HTTPException(status_code=404, detail="文档集不存在") from None
    except ModelNotConfiguredError:
        raise HTTPException(status_code=503, detail="对话模型未配置") from None
    return QueryResponse(
        answer=result.answer,
        citations=[_citation(item) for item in result.citations],
    )


@router.get("/passages/{parent_id}", response_model=PassageResponse)
async def passage(parent_id: str, kb_id: str) -> PassageResponse:
    try:
        found = await get_passage(kb_id, parent_id)
    except UnknownKnowledgeBaseError:
        raise HTTPException(status_code=404, detail="章节不存在") from None
    if found is None:
        raise HTTPException(status_code=404, detail="章节不存在")
    return PassageResponse(
        parent_id=found.parent_id,
        document_name=found.document_name,
        doc_type=found.doc_type,
        section_path=found.section_path,
        content=found.content,
    )


def _citation(passage: Passage) -> CitationResponse:
    text = " ".join(passage.content.split())
    if len(text) > EXCERPT_LIMIT:
        text = text[:EXCERPT_LIMIT] + "…"
    return CitationResponse(
        number=passage.number,
        parent_id=passage.parent_id,
        document_name=passage.document_name,
        doc_type=passage.doc_type,
        section_path=passage.section_path,
        excerpt=text,
    )
