from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    document_name: str
    doc_type: str


class KnowledgeBaseResponse(BaseModel):
    kb_id: str
    kb_name: str
    documents: list[DocumentResponse]
    prompts: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    kb_id: str
    question: str = Field(min_length=1, max_length=500)


class CitationResponse(BaseModel):
    number: int
    parent_id: str
    document_name: str
    doc_type: str
    section_path: list[str]
    excerpt: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]


class PassageResponse(BaseModel):
    parent_id: str
    document_name: str
    doc_type: str
    section_path: list[str]
    content: str
