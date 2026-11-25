import json

from fastapi import APIRouter, HTTPException, Request

from app.auth import Account, authenticate, issue_token, require_account, require_admin
from app.core.config import APP_ROOT
from app.ops.audit import list_audit, record_audit
from app.ops.metrics import observe_query, snapshot
from app.rag.answer import (
    CitationMissingError,
    ModelCallError,
    ModelNotConfiguredError,
    answer_question,
)
from app.rag.catalog import find_knowledge_base, list_knowledge_bases
from app.rag.policy import (
    classify_intent,
    closed_documents,
    disclaimer,
    knowledge_base_policy,
    risk_flags,
    screen_question,
)
from app.rag.retriever import Passage, UnknownKnowledgeBaseError, get_passage

from .schemas import (
    AuditItem,
    CitationResponse,
    ClosedDocumentResponse,
    DocumentResponse,
    KnowledgeBaseResponse,
    LoginRequest,
    LoginResponse,
    PassageResponse,
    PrepareReportResponse,
    QueryRequest,
    QueryResponse,
    RiskResponse,
)

router = APIRouter(prefix="/api")
EXCERPT_LIMIT = 160


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    account = authenticate(body.username.strip(), body.password)
    if account is None:
        await record_audit(body.username.strip(), "login", "", False, "账号或密码错误")
        raise HTTPException(status_code=401, detail="账号或密码错误")
    await record_audit(account.username, "login", "", True, account.role)
    return LoginResponse(
        token=issue_token(account),
        username=account.username,
        role=account.role,
        display_name=account.display_name,
        kb_ids=list(account.kb_ids),
    )


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseResponse])
async def knowledge_bases(request: Request) -> list[KnowledgeBaseResponse]:
    account = require_account(request)
    visible = [base for base in list_knowledge_bases() if account.allows(base.kb_id)]
    return [_base_response(base) for base in visible]


@router.post("/knowledge-bases/{kb_id}/select")
async def select_knowledge_base(kb_id: str, request: Request) -> dict[str, str]:
    account = require_account(request)
    try:
        _ensure_allowed(account, kb_id)
    except HTTPException as exc:
        await record_audit(account.username, "switch_kb", kb_id, False, str(exc.detail))
        raise
    await record_audit(account.username, "switch_kb", kb_id, True, "切换知识库")
    return {"kb_id": kb_id}


