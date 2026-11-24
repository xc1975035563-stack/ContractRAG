export type CatalogDocument = {
  document_name: string;
  doc_type: string;
};

export type KnowledgeBase = {
  kb_id: string;
  kb_name: string;
  documents: CatalogDocument[];
  prompts: string[];
};

export type Citation = {
  number: number;
  parent_id: string;
  document_name: string;
  doc_type: string;
  section_path: string[];
  excerpt: string;
};

export type QueryResult = {
  answer: string;
  citations: Citation[];
};

export type Passage = {
  parent_id: string;
  document_name: string;
  doc_type: string;
  section_path: string[];
  content: string;
};

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // 响应体不是 JSON 时使用状态码。
  }
  return `请求失败（${response.status}）`;
}

export async function fetchKnowledgeBases(): Promise<KnowledgeBase[]> {
  let response: Response;
  try {
    response = await fetch("/api/knowledge-bases");
  } catch {
    throw new Error("接口暂时没有响应，请稍等后刷新页面");
  }
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function queryDocuments(kbId: string, question: string): Promise<QueryResult> {
  const response = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kb_id: kbId, question }),
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function fetchPassage(kbId: string, parentId: string): Promise<Passage> {
  const response = await fetch(
    `/api/passages/${parentId}?kb_id=${encodeURIComponent(kbId)}`,
  );
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}
