"""HTML 강의안 → 구조화 텍스트(슬라이드/섹션 단위) 추출기.

표준 라이브러리만 사용한다. base64 이미지·style·script를 먼저 걷어내고,
슬라이드(class에 slide/page 포함 또는 <section>) 단위로 제목과 본문을 모은다.
슬라이드 구조가 없는 문서는 h1/h2 제목 기준으로 나눈다.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

DATA_URI = re.compile(r"data:[a-z0-9.+/-]+;base64,[A-Za-z0-9+/=\s]+", re.I)
DROP_BLOCKS = re.compile(r"<(style|script|noscript|template)\b[^>]*>.*?</\1\s*>", re.S | re.I)
COMMENTS = re.compile(r"<!--.*?-->", re.S)

UNIT_CLASS = re.compile(r"(^|[\s_-])(slide|page|sheet|chapter)([\s_-]|$)", re.I)
HEADINGS = {"h1", "h2", "h3", "h4"}
BLOCK_TAGS = {
    "p", "div", "li", "tr", "td", "th", "br", "section", "article", "h1", "h2", "h3",
    "h4", "h5", "h6", "ul", "ol", "table", "header", "footer", "blockquote", "pre", "dt", "dd",
    "text", "tspan", "figcaption", "caption", "summary",
}
VOID = {"br", "img", "hr", "meta", "link", "input", "source", "col", "area", "base", "wbr", "embed", "param", "track"}
TITLE_CLASS = re.compile(r"(^|[\s_-])(title|ttl|headline|hd|heading|h1|h2)([\s_-]|$)", re.I)


def clean_html(raw: str) -> str:
    raw = DATA_URI.sub("", raw)
    raw = COMMENTS.sub("", raw)
    raw = DROP_BLOCKS.sub(" ", raw)
    return raw


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.stack: list[tuple[str, bool, bool]] = []  # (tag, opens_unit, is_heading)
        self.unit_depth = 0
        self.units: list[dict] = []
        self.cur: dict | None = None
        self.loose: list[dict] = []  # 슬라이드 밖 텍스트 (heading 기준 분할용)
        self._heading_buf: list[str] | None = None
        self._heading_tag = ""

    # -- helpers
    def _target(self) -> dict:
        if self.cur is not None:
            return self.cur
        if not self.loose:
            self.loose.append({"heading": "", "headings": [], "text": []})
        return self.loose[-1]

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
            return
        if tag in VOID:
            if tag == "br":
                self._target()["text"].append("\n")
            return
        cls = ""
        for k, v in attrs:
            if k == "class" and v:
                cls = v
        opens = False
        if self.cur is None and (tag == "section" or (cls and UNIT_CLASS.search(cls))):
            opens = True
            self.cur = {"heading": "", "headings": [], "text": []}
        is_head = tag in HEADINGS or (bool(cls) and bool(TITLE_CLASS.search(cls)) and tag in {"div", "p", "span"})
        if is_head and self._heading_buf is None:
            self._heading_buf = []
            self._heading_tag = tag
            is_head = True
        else:
            is_head = False
        if tag in BLOCK_TAGS:
            self._target()["text"].append("\n")
        self.stack.append((tag, opens, is_head))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
            return
        if tag in VOID:
            return
        # pop up to matching tag (HTML은 종종 닫는 태그가 어긋난다)
        idx = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                idx = i
                break
        if idx is None:
            return
        popped = self.stack[idx:]
        del self.stack[idx:]
        for t, opens, is_head in reversed(popped):
            if is_head and self._heading_buf is not None:
                h = _norm(" ".join(self._heading_buf))
                self._heading_buf = None
                if h:
                    tgt = self._target()
                    if self.cur is None and t in {"h1", "h2"}:
                        # 슬라이드 구조 없는 문서: h1/h2가 새 섹션을 연다
                        self.loose.append({"heading": h, "headings": [h], "text": []})
                    else:
                        tgt["headings"].append(h)
                        if not tgt["heading"]:
                            tgt["heading"] = h
            if t in BLOCK_TAGS:
                self._target()["text"].append("\n")
            if opens and self.cur is not None:
                self.units.append(self.cur)
                self.cur = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if not data.strip():
            return
        if self._heading_buf is not None:
            self._heading_buf.append(data)
        self._target()["text"].append(data)


def _norm(s: str) -> str:
    s = html.unescape(s)
    s = re.sub(r"[ \t ​]+", " ", s)
    return s.strip()


def _text(parts: list[str]) -> str:
    s = "".join(parts)
    s = html.unescape(s)
    s = re.sub(r"[ \t ​]+", " ", s)
    lines = [ln.strip() for ln in s.split("\n")]
    out: list[str] = []
    for ln in lines:
        if not ln:
            continue
        # 한 글자짜리 조각(번호·화살표)은 앞줄에 붙인다
        if out and (len(ln) <= 2 or len(out[-1]) <= 2):
            out[-1] = out[-1] + " " + ln
        else:
            out.append(ln)
    return "\n".join(out)


SCRIPT_BODY = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script\s*>", re.S | re.I)
STR_LIT = re.compile(r"'((?:\\.|[^'\\\n])*)'|\"((?:\\.|[^\"\\\n])*)\"|`((?:\\.|[^`\\])*)`", re.S)
HANGUL = re.compile(r"[가-힣]")
# 슬라이드 경계로 보는 패턴: base(s,'섹션','제목',...) 같은 렌더 함수 호출, 또는 {title:'...'} 객체
BOUND = re.compile(r"\b(?:base|chapterGate|chapter|cover|gate|slide|addSlide|makeSlide|section)\s*\(\s*\w+\s*,"
                   r"|\b(?:title|heading|h1)\s*:")


def _script_sections(raw_html: str, max_chars: int) -> list[dict]:
    """본문을 JS가 그리는 문서(SVG 강의안 등): 스크립트 안 한글 문자열로 슬라이드를 복원한다."""
    js = "\n".join(SCRIPT_BODY.findall(DATA_URI.sub("", raw_html)))
    if not js:
        return []
    lits = []
    for m in STR_LIT.finditer(js):
        v = m.group(1) or m.group(2) or m.group(3) or ""
        if not HANGUL.search(v):
            continue
        v = re.sub(r"\$\{[^}]*\}", " ", v)
        v = re.sub(r"<[^>]+>", " ", v)
        v = v.replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"')
        v = _norm(v)
        if len(v) >= 2:
            lits.append((m.start(), v))
    if not lits:
        return []
    freq: dict[str, int] = {}
    for _, v in lits:
        freq[v] = freq.get(v, 0) + 1
    lits = [(p, v) for p, v in lits if freq[v] <= 3]  # 머리글·바닥글 같은 반복 문구 제거
    bounds = [m.start() for m in BOUND.finditer(js)]
    groups: list[list[str]] = []
    if len(bounds) >= 3:
        bi, cur = 0, None
        for p, v in lits:
            while bi < len(bounds) and bounds[bi] <= p:
                bi += 1
                cur = []
                groups.append(cur)
            if cur is None:
                cur = []
                groups.append(cur)
            cur.append(v)
    else:
        for i in range(0, len(lits), 10):
            groups.append([v for _, v in lits[i:i + 10]])
    out = []
    for g in groups:
        g = [x for x in g if x]
        if not g or sum(map(len, g)) < 15:
            continue
        # base(s, 섹션, 제목, …) 형태면 두 번째 문자열이 제목
        head = g[1] if len(g) > 1 and len(g[0]) <= 24 and len(g[1]) > len(g[0]) else g[0]
        out.append({"heading": head[:160], "headings": [head[:160]], "text": "\n".join(g)[:max_chars]})
    return out


def extract(raw_html: str, max_units: int = 200, max_chars: int = 1200) -> dict:
    """HTML 문자열 → {title, sections:[{heading, headings, text}], full_text_len}"""
    r = _extract_dom(raw_html, max_units, max_chars)
    if r["text_len"] < 2000:
        js = _script_sections(raw_html, max_chars)
        js_len = sum(len(s["text"]) for s in js)
        if js_len > max(2 * r["text_len"], 400):
            r["sections"] = js[:max_units]
            r["text_len"] = js_len
            r["from_script"] = True
    return r


def _extract_dom(raw_html: str, max_units: int, max_chars: int) -> dict:
    cleaned = clean_html(raw_html)
    p = _Collector()
    try:
        p.feed(cleaned)
        p.close()
    except Exception:  # 깨진 HTML이어도 가능한 만큼은 살린다
        pass
    if p.cur is not None:
        p.units.append(p.cur)
    units = p.units
    # 슬라이드가 2개 미만이면 heading 기반 분할 결과를 사용
    if len(units) < 2:
        units = units + p.loose
    sections = []
    seen = set()
    total = 0
    for u in units:
        text = _text(u["text"])
        if len(text) < 15:
            continue
        key = text[:200]
        if key in seen:  # 반복 템플릿(내비게이션 등) 제거
            continue
        seen.add(key)
        total += len(text)
        heading = u["heading"] or text.split("\n", 1)[0][:80]
        sections.append({
            "heading": heading[:160],
            "headings": [h[:160] for h in u["headings"][:8]],
            "text": text[:max_chars],
        })
        if len(sections) >= max_units:
            break
    return {"title": _norm(p.title), "sections": sections, "text_len": total}


if __name__ == "__main__":
    import json
    import sys

    raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    r = extract(raw)
    print(json.dumps({"title": r["title"], "n": len(r["sections"]), "text_len": r["text_len"],
                      "first": r["sections"][:3]}, ensure_ascii=False, indent=1))
