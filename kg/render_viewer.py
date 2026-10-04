"""콘텐츠 지도 화면만 다시 그린다.

map_template.html(화면 디자인)만 바꿨을 때 쓴다. Drive 원본이나 전체 빌드 없이,
이미 만들어진 site/index.html · graph/viewer.html 안의 데이터를 그대로 꺼내 새 템플릿에 넣는다.

    python kg/render_viewer.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).parent / "map_template.html"
TARGETS = [ROOT / "site" / "index.html", ROOT / "graph" / "viewer.html"]
DATA_RE = re.compile(r"const D = (.*?);\nconst \$ = ", re.S)


def render(path: Path, tpl: str) -> None:
    html = path.read_text(encoding="utf-8")
    head_end = html.index("<title>")
    m = DATA_RE.search(html)
    if not m:
        raise SystemExit(f"{path}: 데이터(const D = ...)를 찾지 못했습니다.")
    path.write_text(html[:head_end] + tpl.replace("/*__DATA__*/null", m.group(1)), encoding="utf-8")
    print(f"{path.relative_to(ROOT)} 다시 그림")


def main() -> None:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    for p in TARGETS:
        if p.exists():
            render(p, tpl)


if __name__ == "__main__":
    main()
