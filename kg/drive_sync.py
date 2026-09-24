"""클라우드(Claude Code on the web) 세션에서 Google Drive와 그래프를 맞추는 보조 도구.

클라우드 컨테이너는 Drive를 직접 마운트할 수 없으므로 Claude가 Drive 커넥터로 파일을 받고,
이 스크립트로 매니페스트 갱신·디코딩을 한다. 절차는 .claude/skills/lecture-kg/SKILL.md 참고.

  python kg/drive_sync.py manifest <search_files 결과 JSON 파일>...
      Drive search_files(parentId = 강의 폴더) 결과로 data/drive_manifest.json 을 갱신하고
      새로 생긴/바뀐 파일을 보고한다.
  python kg/drive_sync.py pending [--min-size 38000]
      본문을 새로 받아야 할 fileId 목록 (새 문서, 원본이 바뀐 문서).
      작은 파일은 커넥터가 본문을 대화창에 직접 돌려주므로(디스크 저장 불가) 'local' 로 따로 표시한다.
  python kg/drive_sync.py decode <out_dir>
      이 세션에서 저장된 download_file_content 결과(JSON, base64)를 <out_dir>/<fileId>.html 로 푼다.
      이후 `python kg/build.py --raw <out_dir>` 로 증분 빌드.
"""
from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "drive_manifest.json"
DOCS = ROOT / "graph" / "documents.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import family_key  # noqa: E402


def cmd_manifest(a):
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cur = {f["id"]: f for f in m["files"]}
    seen, new, changed = set(), [], []
    for p in a.files:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        for f in data.get("files", []):
            if f.get("parentId") and f["parentId"] != m["folderId"]:
                continue
            if f.get("mimeType", "text/html") != "text/html":
                continue
            rec = {k: f.get(k) for k in ("id", "title", "modifiedTime", "createdTime", "fileSize")}
            seen.add(rec["id"])
            old = cur.get(rec["id"])
            if not old:
                new.append(rec)
            elif old.get("modifiedTime") != rec["modifiedTime"]:
                changed.append(rec)
            cur[rec["id"]] = rec
    removed = [i for i in cur if i not in seen] if a.full else []
    for i in removed:
        del cur[i]
    m["files"] = sorted(cur.values(), key=lambda f: f["title"])
    from datetime import date
    m["fetched"] = date.today().isoformat()
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"매니페스트 {len(cur)}개 · 새 파일 {len(new)} · 변경 {len(changed)} · 삭제 {len(removed)}")
    for f in new:
        print("  + ", f["title"], f["id"])
    for f in changed:
        print("  ~ ", f["title"], f["id"])


def cmd_pending(a):
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    docs = json.loads(DOCS.read_text(encoding="utf-8")) if DOCS.exists() else []
    by_fam = {d["family"]: d for d in docs}
    fams: dict[str, list] = {}
    for f in m:
        fams.setdefault(family_key(f["title"]), []).append(f)
    cloud, local = [], []
    for fam, members in fams.items():
        latest = max(members, key=lambda f: (f.get("modifiedTime") or "", int(f.get("fileSize") or 0)))
        d = by_fam.get(fam)
        up_to_date = d and d["has_content"] and d.get("indexed_modified") and \
            d["indexed_modified"] >= (latest.get("modifiedTime") or "")
        if up_to_date:
            continue
        size = int(latest.get("fileSize") or 0)
        (cloud if a.min_size <= size <= a.max_size else local).append(latest)
    print(f"# 클라우드에서 받을 파일 {len(cloud)}개 (한 번에 1~3개씩, 5MB 이상은 하나씩)")
    for f in sorted(cloud, key=lambda f: int(f.get("fileSize") or 0)):
        print(f["id"], f"{int(f.get('fileSize') or 0) // 1000}K", f["title"])
    print(f"\n# 로컬 빌드에서만 처리 가능 {len(local)}개 (너무 작거나 10MB 초과)")
    if a.verbose:
        for f in local:
            print(f["id"], f"{int(f.get('fileSize') or 0) // 1000}K", f["title"])


def cmd_decode(a):
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    roots = [os.path.expanduser("~/.claude/projects"), "/root/.claude/projects"]
    n = 0
    for r in dict.fromkeys(roots):
        for p in glob.glob(os.path.join(r, "**", "tool-results", "*download_file_content*"), recursive=True):
            try:
                d = json.loads(Path(p).read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if "content" in d and "id" in d:
                dst = out / f"{d['id']}.html"
                if not dst.exists() or a.force:
                    dst.write_bytes(base64.b64decode(d["content"]))
                    n += 1
    print(f"디코딩 {n}개 → {out} (총 {len(list(out.glob('*.html')))}개)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("manifest"); p.add_argument("files", nargs="+")
    p.add_argument("--full", action="store_true", help="목록에 없는 파일을 삭제로 처리 (폴더 전체를 받았을 때만)")
    p.set_defaults(f=cmd_manifest)
    p = sp.add_parser("pending"); p.add_argument("--min-size", type=int, default=38000)
    p.add_argument("--max-size", type=int, default=9_500_000); p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(f=cmd_pending)
    p = sp.add_parser("decode"); p.add_argument("out_dir"); p.add_argument("--force", action="store_true")
    p.set_defaults(f=cmd_decode)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
