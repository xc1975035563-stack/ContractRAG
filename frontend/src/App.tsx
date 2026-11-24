import { FormEvent, useEffect, useRef, useState } from "react";
import {
  Citation,
  KnowledgeBase,
  Passage,
  fetchKnowledgeBases,
  fetchPassage,
  queryDocuments,
} from "./api";

type Turn = {
  question: string;
  answer: string;
  citations: Citation[];
};

export function App() {
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [kbId, setKbId] = useState("");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [passage, setPassage] = useState<Passage | null>(null);
  const [passageError, setPassageError] = useState("");
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [openTick, setOpenTick] = useState(0);
  const sourceRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      for (let attempt = 0; attempt < 5; attempt += 1) {
        try {
          const items = await fetchKnowledgeBases();
          if (cancelled) {
            return;
          }
          setBases(items);
          setKbId((current) => current || items[0]?.kb_id || "");
          setError("");
          return;
        } catch (reason) {
          if (attempt === 4 && !cancelled) {
            setError(reason instanceof Error ? reason.message : "请求失败");
          }
          await new Promise((resolve) => setTimeout(resolve, 800));
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = bases.find((item) => item.kb_id === kbId);

  useEffect(() => {
    const panel = sourceRef.current;
    if (!panel || !passage) {
      return;
    }
    const jump = () => {
      panel.scrollTop = 0;
      const heading = panel.querySelector("h3");
      const target = heading ?? panel;
      const box = target.getBoundingClientRect();
      if (box.top < 8 || box.bottom > window.innerHeight - 8) {
        target.scrollIntoView({ block: "center" });
      }
    };
    jump();
    const frame = requestAnimationFrame(jump);
    return () => cancelAnimationFrame(frame);
  }, [passage, openTick]);

  function chooseBase(nextId: string) {
    setKbId(nextId);
    setTurns([]);
    setPassage(null);
    setActiveKey(null);
    setError("");
  }

  async function openCitation(turnIndex: number, citation: Citation) {
    setActiveKey(`${turnIndex}-${citation.number}`);
    setOpenTick((current) => current + 1);
    setPassageError("");
    try {
      setPassage(await fetchPassage(kbId, citation.parent_id));
    } catch (reason) {
      setPassage(null);
      setPassageError(reason instanceof Error ? reason.message : "无法打开原文");
    }
  }

  async function ask(text: string) {
    if (!text || !kbId || loading) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await queryDocuments(kbId, text);
      const turnIndex = turns.length;
      setTurns((current) => [
        ...current,
        { question: text, answer: result.answer, citations: result.citations },
      ]);
      setQuestion("");
      const first = result.citations[0];
      if (first) {
        await openCitation(turnIndex, first);
      } else {
        setPassage(null);
        setActiveKey(null);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提问失败");
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(question.trim());
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <p className="eyebrow">文档问答</p>
          <h1>合同速查</h1>
        </div>
        <p className="side-label">文档集</p>
        <nav className="sets">
          {bases.map((base) => (
            <button
              key={base.kb_id}
              className={base.kb_id === kbId ? "set active" : "set"}
              type="button"
              onClick={() => chooseBase(base.kb_id)}
            >
              <strong>{base.kb_name}</strong>
              <span>{base.documents.map((item) => item.doc_type).join(" · ")}</span>
            </button>
          ))}
        </nav>
      </aside>
      <div className="workspace">
        <main className="conversation">
          <div className="messages">
            {turns.length === 0 && (
              <div className="empty">
                <p>当前文档集是「{selected?.kb_name ?? "…"}」。</p>
                {selected && (selected.prompts ?? []).length > 0 && (
                  <div className="prompts">
                    {(selected.prompts ?? []).map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        disabled={loading}
                        onClick={() => void ask(prompt)}
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            {turns.map((turn, index) => (
              <article key={`${turn.question}-${index}`} className="turn">
                <p className="question">{turn.question}</p>
                <AnswerText
                  answer={turn.answer}
                  citations={turn.citations}
                  activeKey={activeKey}
                  turnIndex={index}
                  onOpen={openCitation}
                />
                {turn.citations.length > 0 && (
                  <ul className="citation-list">
                    {turn.citations.map((citation) => (
                      <li key={citation.parent_id}>
                        <button
                          type="button"
                          className={activeKey === `${index}-${citation.number}` ? "active" : undefined}
                          onClick={() => openCitation(index, citation)}
                        >
                          [{citation.number}] {citation.document_name}
                          {citation.section_path.length > 0
                            ? ` / ${citation.section_path[citation.section_path.length - 1]}`
                            : ""}
                        </button>
                        <p>{citation.excerpt}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </article>
            ))}
          </div>
          <form className="composer" onSubmit={onSubmit}>
            {error && <p className="error">{error}</p>}
            <textarea
              value={question}
              placeholder="在当前文档集中提问"
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <button type="submit" disabled={loading || !kbId}>
              {loading ? "检索中" : "提问"}
            </button>
          </form>
        </main>
        <aside className="source" ref={sourceRef}>
          <h2>章节原文</h2>
          {passageError && <p className="error">{passageError}</p>}
          {passage ? (
            <div key={`${passage.parent_id}-${openTick}`} className="source-body">
              <p className="source-meta">
                {passage.doc_type} · {passage.document_name}
              </p>
              <h3>{passage.section_path.join(" / ") || "正文"}</h3>
              <article>{passage.content}</article>
            </div>
          ) : (
            <p className="empty">点击答案中的引用编号，查看对应章节。</p>
          )}
        </aside>
      </div>
    </div>
  );
}

function AnswerText({
  answer,
  citations,
  activeKey,
  turnIndex,
  onOpen,
}: {
  answer: string;
  citations: Citation[];
  activeKey: string | null;
  turnIndex: number;
  onOpen: (turnIndex: number, citation: Citation) => void;
}) {
  const parts = answer.split(/(\[\d+\])/g);
  return (
    <p className="answer">
      {parts.map((part, index) => {
        const matched = part.match(/^\[(\d+)\]$/);
        if (!matched) {
          return <span key={index}>{part}</span>;
        }
        const number = Number(matched[1]);
        const citation = citations.find((item) => item.number === number);
        if (!citation) {
          return <span key={index}>{part}</span>;
        }
        return (
          <button
            key={index}
            type="button"
            className={activeKey === `${turnIndex}-${number}` ? "ref active" : "ref"}
            onClick={() => onOpen(turnIndex, citation)}
          >
            {part}
          </button>
        );
      })}
    </p>
  );
}
