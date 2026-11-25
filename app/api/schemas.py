from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str
    display_name: str
    kb_ids: list[str]


class DocumentResponse(BaseModel):
    document_name: str
    doc_type: str


class ClosedDocumentResponse(BaseModel):
    document_name: str
    doc_type: str
    replaced_by: str
    reason: str


class KnowledgeBaseResponse(BaseModel):
    kb_id: str
    kb_name: str
    owner_dept: str
    scene: str
    documents: list[DocumentResponse]
    closed_documents: list[ClosedDocumentResponse] = Field(default_factory=list)
    prompts: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    kb_id: str
    question: str = Field(min_length=1, max_length=500)
    ticket_id: str = Field(default="", max_length=32)


class CitationResponse(BaseModel):
    number: int
    parent_id: str
    document_name: str
    doc_type: str
    section_path: list[str]
    excerpt: str


class RiskResponse(BaseModel):
    code: str
    level: str
    hint: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    intent: str
    owner_dept: str
    disclaimer: str
    risks: list[RiskResponse] = Field(default_factory=list)


class PassageResponse(BaseModel):
    parent_id: str
    document_name: str
    doc_type: str
    section_path: list[str]
    content: str


class AuditItem(BaseModel):
    id: int
    username: str
    action: str
    kb_id: str
    success: bool
    detail: str
    created_at: str


class PrepareReportResponse(BaseModel):
    written: list[str]
    notes: list[dict[str, str]]
    failures: list[dict[str, str]]
