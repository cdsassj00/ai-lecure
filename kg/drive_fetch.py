"""Google Drive API로 강의 폴더를 직접 읽어 '바뀐 파일만' 내려받는다 (GitHub Actions용).

Claude(LLM)를 쓰지 않는 순수 스크립트다. 토큰 비용이 없다.

필요 패키지: google-auth, requests  (pip install google-auth requests)
인증: 환경변수 GDRIVE_SA_KEY 에 서비스 계정 JSON 키 전체 문자열
      (Drive 폴더를 서비스 계정 이메일에 '뷰어'로 공유해 두어야 한다)

  python kg/drive_fetch.py --out raw          # 매니페스트 갱신 + 변경 파일 다운로드
  python kg/build.py --raw raw                # 증분 빌드

동작
  1. 폴더의 전체 HTML 목록을 받아 data/drive_manifest.json 을 새로 쓴다 (삭제된 파일은 빠진다).
  2. 강의안 계열(버전 묶음)마다 최신 파일의 수정시각이 documents.json 의 indexed_modified 보다
     새로우면 그 파일만 받는다. 처음 실행하면 아직 본문이 없는 문서를 모두 받는다.
  3. 받은 개수를 GITHUB_OUTPUT(changed=, downloaded=)에 남긴다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "drive_manifest.json"
DOCS = ROOT / "graph" / "documents.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import family_key  # noqa: E402

API = "https://www.googleapis.com/drive/v3/files"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def session():
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    raw = os.environ.get("GDRIVE_SA_KEY")
    if not raw:
        sys.exit("GDRIVE_SA_KEY 환경변수(서비스 계정 JSON)가 없습니다.")
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return AuthorizedSession(creds)


def list_folder(s, folder_id: str) -> list[dict]:
    files, token = [], None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, size)",
            "pageSize": 1000, "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
        }
        if token:
            params["pageToken"] = token
        r = s.get(API, params=params, timeout=60)
        r.raise_for_status()
        j = r.json()
        for f in j.get("files", []):
            if f["name"].lower().endswith((".html", ".htm")):
                files.append({"id": f["id"], "title": f["name"], "modifiedTime": f.get("modifiedTime"),
                              "createdTime": f.get("createdTime"), "fileSize": f.get("size")})
        token = j.get("nextPageToken")
        if not token:
            return files


def download(s, fid: str, dst: Path) -> None:
    with s.get(f"{API}/{fid}", params={"alt": "media", "supportsAllDrives": "true"}, stream=True, timeout=300) as r:
        r.raise_for_status()
        with dst.open("wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="raw", help="다운로드 폴더")
    ap.add_argument("--max-files", type=int, default=2000, help="한 번에 받을 최대 파일 수")
    ap.add_argument("--dry-run", action="store_true", help="목록만 비교하고 받지 않음")
    a = ap.parse_args()

    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    s = session()
    files = list_folder(s, m["folderId"])
    if not files:
        sys.exit("폴더에서 HTML 파일을 찾지 못했습니다. 폴더를 서비스 계정 이메일에 공유했는지 확인하세요.")
    old = {f["id"]: f for f in m["files"]}
    new_ids = [f for f in files if f["id"] not in old]
    changed = [f for f in files if f["id"] in old and old[f["id"]].get("modifiedTime") != f["modifiedTime"]]
    removed = [i for i in old if i not in {f["id"] for f in files}]
    m["files"] = sorted(files, key=lambda f: f["title"])
    m["fetched"] = date.today().isoformat()
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Drive {len(files)}개 · 새 파일 {len(new_ids)} · 수정 {len(changed)} · 삭제 {len(removed)}")

    docs = json.loads(DOCS.read_text(encoding="utf-8")) if DOCS.exists() else []
    indexed = {d["family"]: d.get("indexed_modified") for d in docs}
    fams: dict[str, list] = {}
    for f in files:
        fams.setdefault(family_key(f["title"]), []).append(f)
    todo = []
    for fam, members in fams.items():
        latest = max(members, key=lambda f: (f.get("modifiedTime") or "", int(f.get("fileSize") or 0)))
        seen = indexed.get(fam)
        if not seen or seen < (latest.get("modifiedTime") or ""):
            todo.append(latest)
    todo = todo[: a.max_files]
    print(f"받을 파일 {len(todo)}개")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    got = 0
    if not a.dry_run:
        for f in todo:
            try:
                download(s, f["id"], out / f"{f['id']}.html")
                got += 1
                print(f"  ↓ {f['title']}")
            except Exception as e:  # noqa: BLE001
                print(f"  ! 실패 {f['title']}: {e}", file=sys.stderr)
    changed_any = bool(new_ids or changed or removed or got)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as fh:
            fh.write(f"changed={'true' if changed_any else 'false'}\ndownloaded={got}\n")
    print(f"다운로드 {got}개 → {out}")


if __name__ == "__main__":
    main()