@router.post("/query", response_model=QueryResponse)
async def query(body: QueryRequest, request: Request) -> QueryResponse:
    account = require_account(request)
    ticket = "-"
    try:
        ticket = _ticket(body.ticket_id)
        _ensure_allowed(account, body.kb_id)
        refusal = screen_question(body.kb_id, body.question)
        if refusal is not None:
            raise HTTPException(status_code=422, detail=refusal.message)
        result = await answer_question(request.app.state.store, body.kb_id, body.question)
    except HTTPException as exc:
        observe_query(False)
        detail = str(exc.detail)
        if ticket != "-":
            detail = f"单号 {ticket}；{detail}"
        await record_audit(account.username, "query", body.kb_id, False, detail)
        raise
    except KeyError:
        observe_query(False)
        await record_audit(account.username, "query", body.kb_id, False, "文档集不存在")
        raise HTTPException(status_code=404, detail="文档集不存在") from None
    except UnknownKnowledgeBaseError:
        observe_query(False)
        await record_audit(account.username, "query", body.kb_id, False, "文档集不存在")
        raise HTTPException(status_code=404, detail="文档集不存在") from None
    except ModelNotConfiguredError:
        observe_query(False)
        await record_audit(account.username, "query", body.kb_id, False, "对话模型未配置")
        raise HTTPException(status_code=503, detail="对话模型未配置") from None
    except ModelCallError as exc:
        observe_query(False)
        await record_audit(account.username, "query", body.kb_id, False, str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from None
    except CitationMissingError as exc:
        observe_query(False)
        await record_audit(account.username, "query", body.kb_id, False, str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from None
    observe_query(True)
    intent = classify_intent(body.question)
    flags = risk_flags(
        body.question,
        [item.content for item in result.citations],
    )
    policy = knowledge_base_policy(body.kb_id)
    await record_audit(
        account.username,
        "query",
        body.kb_id,
        True,
        f"单号 {ticket}；意图 {intent}；引用 {len(result.citations)} 条",
    )
    return QueryResponse(
        answer=result.answer,
        citations=[_citation(item) for item in result.citations],
        intent=intent,
        owner_dept=policy.owner_dept,
        disclaimer=disclaimer(),
        risks=[RiskResponse(code=item.code, level=item.level, hint=item.hint) for item in flags],
    )


@router.get("/passages/{parent_id}", response_model=PassageResponse)
async def passage(parent_id: str, kb_id: str, request: Request) -> PassageResponse:
    account = require_account(request)
    try:
        _ensure_allowed(account, kb_id)
        found = await get_passage(kb_id, parent_id)
    except HTTPException as exc:
        await record_audit(account.username, "view_passage", kb_id, False, str(exc.detail))
        raise
    except UnknownKnowledgeBaseError:
        await record_audit(account.username, "view_passage", kb_id, False, "章节不存在")
        raise HTTPException(status_code=404, detail="章节不存在") from None
    if found is None:
        await record_audit(account.username, "view_passage", kb_id, False, "章节不存在")
        raise HTTPException(status_code=404, detail="章节不存在")
    await record_audit(account.username, "view_passage", kb_id, True, found.document_name)
    return PassageResponse(
        parent_id=found.parent_id,
        document_name=found.document_name,
        doc_type=found.doc_type,
        section_path=found.section_path,
        content=found.content,
    )


@router.get("/admin/audit", response_model=list[AuditItem])
async def audit(request: Request) -> list[AuditItem]:
    account = require_account(request)
    require_admin(account)
    rows = await list_audit()
    return [
        AuditItem(
            id=row.id,
            username=row.username,
            action=row.action,
            kb_id=row.kb_id,
            success=row.success,
            detail=row.detail,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )
        for row in rows
    ]


@router.get("/admin/metrics")
async def metrics(request: Request) -> dict[str, object]:
    account = require_account(request)
    require_admin(account)
    return snapshot()


@router.get("/admin/prepare-report", response_model=PrepareReportResponse)
async def prepare_report(request: Request) -> PrepareReportResponse:
    account = require_account(request)
    require_admin(account)
    path = APP_ROOT / "data" / "reports" / "estate_prepare.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="还没有整理报告，请先运行 scripts/prepare_documents.py")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return PrepareReportResponse(**payload)


def _ensure_allowed(account: Account, kb_id: str) -> None:
    base = find_knowledge_base(kb_id)
    if base is None:
        raise HTTPException(status_code=404, detail="文档集不存在")
    if not account.allows(kb_id):
        raise HTTPException(status_code=403, detail="没有该知识库的查询权限")


def _ticket(value: str) -> str:
    ticket = value.strip()
    if ticket and not ticket.replace("-", "").isalnum():
        raise HTTPException(status_code=422, detail="咨询单号只允许字母、数字和短横线")
    return ticket or "-"


def _base_response(base) -> KnowledgeBaseResponse:
    policy = knowledge_base_policy(base.kb_id)
    return KnowledgeBaseResponse(
        kb_id=base.kb_id,
        kb_name=base.kb_name,
        owner_dept=policy.owner_dept,
        scene=policy.scene,
        documents=[
            DocumentResponse(
                document_name=document.document_name,
                doc_type=document.doc_type,
            )
            for document in base.documents
        ],
        closed_documents=[
            ClosedDocumentResponse(
                document_name=item.document_name,
                doc_type=item.doc_type,
                replaced_by=item.replaced_by,
                reason=item.reason,
            )
            for item in closed_documents(base.kb_id)
        ],
        prompts=list(base.prompts),
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
