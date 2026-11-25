"""检查咨询边界。规则写死，不调用模型，也不能当成线上准确率。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.policy import classify_intent, risk_flags, screen_question

CASES = [
    ("起草", "estate", "帮我起草一份租赁合同", "draft", None, None),
    ("诉讼", "estate", "业主欠费怎么起诉", "advice", None, None),
    ("废止", "estate", "2019版物业服务收费说明里物业费是多少", "superseded", None, None),
    ("押金", "estate", "押金什么时候退", None, "费用", "deposit"),
    ("权属", "estate", "办不出房产证怎么处理", None, "权属", "title"),
    ("电商", "qinghe", "帮我写一份入驻协议", "draft", None, None),
]


def main() -> None:
    failed = 0
    for name, kb_id, question, expect_code, expect_intent, expect_risk in CASES:
        refusal = screen_question(kb_id, question)
        code = refusal.code if refusal else None
        intent = classify_intent(question)
        risks = {item.code for item in risk_flags(question, [])}
        problems: list[str] = []
        if code != expect_code:
            problems.append(f"拒答 {code}，期望 {expect_code}")
        if expect_intent and intent != expect_intent:
            problems.append(f"意图 {intent}，期望 {expect_intent}")
        if expect_risk and expect_risk not in risks:
            problems.append(f"缺少风险 {expect_risk}")
        if problems:
            failed += 1
            print(f"FAIL {name} " + "；".join(problems))
        else:
            print(f"PASS {name}")
    print(f"业务规则 {len(CASES) - failed}/{len(CASES)} 通过。这不是线上准确率。")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
