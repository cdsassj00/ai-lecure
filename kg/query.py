"""강의안 지식그래프 조회 도구.

  python kg/query.py search "MCP 스킬 차이"        # 슬라이드/섹션 단위 검색 (BM25)
  python kg/query.py pack "공공기관 대상 에이전트 입문 4시간" -o pack.md
                                                   # 새 강의안용 재료팩 (관련 문서·재사용 슬라이드·개념 지도)
  python kg/query.py doc 삼성전자_20260825          # 문서 카드 + 목차 (--full: 섹션 본문까지)
  python kg/query.py concept 하네스                 # 개념 → 관련 문서·함께 다룬 개념
  python kg/query.py client 행정안전부              # 고객사별 문서
  python kg/query.py topics                          # 내용 주제 지도 (대주제 → 소주제, 슬라이드 수)
  python kg/query.py context "MCP" -n 15 -o ctx.md   # 주제/키워드 → 강의안 작성용 컨텍스트 (슬라이드 원문 모음)
  python kg/query.py course [데이터분석]             # 과정 묶음별 강의안 목록
  python kg/query.py stats
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
G = ROOT / "graph"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vocab import CONCEPTS  # noqa: E402

JOSA = re.compile(r"(습니다|입니다|합니다|됩니다|으로써|으로서|에서는|이라는|으로|에서|에게|까지|부터|처럼|보다|이란|과|와|은|는|이|가|을|를|의|에|로|도|만)$")


def load():
    docs = json.loads((G / "documents.json").read_text(encoding="utf-8"))
    chunks = [json.loads(l) for l in (G / "chunks.jsonl").open(encoding="utf-8")]
    graph = json.loads((G / "graph.json").read_text(encoding="utf-8"))
    return {d["id"]: d for d in docs}, chunks, graph


def toks(s: str) -> list[str]:
    s = s.lower()
    out = []
    for w in re.findall(r"[a-z][a-z0-9+#.\-]+|[가-힣]+|\d{2,}", s):
        if re.match(r"[가-힣]", w):
            w2 = JOSA.sub("", w) if len(w) > 2 else w
            if len(w2) >= 2:
                out.append(w2)
            out += [w2[i:i + 2] for i in range(len(w2) - 1)] if len(w2) > 2 else []
        else:
            out.append(w)
    return out


class BM25:
    def __init__(self, texts: list[str], k1=1.4, b=0.7):
        self.k1, self.b = k1, b
        self.tf = [Counter(toks(t)) for t in texts]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = sum(self.len) / max(1, len(self.len))
        df = Counter()
        for c in self.tf:
            df.update(c.keys())
        N = len(texts)
        self.idf = {w: math.log(1 + (N - n + .5) / (n + .5)) for w, n in df.items()}
        self.inv = defaultdict(list)
        for i, c in enumerate(self.tf):
            for w in c:
                self.inv[w].append(i)

    def search(self, q: str, k=20) -> list[tuple[int, float]]:
        sc: Counter = Counter()
        for w in set(toks(q)):
            idf = self.idf.get(w)
            if not idf:
                continue
            for i in self.inv[w]:
                f = self.tf[i][w]
                sc[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return sc.most_common(k)


def find_doc(docs: dict, key: str) -> dict | None:
    if key in docs:
        return docs[key]
    kl = key.lower()
    cands = [d for d in docs.values() if kl in d["title"].lower() or kl in d["family"].lower()
             or kl in (d.get("page_title") or "").lower()]
    cands.sort(key=lambda d: (not d["has_content"], -(d["n_sections"] or 0)))
    return cands[0] if cands else None


def concept_of(q: str) -> list[str]:
    ql = q.lower()
    hits = []
    for name, (_, syns) in CONCEPTS.items():
        if any(s.lower() in ql for s in [name] + syns if len(s) >= 2):
            hits.append(name)
    return hits


def link(d: dict) -> str:
    return d["url"] or "(로컬 전용)"


# ─────────────────────────── commands ───────────────────────────

def cmd_search(a):
    docs, chunks, _ = load()
    bm = BM25([c["heading"] * 2 + "\n" + c["text"] for c in chunks])
    per_doc = Counter()
    n = 0
    for i, s in bm.search(a.query, k=a.k * 4):
        c = chunks[i]
        if per_doc[c["doc"]] >= a.per_doc:
            continue
        per_doc[c["doc"]] += 1
        d = docs[c["doc"]]
        print(f"\n[{s:5.1f}] {d['family']}  §{c['i'] + 1}  ({d['doc_type']}, {d['date']})")
        print(f"   ▸ {c['heading']}")
        body = c["text"].replace("\n", " / ")
        print("     " + body[: a.chars] + ("…" if len(body) > a.chars else ""))
        print(f"     fileId={d['id']}")
        n += 1
        if n >= a.k:
            break
    # 제목만 색인된 문서도 제목으로 찾아준다
    title_hits = [d for d in docs.values() if not d["has_content"]
                  and any(t in d["family"].lower() for t in toks(a.query) if len(t) >= 2 and not re.fullmatch(r"[가-힣]{2}", t) or t == a.query.lower())]
    if title_hits:
        print("\n— 본문 미색인(제목 일치) 문서:")
        for d in title_hits[:10]:
            print(f"   · {d['family']}  fileId={d['id']}")


def cmd_doc(a):
    docs, chunks, graph = load()
    d = find_doc(docs, a.key)
    if not d:
        sys.exit(f"문서를 찾지 못했습니다: {a.key}")
    print(f"# {d.get('page_title') or d['family']}\n")
    print(f"- 파일: {d['title']}  ({d['doc_type']}, {d['date']})")
    print(f"- 고객사: {', '.join(d['clients']) or '—'}")
    print(f"- Drive: {link(d)}   fileId={d['id']}")
    if d["versions"]:
        print(f"- 다른 판 {len(d['versions'])}개: " + ", ".join(v['title'] for v in d['versions'][:8]))
    print(f"- 개념: " + ", ".join(f"{k}({v})" for k, v in d["concepts"].items()))
    print(f"- 키워드: {', '.join(d.get('keywords', []))}")
    if d["summary"]:
        print(f"- 요약: {d['summary']}")
    sims = [e for e in graph["edges"] if e["type"] == "유사" and d["id"] in (e["s"][4:], e["t"][4:])]
    if sims:
        print("- 비슷한 문서: " + ", ".join(
            docs[(e["t"] if e["s"][4:] == d["id"] else e["s"])[4:]]["family"] for e in sims))
    if not d["has_content"]:
        print("\n(본문 미색인 — 로컬에서 `python kg/build.py --src <폴더>` 실행 시 채워집니다. "
              "Claude는 Drive 커넥터의 download_file_content로 fileId를 직접 열 수 있습니다.)")
        return
    print(f"\n## 목차 ({d['n_sections']})")
    secs = [c for c in chunks if c["doc"] == d["id"]]
    for c in secs:
        print(f"{c['i'] + 1:>3}. {c['heading']}")
        if a.full:
            print("     " + c["text"].replace("\n", "\n     "))


def cmd_concept(a):
    docs, _, graph = load()
    names = [n for n in CONCEPTS if a.name.lower() in n.lower()] or concept_of(a.name)
    if not names:
        sys.exit(f"개념 사전에 없습니다: {a.name}  (kg/vocab.py에 추가 가능)")
    for name in names:
        rel = sorted((d for d in docs.values() if name in d["concepts"]), key=lambda d: -d["concepts"][name])
        print(f"\n## {name}  ({CONCEPTS[name][0]}) — 문서 {len(rel)}개")
        co = Counter()
        for d in rel:
            co.update(k for k in d["concepts"] if k != name)
        print("함께 다룬 개념: " + ", ".join(f"{k}({v})" for k, v in co.most_common(10)))
        for d in rel[: a.k]:
            print(f"  · [{d['concepts'][name]:>3}] {d['family']}  ({d['doc_type']}, {d['date']})  fileId={d['id']}")


def cmd_client(a):
    docs, _, _ = load()
    rel = [d for d in docs.values() if any(a.name.lower() in c.lower() for c in d["clients"])]
    rel.sort(key=lambda d: d["date"] or "", reverse=True)
    print(f"## {a.name} — 문서 {len(rel)}개")
    for d in rel:
        print(f"  · {d['date']}  {d['family']}  ({d['doc_type']}, 섹션 {d['n_sections']})  fileId={d['id']}")


def cmd_course(a):
    docs, _, _ = load()
    from vocab import TOPICS
    names = [t[0] for t in TOPICS]
    if not a.name:
        for t in names:
            ds = [d for d in docs.values() if d.get("topic") == t]
            print(f"{len(ds):>4}  {t}")
        return
    hit = [t for t in names if a.name.lower() in t.lower()]
    if not hit:
        sys.exit("주제 목록: " + ", ".join(names))
    for t in hit:
        ds = sorted((d for d in docs.values() if d.get("topic") == t), key=lambda d: d["date"] or "", reverse=True)
        print(f"## {t} — 문서 {len(ds)}개")
        for d in ds:
            print(f"  · {d['date']}  {d['family']}  ({d['doc_type']}, 섹션 {d['n_sections']})  fileId={d['id']}")


def load_topics():
    return json.loads((G / "topics.json").read_text(encoding="utf-8"))


def cmd_topics(a):
    tm = load_topics()
    st = tm["stats"]
    print(f"슬라이드 {st['unique_slides']}장(중복 제거) · 주제 배정 섹션 {st['assigned']}/{st['sections']}")
    for g in tm["groups"]:
        print(f"\n■ {g['name']}")
        for t in sorted(g["subs"], key=lambda t: -t["slides"]):
            print(f"   {t['id']}  {t['name']:<22} 슬라이드 {t['slides']:>4} · 강의안 {t['lectures']:>3}")


def cmd_context(a):
    """주제 이름(또는 id)이나 키워드 → 새 강의안 작성용 컨텍스트 마크다운."""
    docs, _, _ = load()
    tm = load_topics()
    slides = tm["slides"]
    subs = [t for g in tm["groups"] for t in g["subs"]]
    q = a.query.strip()
    hit = [t for t in subs if q == t["id"] or q.replace(" ", "") in t["name"].replace(" ", "")]
    if hit:
        pool, label = [], ", ".join(t["name"] for t in hit)
        for t in hit:
            pool += [slides[n] for n in t["order"]]
    else:
        ql = q.lower()
        pool = [s for s in slides if ql in s["h"].lower() or ql in s["x"].lower()]
        pool.sort(key=lambda s: (ql not in s["h"].lower(), -s["reuse"]))
        label = f"“{q}” 검색"
    per, picked = Counter(), []
    for s in pool:
        if per[s["d"]] >= a.per_doc or s in picked:
            continue
        per[s["d"]] += 1
        picked.append(s)
        if len(picked) >= a.n:
            break
    if not picked:
        sys.exit(f"'{q}'에 해당하는 주제나 슬라이드가 없습니다. `python kg/query.py topics`로 주제 목록을 확인하세요.")
    names = {t["id"]: t["name"] for t in subs}
    L = [f"# 강의 컨텍스트 — {label}", "",
         f"> 기존 강의안 {len(per)}개에서 고른 슬라이드 {len(picked)}장. 원문 발췌이므로 새 대상·시간에 맞게 다시 씁니다.", ""]
    for i, s in enumerate(picked, 1):
        d = docs.get(s["d"], {})
        src = " · ".join(x for x in [d.get("page_title") or d.get("family"), s.get("date"), ", ".join(d.get("clients", []))] if x)
        L += [f"## {i}. {s['h']}", f"- 출처: {src} · fileId `{s['d']}`" + (f" · 강의안 {s['reuse']}개에서 재사용" if s["reuse"] > 1 else ""),
              f"- 주제: {', '.join(names.get(t, t) for t in s['t'])}", "", s["x"].strip(), ""]
    out = "\n".join(L)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
        print(f"컨텍스트 저장: {a.out} (슬라이드 {len(picked)}장, 강의안 {len(per)}개)")
    else:
        print(out)


def cmd_stats(a):
    docs, chunks, graph = load()
    ds = list(docs.values())
    print(f"문서 {len(ds)} (본문 {sum(d['has_content'] for d in ds)}) · 섹션 {len(chunks)} · "
          f"노드 {len(graph['nodes'])} · 엣지 {len(graph['edges'])}")
    print("유형:", dict(Counter(d["doc_type"] for d in ds).most_common()))
    print("개념 상위:", dict(Counter(k for d in ds for k in d["concepts"]).most_common(20)))


def cmd_pack(a):
    """새 강의 주제 → 재료팩(Markdown)."""
    docs, chunks, graph = load()
    q = a.topic
    bm = BM25([c["heading"] * 2 + "\n" + c["text"] for c in chunks])
    hits = bm.search(q, k=400)
    qcon = concept_of(q)
    # 문서 점수 = 상위 섹션 점수 합 + 질의 개념 가중치
    dscore: Counter = Counter()
    dsecs: dict[str, list] = defaultdict(list)
    for i, s in hits:
        c = chunks[i]
        dsecs[c["doc"]].append((s, c))
        if len(dsecs[c["doc"]]) <= 5:
            dscore[c["doc"]] += s
    for d in docs.values():
        for k in qcon:
            if k in d["concepts"]:
                dscore[d["id"]] += 2 * math.log1p(d["concepts"][k])
    top_docs = [docs[i] for i, _ in dscore.most_common(a.docs)]
    # 개념 지도
    con = Counter()
    for d in top_docs:
        for k, v in d["concepts"].items():
            con[k] += math.log1p(v)
    L = [f"# 재료팩: {q}", "",
         f"> 기존 강의안 지식그래프(문서 {len(docs)}개, 섹션 {len(chunks)}개)에서 자동으로 모은 재료입니다. "
         "문장은 원문 발췌이므로 새 강의안에 맞게 다시 쓰고, 필요한 원본은 fileId로 Drive에서 여십시오.", ""]
    if qcon:
        L.append(f"- 질의에서 인식한 개념: {', '.join(qcon)}")
    L.append("- 관련 개념(가중): " + ", ".join(f"{k}" for k, _ in con.most_common(14)))
    L += ["", "## 1. 가장 가까운 기존 강의안", "",
          "| # | 문서 | 유형 | 날짜 | 고객사 | 섹션 | fileId |", "|---:|---|---|---|---|---:|---|"]
    for n, d in enumerate(top_docs, 1):
        L.append(f"| {n} | {d.get('page_title') or d['family']} | {d['doc_type']} · {d.get('topic', '')} | {d['date']} | "
                 f"{', '.join(d['clients']) or '—'} | {d['n_sections']} | `{d['id']}` |")
    L += ["", "## 2. 재사용 후보 슬라이드 (원문 발췌)", ""]
    per = Counter()
    shown = 0
    for i, s in hits:
        c = chunks[i]
        if per[c["doc"]] >= a.per_doc:
            continue
        per[c["doc"]] += 1
        d = docs[c["doc"]]
        body = c["text"].strip()
        if len(body) > a.chars:
            body = body[: a.chars] + "…"
        L += [f"### {c['heading']}", f"*출처: {d.get('page_title') or d['family']} §{c['i'] + 1} · `{d['id']}`*", "",
              "```", body, "```", ""]
        shown += 1
        if shown >= a.slides:
            break
    L += ["## 3. 기존 강의 흐름 (목차 참고)", ""]
    for d in top_docs[: a.outlines]:
        if not d["outline"]:
            continue
        L.append(f"**{d.get('page_title') or d['family']}** ({d['date']}, {d['n_sections']}개 섹션)")
        L += [f"{j}. {h}" for j, h in enumerate(d["outline"][:30], 1)]
        L.append("")
    L += ["## 4. 새 강의안 작성 체크리스트", "",
          "- [ ] 대상·시간·고객사 맥락 확정 (위 1번 표의 같은 고객사 이력 확인)",
          "- [ ] 3번 흐름 중 하나를 뼈대로 선택하고 빠진 개념(2번에 없는 최신 주제) 보강",
          "- [ ] 2번 발췌를 그대로 붙이지 말고 새 대상의 업무 사례로 다시 쓰기",
          "- [ ] 문체·디자인은 기존 스킬(ssj-lecture-voice, ssjhtml4 등) 적용",
          ""]
    out = "\n".join(L)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
        print(f"재료팩 저장: {a.out}  (문서 {len(top_docs)}개, 슬라이드 {shown}개)")
    else:
        print(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("search"); p.add_argument("query"); p.add_argument("-k", type=int, default=12)
    p.add_argument("--per-doc", type=int, default=2); p.add_argument("--chars", type=int, default=220)
    p.set_defaults(f=cmd_search)
    p = sp.add_parser("pack"); p.add_argument("topic"); p.add_argument("-o", "--out")
    p.add_argument("--docs", type=int, default=10); p.add_argument("--slides", type=int, default=24)
    p.add_argument("--per-doc", type=int, default=3); p.add_argument("--chars", type=int, default=600)
    p.add_argument("--outlines", type=int, default=4); p.set_defaults(f=cmd_pack)
    p = sp.add_parser("doc"); p.add_argument("key"); p.add_argument("--full", action="store_true"); p.set_defaults(f=cmd_doc)
    p = sp.add_parser("concept"); p.add_argument("name"); p.add_argument("-k", type=int, default=25); p.set_defaults(f=cmd_concept)
    p = sp.add_parser("client"); p.add_argument("name"); p.set_defaults(f=cmd_client)
    p = sp.add_parser("course"); p.add_argument("name", nargs="?"); p.set_defaults(f=cmd_course)
    p = sp.add_parser("topics"); p.set_defaults(f=cmd_topics)
    p = sp.add_parser("context"); p.add_argument("query"); p.add_argument("-n", type=int, default=15)
    p.add_argument("--per-doc", type=int, default=3); p.add_argument("-o", "--out"); p.set_defaults(f=cmd_context)
    p = sp.add_parser("stats"); p.set_defaults(f=cmd_stats)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
