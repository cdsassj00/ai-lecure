"""강의안 HTML 폴더 → 지식그래프 빌드.

사용법
  # 1) 로컬 PC: 구글 드라이브 동기화 폴더를 직접 읽는다 (가장 완전함)
  python kg/build.py --src "G:/내 드라이브/강의안/01_강의관련"

  # 2) 클라우드 세션: Drive에서 받은 <fileId>.html 묶음을 읽는다
  python kg/build.py --raw /path/to/raw

  두 옵션은 함께 쓸 수 있다. data/drive_manifest.json 에 있는 모든 파일은
  본문이 없어도 '제목만 있는 문서' 노드로 그래프에 들어간다.

산출물 (graph/)
  graph.json     : 노드·엣지 (뷰어·쿼리용)
  documents.json : 문서 카드 (유형·고객사·개념·목차·버전)
  chunks.jsonl   : 슬라이드/섹션 단위 본문 (검색·재활용용)
  INDEX.md       : 사람과 Claude가 바로 읽는 카탈로그
  viewer.html    : 브라우저에서 여는 인터랙티브 그래프
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import extract  # noqa: E402
from vocab import CLIENTS, CONCEPTS, DOC_TYPES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "drive_manifest.json"
OUT = ROOT / "graph"
DRIVE_URL = "https://drive.google.com/file/d/{}/view"

# ───────────────────────── 이름 정규화 ─────────────────────────

def family_key(title: str) -> str:
    """버전·사본 표기를 떼어 같은 강의안 계열을 묶는 키."""
    s = re.sub(r"\.html?$", "", title, flags=re.I)
    s = re.sub(r"\s*\(\d+\)", "", s)
    s = re.sub(r"__\d+$", "", s)
    s = re.sub(r"__Downloads$", "", s)
    s = re.sub(r"[_ -]?(v\d+(\.\d+)?|final|최종|수정|수수정|edited|copy)$", "", s, flags=re.I)
    return s.strip(" _-")


def date_from(title: str, modified: str | None) -> str | None:
    m = re.search(r"(20\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?([0-3]\d)", title)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return (modified or "")[:10] or None


def doc_type(title: str, page_title: str) -> str:
    for name, pat in DOC_TYPES:
        if re.search(pat, title, re.I):
            return name
    for name, pat in DOC_TYPES:
        if page_title and re.search(pat, page_title, re.I):
            return name
    return "기타"


# ───────────────────────── 개념 매칭 ─────────────────────────

def _compile(term: str) -> re.Pattern:
    t = term.strip()
    if re.fullmatch(r"[A-Z0-9.]{2,5}", t):  # 약어는 대소문자 구분 + 경계
        return re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])")
    if re.fullmatch(r"[A-Za-z0-9 .\-]+", t):
        return re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", re.I)
    return re.compile(re.escape(t), re.I)


CONCEPT_PATTERNS = {name: [_compile(s) for s in syns] for name, (_, syns) in CONCEPTS.items()}
CLIENT_PATTERNS = {name: [_compile(s) for s in syns] for name, syns in CLIENTS.items()}


def count_concepts(text: str) -> Counter:
    c: Counter = Counter()
    for name, pats in CONCEPT_PATTERNS.items():
        n = sum(len(p.findall(text)) for p in pats)
        if n:
            c[name] = n
    return c


def match_clients(title: str, text: str) -> list[str]:
    found = []
    for name, pats in CLIENT_PATTERNS.items():
        if any(p.search(title) for p in pats):
            found.append(name)
    if not found and text:
        head = text[:4000]
        for name, pats in CLIENT_PATTERNS.items():
            if name in ("CDSA",):
                continue
            if sum(len(p.findall(head)) for p in pats) >= 2:
                found.append(name)
    return found


# ───────────────────────── 키워드 (제목·헤딩 기반) ─────────────────────────
JOSA = re.compile(r"(습니다|입니다|합니다|됩니다|으로써|으로서|에서는|이라는|에게서|으로|에서|에게|까지|부터|처럼|보다|이란|이며|하고|하는|하기|했다|한다|입니다|합니다|과|와|은|는|이|가|을|를|의|에|로|도|만)$")
STOP = set("""아니라 하나 있습니다 다른 따라 맡기 그리고 하지만 때문 위해 같은 이렇게 먼저 함께 모든 각각 가장 바로 직접 실제
이상 이하 여기 지금 이제 우선 정도 부분 결과 문제 이유 그대로 하나씩 만들기 만들 무엇을 어디 언제 누가 해야 해야합니다 이런 그런
강의 강의안 교안 슬라이드 페이지 목차 개요 소개 정리 요약 실습 예시 예제 방법 단계 사례 활용 이해 기본 핵심 주요 전체
구성 내용 과정 시간 오늘 우리 이번 다음 이것 그것 무엇 어떻게 위한 대한 통한 있는 없는 하는 되는 경우 사용 이용 필요
the and for with from this that into your you are our what how why version final html page slide""".split())


def tokens(s: str) -> list[str]:
    out = []
    for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]{2,}|[가-힣]{2,}", s):
        w = w.strip(".-")
        if re.match(r"[가-힣]", w):
            w = JOSA.sub("", w)
            if len(w) < 2:
                continue
        else:
            w = w.lower()
        if w in STOP or w.isdigit():
            continue
        out.append(w)
    return out


# ───────────────────────── 로딩 ─────────────────────────

def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        return []
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]


def read_html(path: Path) -> str:
    b = path.read_bytes()
    for enc in ("utf-8-sig", "cp949", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def collect(src_dirs: list[Path], raw_dirs: list[Path]) -> list[dict]:
    manifest = load_manifest()
    by_title = {f["title"]: f for f in manifest}
    by_id = {f["id"]: f for f in manifest}
    files: dict[str, dict] = {}
    for f in manifest:
        files[f["id"]] = {"id": f["id"], "title": f["title"], "modified": f.get("modifiedTime"),
                          "size": int(f.get("fileSize") or 0), "path": None, "drive": True}
    for d in raw_dirs:
        for p in d.glob("*.html"):
            fid = p.stem
            if fid in files:  # 매니페스트(강의 폴더)에 있는 파일만 받는다
                files[fid]["path"] = p
    for d in src_dirs:
        for p in d.rglob("*.htm*"):
            meta = by_title.get(p.name)
            if meta:
                files[meta["id"]]["path"] = p
            else:
                fid = "local-" + hashlib.sha1(p.name.encode()).hexdigest()[:12]
                from datetime import datetime, timezone
                mt = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat()
                files[fid] = {"id": fid, "title": p.name, "modified": mt, "size": p.stat().st_size,
                              "path": p, "drive": False}
    return list(files.values())


# ───────────────────────── 빌드 ─────────────────────────

def build(src_dirs: list[Path], raw_dirs: list[Path], max_chunk_chars: int) -> None:
    files = collect(src_dirs, raw_dirs)
    fams: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        fams[family_key(f["title"])].append(f)

    prev_secs, prev_meta = load_previous()
    docs: list[dict] = []
    chunks: list[dict] = []
    for fam, members in sorted(fams.items()):
        # 원본 파일이 있거나, 이전 빌드에서 본문을 색인해 둔 판을 우선한다
        members.sort(key=lambda f: (f["path"] is not None or f["id"] in prev_secs,
                                    f["modified"] or "", f["size"]), reverse=True)
        canon = members[0]
        rec = {
            "id": canon["id"], "title": canon["title"], "family": fam,
            "modified": canon["modified"], "size": canon["size"],
            "url": DRIVE_URL.format(canon["id"]) if canon["drive"] else None,
            "versions": [{"id": m["id"], "title": m["title"], "modified": m["modified"]} for m in members[1:]],
        }
        page_title, sections, text_all = "", [], ""
        indexed = None
        if canon["path"] is not None:
            try:
                ex = extract(read_html(canon["path"]), max_chars=max_chunk_chars)
                page_title, sections = ex["title"], ex["sections"]
                indexed = canon["modified"]
            except Exception as e:  # noqa: BLE001
                print("  ! extract 실패", canon["title"], e, file=sys.stderr)
        elif canon["id"] in prev_secs:  # 증분 빌드: 원본이 없으면 이전 색인 본문을 그대로 쓴다
            pm = prev_meta.get(canon["id"], {})
            page_title, sections, indexed = pm.get("page_title", ""), prev_secs[canon["id"]], pm.get("indexed_modified")
        text_all = "\n".join(s["heading"] + "\n" + s["text"] for s in sections)
        title_text = fam.replace("_", " ") + " " + page_title
        cc = count_concepts(text_all)
        tc = count_concepts(title_text)
        concepts = Counter()
        for k, v in cc.items():
            if v >= 2:
                concepts[k] += v
        for k, v in tc.items():
            concepts[k] += 5 * v  # 제목에 나온 개념은 가중치를 크게
        rec.update({
            "page_title": page_title,
            "doc_type": doc_type(canon["title"], page_title),
            "clients": match_clients(canon["title"] + " " + page_title, text_all),
            "date": date_from(canon["title"], canon["modified"]),
            "has_content": bool(sections),
            "indexed_modified": indexed if sections else None,
            "n_sections": len(sections),
            "text_chars": len(text_all),
            "concepts": dict(concepts.most_common(15)),
            "outline": [s["heading"] for s in sections][:80],
            "summary": _summary(sections),
        })
        rec["_tok"] = Counter(tokens(title_text + " " + " ".join(rec["outline"])))
        docs.append(rec)
        for i, s in enumerate(sections):
            sc = count_concepts(s["heading"] + "\n" + s["text"])
            chunks.append({"doc": rec["id"], "i": i, "heading": s["heading"], "text": s["text"],
                           "concepts": [k for k, _ in sc.most_common(6)]})

    # 키워드: 문서빈도 2 이상, 전체의 25% 이하인 제목/헤딩 토큰의 TF-IDF 상위
    N = len(docs)
    df = Counter()
    for d in docs:
        df.update(set(d["_tok"]))
    for d in docs:
        scored = [(w, tf * math.log(N / df[w])) for w, tf in d["_tok"].items() if 2 <= df[w] <= max(3, N * 0.25)]
        d["keywords"] = [w for w, _ in sorted(scored, key=lambda x: -x[1])[:10]]
        del d["_tok"]

    graph = make_graph(docs)
    OUT.mkdir(exist_ok=True)
    (OUT / "documents.json").write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
    with (OUT / "chunks.jsonl").open("w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    (OUT / "graph.json").write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    (OUT / "INDEX.md").write_text(make_index(docs, graph), encoding="utf-8")
    (OUT / "viewer.html").write_text(
        '<!doctype html>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + viewer_body(graph, docs), encoding="utf-8")
    with_c = sum(d["has_content"] for d in docs)
    print(f"파일 {len(files)}개 → 문서(계열) {len(docs)}개, 본문 확보 {with_c}개, 섹션 {len(chunks)}개")
    print(f"노드 {len(graph['nodes'])}개, 엣지 {len(graph['edges'])}개 → {OUT}")


def load_previous() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """이전 빌드의 섹션 본문을 읽어 둔다 (원본이 없는 환경에서 다시 빌드해도 색인이 유지되도록)."""
    secs: dict[str, list[dict]] = defaultdict(list)
    meta: dict[str, dict] = {}
    cp, dp = OUT / "chunks.jsonl", OUT / "documents.json"
    if cp.exists():
        for line in cp.open(encoding="utf-8"):
            c = json.loads(line)
            secs[c["doc"]].append({"heading": c["heading"], "headings": [c["heading"]], "text": c["text"]})
    if dp.exists():
        for d in json.loads(dp.read_text(encoding="utf-8")):
            meta[d["id"]] = {"page_title": d.get("page_title", ""),
                             "indexed_modified": d.get("indexed_modified", d.get("modified"))}
    return secs, meta


def viewer_body(graph: dict, docs: list[dict]) -> str:
    """뷰어 템플릿에 그래프와 문서 카드(요약본)를 끼워 넣는다."""
    payload = dict(graph)
    payload["docs"] = {
        d["id"]: {
            "title": d["title"], "page_title": d["page_title"], "clients": d["clients"],
            "summary": d["summary"], "keywords": d["keywords"], "outline": d["outline"][:40],
            "versions": len(d["versions"]),
        } for d in docs
    }
    tpl = (Path(__file__).parent / "viewer_template.html").read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return tpl.replace("/*__GRAPH__*/null", data)


def _summary(sections: list[dict]) -> str:
    for s in sections[:4]:
        lines = [ln for ln in s["text"].split("\n") if len(ln) >= 20]
        if lines:
            return " / ".join(lines[:2])[:280]
    return ""


def make_graph(docs: list[dict]) -> dict:
    nodes, edges = [], []
    used_concepts: Counter = Counter()
    for d in docs:
        nodes.append({"id": "doc:" + d["id"], "type": "document", "label": d["family"][:60],
                      "doc_type": d["doc_type"], "date": d["date"], "has_content": d["has_content"],
                      "url": d["url"], "n": d["n_sections"]})
        for c, w in d["concepts"].items():
            edges.append({"s": "doc:" + d["id"], "t": "concept:" + c, "type": "다룸", "w": w})
            used_concepts[c] += 1
        for cl in d["clients"]:
            edges.append({"s": "doc:" + d["id"], "t": "client:" + cl, "type": "고객사", "w": 1})
        edges.append({"s": "doc:" + d["id"], "t": "type:" + d["doc_type"], "type": "유형", "w": 1})
    for c, n in used_concepts.items():
        cat = CONCEPTS[c][0]
        nodes.append({"id": "concept:" + c, "type": "concept", "label": c, "category": cat, "docs": n})
        edges.append({"s": "concept:" + c, "t": "category:" + cat, "type": "분류", "w": 1})
    for cat in sorted({CONCEPTS[c][0] for c in used_concepts}):
        nodes.append({"id": "category:" + cat, "type": "category", "label": cat})
    for cl in sorted({cl for d in docs for cl in d["clients"]}):
        nodes.append({"id": "client:" + cl, "type": "client", "label": cl,
                      "docs": sum(cl in d["clients"] for d in docs)})
    for t in sorted({d["doc_type"] for d in docs}):
        nodes.append({"id": "type:" + t, "type": "doctype", "label": t,
                      "docs": sum(d["doc_type"] == t for d in docs)})

    # 개념 공출현
    co: Counter = Counter()
    for d in docs:
        cs = sorted(d["concepts"])
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                co[(cs[i], cs[j])] += 1
    for (a, b), n in co.items():
        if n >= 3:
            edges.append({"s": "concept:" + a, "t": "concept:" + b, "type": "함께 등장", "w": n})

    # 유사 문서 (개념 가중치 + 키워드 코사인), 문서당 상위 4개
    vecs = {}
    for d in docs:
        v = {("c", k): math.log1p(w) for k, w in d["concepts"].items()}
        v.update({("k", k): 0.8 for k in d.get("keywords", [])})
        vecs[d["id"]] = (v, math.sqrt(sum(x * x for x in v.values())) or 1.0)
    ids = [d["id"] for d in docs if d["concepts"]]
    inv = defaultdict(list)
    for i in ids:
        for k in vecs[i][0]:
            inv[k].append(i)
    seen = set()
    for i in ids:
        vi, ni = vecs[i]
        scores: Counter = Counter()
        for k, x in vi.items():
            if len(inv[k]) > len(ids) * 0.4:
                continue
            for j in inv[k]:
                if j != i:
                    scores[j] += x * vecs[j][0][k]
        for j, s in scores.most_common(4):
            sim = s / (ni * vecs[j][1])
            key = tuple(sorted((i, j)))
            if sim >= 0.35 and key not in seen:
                seen.add(key)
                edges.append({"s": "doc:" + i, "t": "doc:" + j, "type": "유사", "w": round(sim, 3)})
    return {"nodes": nodes, "edges": edges}


def make_index(docs: list[dict], graph: dict) -> str:
    by_id = {d["id"]: d for d in docs}
    L = ["# 강의안 지식그래프 인덱스", "",
         f"- 문서(버전 묶음 기준) {len(docs)}개 · 본문 색인 {sum(d['has_content'] for d in docs)}개 · "
         f"원본 파일 {sum(1 + len(d['versions']) for d in docs)}개",
         "- 검색: `python kg/query.py search \"키워드\"` · 재료팩: `python kg/query.py pack \"새 강의 주제\"`",
         "- 문서 링크는 Google Drive 원본입니다. Claude는 Drive 커넥터로 fileId를 열어 원문을 볼 수 있습니다.", ""]
    L += ["## 개념별 문서", ""]
    concept_docs = defaultdict(list)
    for d in docs:
        for c, w in d["concepts"].items():
            concept_docs[c].append((w, d))
    for cat in dict.fromkeys(v[0] for v in CONCEPTS.values()):
        cs = [c for c, v in CONCEPTS.items() if v[0] == cat and c in concept_docs]
        if not cs:
            continue
        L.append(f"### {cat}")
        for c in sorted(cs, key=lambda c: -len(concept_docs[c])):
            top = sorted(concept_docs[c], key=lambda x: -x[0])[:8]
            L.append(f"- **{c}** ({len(concept_docs[c])}) — " + ", ".join(f"`{d['family'][:40]}`" for _, d in top))
        L.append("")
    L += ["## 고객사별 문서", ""]
    cl = defaultdict(list)
    for d in docs:
        for c in d["clients"]:
            cl[c].append(d)
    for c, ds in sorted(cl.items(), key=lambda x: -len(x[1])):
        L.append(f"- **{c}** ({len(ds)}) — " + ", ".join(f"`{d['family'][:40]}`" for d in sorted(ds, key=lambda d: d['date'] or '', reverse=True)[:12]))
    L += ["", "## 문서 목록 (유형 → 최신순)", ""]
    types = defaultdict(list)
    for d in docs:
        types[d["doc_type"]].append(d)
    for t, ds in sorted(types.items(), key=lambda x: -len(x[1])):
        L.append(f"### {t} ({len(ds)})")
        L.append("")
        L.append("| 날짜 | 문서 | 섹션 | 주요 개념 | fileId |")
        L.append("|---|---|---:|---|---|")
        for d in sorted(ds, key=lambda d: d["date"] or "", reverse=True):
            cs = ", ".join(list(d["concepts"])[:5])
            name = d["family"].replace("|", "/")[:70]
            if d["versions"]:
                name += f" (+{len(d['versions'])}판)"
            L.append(f"| {d['date'] or ''} | {name} | {d['n_sections'] or '—'} | {cs} | `{d['id']}` |")
        L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", action="append", default=[], help="강의안 HTML 폴더 (여러 번 지정 가능)")
    ap.add_argument("--raw", action="append", default=[], help="<driveFileId>.html 폴더")
    ap.add_argument("--chunk-chars", type=int, default=1200, help="섹션 본문 최대 글자 수")
    a = ap.parse_args()
    src = [Path(p) for p in a.src]
    raw = [Path(p) for p in a.raw]
    if not src and not raw and os.environ.get("LECTURE_DIR"):
        src = [Path(os.environ["LECTURE_DIR"])]
    build(src, raw, a.chunk_chars)


if __name__ == "__main__":
    main()
