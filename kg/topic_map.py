"""슬라이드 → 내용 주제 지도.

build.py가 호출한다. 산출물:
  graph/topics.json : 대주제 → 소주제 → 슬라이드(중복 제거) 구조와 통계
  chunks.jsonl 의 각 섹션에 "topics": [소주제 id...] 를 채운다.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from content_topics import CONTENT_TOPICS, SUBTOPICS, score_section

EXCLUDE_COURSES = {"수강생 실습 산출물"}  # 교육생 결과물은 '내가 가르친 내용'이 아니므로 지도에서 뺀다


def _key(heading: str, text: str) -> str:
    s = re.sub(r"[\s\d·.,:;!?'\"()\[\]{}<>/\\|~`@#$%^&*_+=-]+", "", (heading + text[:160]).lower())
    return s[:140]


def build_topic_map(docs: list[dict], chunks: list[dict], text_chars: int = 900) -> dict:
    by_id = {d["id"]: d for d in docs}
    # 1) 섹션별 주제 점수
    for c in chunks:
        d = by_id[c["doc"]]
        if d.get("topic") in EXCLUDE_COURSES:
            c["topics"] = []
            continue
        c["topics"] = [t for t, _ in score_section(c["heading"], c["text"])]
        c["_score"] = dict(score_section(c["heading"], c["text"]))

    # 2) 중복 슬라이드 묶기 (여러 강의안에 그대로 재사용된 슬라이드)
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in chunks:
        if c["topics"]:
            groups[_key(c["heading"], c["text"])].append(c)
    slides = []
    for members in groups.values():
        members.sort(key=lambda c: (by_id[c["doc"]].get("date") or "", len(c["text"])), reverse=True)
        rep = members[0]
        d = by_id[rep["doc"]]
        used = list(dict.fromkeys(m["doc"] for m in members))
        tp = Counter()
        for m in members:
            for t in m["topics"]:
                tp[t] = max(tp[t], m["_score"].get(t, 0))
        slides.append({
            "h": rep["heading"], "x": rep["text"][:text_chars], "d": rep["doc"], "i": rep["i"],
            "date": d.get("date"), "reuse": len(used), "docs": used[:8],
            "t": [t for t, _ in tp.most_common(2)], "s": {t: v for t, v in tp.items()},
        })
    for c in chunks:
        c.pop("_score", None)
    slides.sort(key=lambda s: (s["date"] or ""), reverse=True)
    for n, s in enumerate(slides):
        s["n"] = n

    # 3) 소주제 통계
    by_topic: dict[str, list[dict]] = defaultdict(list)
    for s in slides:
        for t in s["t"]:
            by_topic[t].append(s)
    doc_topics: dict[str, Counter] = defaultdict(Counter)
    for s in slides:
        for t in s["t"]:
            for did in s["docs"]:
                doc_topics[did][t] += 1
    co: Counter = Counter()
    for did, tc in doc_topics.items():
        ts = [t for t, n in tc.items() if n >= 2]
        for i in range(len(ts)):
            for j in range(i + 1, len(ts)):
                co[tuple(sorted((ts[i], ts[j])))] += 1

    out_groups = []
    for gi, (gname, subs) in enumerate(CONTENT_TOPICS):
        g = {"name": gname, "subs": []}
        for st in [x for x in SUBTOPICS if x["group"] == gname]:
            ss = by_topic.get(st["id"], [])
            # 대표 슬라이드 순서: 점수 높고 재사용 많고 최신 → 강의안당 최대 4장씩 번갈아
            ss = sorted(ss, key=lambda s: (-s["s"].get(st["id"], 0), -s["reuse"], s["date"] or ""), reverse=False)
            lec = Counter()
            for s in ss:
                for did in s["docs"]:
                    lec[did] += 1
            dates = sorted(s["date"] for s in ss if s["date"])
            rel = sorted(((b if a == st["id"] else a, n) for (a, b), n in co.items() if st["id"] in (a, b)),
                         key=lambda x: -x[1])[:6]
            g["subs"].append({
                "id": st["id"], "name": st["name"],
                "keywords": [k.lstrip("#") for k in st["keywords"][:8]],
                "slides": len(ss), "lectures": len(lec),
                "from": dates[0] if dates else None, "to": dates[-1] if dates else None,
                "order": [s["n"] for s in ss],
                "top_lectures": [[did, n] for did, n in lec.most_common(12)],
                "related": [[t, n] for t, n in rel],
            })
        out_groups.append(g)
    assigned = sum(1 for c in chunks if c["topics"])
    return {"groups": out_groups, "slides": slides,
            "stats": {"sections": len(chunks), "assigned": assigned, "unique_slides": len(slides)}}
