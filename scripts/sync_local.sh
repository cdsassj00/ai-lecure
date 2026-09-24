#!/usr/bin/env bash
# 로컬 PC에서 Drive 동기화 폴더 전체를 색인하고 GitHub에 올린다.
# 사용법: LECTURE_DIR="/Users/me/Google Drive/내 드라이브/강의안/01_강의관련" scripts/sync_local.sh
set -euo pipefail
cd "$(dirname "$0")/.."
: "${LECTURE_DIR:?LECTURE_DIR 환경변수에 01_강의관련 폴더 경로를 지정하세요}"
git pull --ff-only
python3 kg/build.py --src "$LECTURE_DIR"
python3 kg/query.py stats
git add graph data
if git diff --cached --quiet; then echo "변경 없음"; exit 0; fi
git commit -m "강의안 지식그래프 갱신 ($(date +%F))"
git push
