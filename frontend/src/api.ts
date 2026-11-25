export type CatalogDocument = {
  document_name: string;
  doc_type: string;
};

export type ClosedDocument = {
  document_name: string;
  doc_type: string;
  replaced_by: string;
  reason: string;
};

export type KnowledgeBase = {
  kb_id: string;
  kb_name: string;
  owner_dept: string;
  scene: string;
  documents: CatalogDocument[];
  closed_documents: ClosedDocument[];
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

export type RiskFlag = {
  code: string;
  level: string;
  hint: string;
};

export type QueryResult = {
  answer: string;
  citations: Citation[];
  intent: string;
  owner_dept: string;
  disclaimer: string;
  risks: RiskFlag[];
};

export type Passage = {
  parent_id: string;
  document_name: string;
  doc_type: string;
  section_path: string[];
  content: string;
};

export type Session = {
  token: string;
  username: string;
  role: string;
  display_name: string;
  kb_ids: string[];
};

export type AuditItem = {
  id: number;
  username: string;
  action: string;
  kb_id: string;
  success: boolean;
  detail: string;
  created_at: string;
};

const SESSION_KEY = "contractrag-session";

export function loadSession(): Session | null {
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function saveSession(session: Session | null) {
  if (session) {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } else {
    sessionStorage.removeItem(SESSION_KEY);
  }
}

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

async function request(path: string, token: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        ...(init?.headers ?? {}),
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    throw new Error("接口暂时没有响应，请稍等后刷新页面");
  }
  if (response.status === 401) {
    saveSession(null);
    throw new Error(await readError(response));
  }
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response;
}

export async function login(username: string, password: string): Promise<Session> {
  const response = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  const session = (await response.json()) as Session;
  saveSession(session);
  return session;
}

export async function fetchKnowledgeBases(token: string): Promise<KnowledgeBase[]> {
  const response = await request("/api/knowledge-bases", token);
  return response.json();
}

export async function selectKnowledgeBase(token: string, kbId: string): Promise<void> {
  await request(`/api/knowledge-bases/${encodeURIComponent(kbId)}/select`, token, {
    method: "POST",
  });
}

export async function queryDocuments(
  token: string,
  kbId: string,
  question: string,
  ticketId: string,
): Promise<QueryResult> {
  const response = await request("/api/query", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kb_id: kbId, question, ticket_id: ticketId }),
  });
  return response.json();
}

export async function fetchPassage(token: string, kbId: string, parentId: string): Promise<Passage> {
  const response = await request(
    `/api/passages/${parentId}?kb_id=${encodeURIComponent(kbId)}`,
    token,
  );
  return response.json();
}

export async function fetchAudit(token: string): Promise<AuditItem[]> {
  const response = await request("/api/admin/audit", token);
  return response.json();
}
