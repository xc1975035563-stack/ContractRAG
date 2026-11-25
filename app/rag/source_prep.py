"""把 data/sources 里的示范合同整理成可入库的 Markdown。

缺页、空章节、重复条款记入报告；无法解析的文件带上失败原因，不悄悄丢掉。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
_CLAUSE = re.compile(r"^第([一二三四五六七八九十百零]+)([章条])\s*(.*)$")
_PAGE = re.compile(r"第\s*(\d{1,3})\s*页")
_DIGITS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


@dataclass(frozen=True)
class SourceSpec:
    filename: str
    document_name: str
    doc_type: str
    required: bool = True


@dataclass
class PrepareNote:
    source: str
    level: str
    reason: str


@dataclass
class PreparedDocument:
    document_name: str
    doc_type: str
    markdown: str
    output_name: str


@dataclass
class PrepareReport:
    documents: list[PreparedDocument] = field(default_factory=list)
    notes: list[PrepareNote] = field(default_factory=list)
    failures: list[PrepareNote] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(item.level == "fail" and _required_failure(item) for item in self.failures)


def _required_failure(note: PrepareNote) -> bool:
    return not note.reason.startswith("非必需")


def prepare_sources(source_dir: Path, specs: list[SourceSpec]) -> PrepareReport:
    report = PrepareReport()
    if not source_dir.is_dir():
        report.failures.append(PrepareNote(str(source_dir), "fail", "源目录不存在，无法整理地产合同"))
        return report
    for spec in specs:
        path = source_dir / spec.filename
        try:
            text = _read_source(path)
            markdown, notes = _clean_contract(text, spec.document_name)
        except PrepareError as exc:
            prefix = "" if spec.required else "非必需文件。"
            report.failures.append(PrepareNote(spec.filename, "fail", prefix + str(exc)))
            continue
        report.notes.extend(PrepareNote(spec.filename, note[0], note[1]) for note in notes)
        report.documents.append(
            PreparedDocument(
                document_name=spec.document_name,
                doc_type=spec.doc_type,
                markdown=markdown,
                output_name=f"{spec.document_name}.md",
            )
        )
    return report


class PrepareError(Exception):
    pass


def _read_source(path: Path) -> str:
    if not path.is_file():
        raise PrepareError(f"文件不存在：{path.name}")
    raw = path.read_bytes()
    if not raw.strip():
        raise PrepareError(f"文件是空的：{path.name}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PrepareError(f"无法按 UTF-8 解析：{path.name}（{exc.reason}）") from exc


def _clean_contract(text: str, title: str) -> tuple[str, list[tuple[str, str]]]:
    notes: list[tuple[str, str]] = []
    for missing in _missing_pages(text):
        notes.append(("skip", f"缺页：未找到第 {missing} 页，已跳过该页检查并记录"))
    lines = text.splitlines()
    sections, preamble = _sections(lines)
    if preamble.strip():
        notes.append(("skip", "正文开始前的站点说明已跳过，不入库"))
    if not sections:
        raise PrepareError("无法解析：没有章节标题（需要 Markdown 标题，或“第×章 / 第×条”）")

    kept: list[tuple[str, str, str]] = []
    seen: dict[str, str] = {}
    for level, heading, body in sections:
        stripped = body.strip()
        if len(stripped) < 8:
            if "条" in heading and len(heading) >= 12:
                stripped = heading
            else:
                notes.append(("skip", f"空章节已跳过：{heading}"))
                continue
        digest = hashlib.sha256(_normalize(stripped).encode("utf-8")).hexdigest()
        if digest in seen:
            notes.append(("duplicate", f"重复条款已跳过：{heading}（与 {seen[digest]} 正文相同）"))
            continue
        seen[digest] = heading
        kept.append((level, heading, stripped))

    for gap in _chapter_gaps(sections):
        notes.append(("skip", f"章节编号不连续，缺少第{gap}章，已记录"))

    if not kept:
        raise PrepareError("无法解析：标题下没有可入库的正文")

    chunks = [f"# {title}", ""]
    for level, heading, body in kept:
        chunks.append(f"{level} {heading}")
        chunks.append("")
        chunks.append(body)
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n", notes


def _sections(lines: list[str]) -> tuple[list[tuple[str, str, str]], str]:
    markdown = [line for line in lines if _HEADING.match(line)]
    use_markdown = len(markdown) >= 2
    sections: list[tuple[str, str, str]] = []
    preamble: list[str] = []
    current: tuple[str, str, list[str]] | None = None
    started = False
    for line in lines:
        heading = _heading_of(line, use_markdown)
        if heading is None:
            if current is None:
                preamble.append(line)
            else:
                current[2].append(line)
            continue
        started = True
        if current is not None:
            sections.append((current[0], current[1], "\n".join(current[2])))
        current = (heading[0], heading[1], [])
    if current is not None:
        sections.append((current[0], current[1], "\n".join(current[2])))
    if not started:
        return [], "\n".join(preamble)
    return sections, "\n".join(preamble)


def _heading_of(line: str, use_markdown: bool) -> tuple[str, str] | None:
    stripped = line.strip()
    if use_markdown:
        matched = _HEADING.match(stripped)
        if matched is None:
            return None
        return matched.group(1), matched.group(2).strip()
    matched = _CLAUSE.match(stripped)
    if matched is None:
        return None
    level = "##" if matched.group(2) == "章" else "###"
    title = f"第{matched.group(1)}{matched.group(2)}"
    rest = matched.group(3).strip()
    if rest:
        title = f"{title} {rest}"
    return level, title


def _missing_pages(text: str) -> list[int]:
    numbers = [int(item) for item in _PAGE.findall(text)]
    if len(numbers) < 2:
        return []
    found = set(numbers)
    return [page for page in range(min(found), max(found) + 1) if page not in found]


def _chapter_gaps(sections: list[tuple[str, str, str]]) -> list[str]:
    numbers: list[int] = []
    for _level, heading, _body in sections:
        matched = re.search(r"第([一二三四五六七八九十零]+)章", heading)
        if matched is None:
            continue
        value = _chinese_number(matched.group(1))
        if value is not None:
            numbers.append(value)
    if len(numbers) < 2:
        return []
    missing: list[str] = []
    for start, end in zip(numbers, numbers[1:]):
        for gap in range(start + 1, end):
            missing.append(_chinese(gap))
    return missing


def _chinese_number(text: str) -> int | None:
    if text == "十":
        return 10
    if "十" not in text:
        if len(text) != 1:
            return None
        return _DIGITS.get(text)
    left, right = text.split("十", 1)
    tens = 1 if left == "" else _DIGITS.get(left)
    ones = 0 if right == "" else _DIGITS.get(right)
    if tens is None or ones is None:
        return None
    return tens * 10 + ones


def _chinese(value: int) -> str:
    names = "零一二三四五六七八九"
    if value <= 10:
        return "十" if value == 10 else names[value]
    if value < 20:
        return "十" + names[value - 10]
    tens, ones = divmod(value, 10)
    return names[tens] + "十" + (names[ones] if ones else "")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)
