from dataclasses import dataclass


@dataclass(frozen=True)
class CorpusDocument:
    kb_id: str
    kb_name: str
    document_name: str
    doc_type: str
    markdown: str
