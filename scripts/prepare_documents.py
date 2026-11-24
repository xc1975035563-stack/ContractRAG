"""确认目录中的合同 Markdown 已经备好。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "catalog.json"


def main() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    for item in catalog:
        target = ROOT / item["path"]
        if not target.is_file():
            raise SystemExit(f"缺少合同文件：{item['path']}")
        size = len(target.read_text(encoding="utf-8"))
        print(f"{item['kb_name']} / {item['document_name']} -> {item['path']} ({size} 字)")


if __name__ == "__main__":
    main()
