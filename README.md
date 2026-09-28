# 강의안 지식그래프 (ai-lecure)

Google Drive `강의안/01_강의관련` 폴더의 HTML 강의안을 지식그래프로 바꿔 둔 저장소입니다.
그래프가 GitHub에 있으므로 클라우드의 Claude Code 세션에서 언제든 기존 강의안을 찾아 새 강의안 재료로 쓸 수 있습니다.

## 현재 상태 (2026-09-24 빌드)

| 항목 | 수 |
|---|---:|
| Drive 원본 HTML 파일 | 891 |
| 문서 (버전·사본을 묶은 강의안 계열) | 505 |
| 본문까지 색인된 문서 | 254 |
| 슬라이드/섹션 청크 | 5,548 |
| 개념 노드 | 55 |
| 고객사 노드 | 30 |

나머지 251개 문서는 제목·날짜·유형·Drive 링크만 들어 있습니다. 대부분 40KB 미만의 작은 파일이고, 일부는 5MB가 넘는 이미지 포함 파일입니다.
클라우드 커넥터로는 이 파일들의 본문을 가져올 수 없으므로, 로컬 PC에서 `scripts/sync_local.ps1`을 한 번 실행하면 모두 채워집니다.

## 구조

```
kg/
  extract.py          HTML → 슬라이드/섹션 텍스트 (base64 이미지 제거, JS로 그리는 SVG 강의안도 복원)
  content_topics.py   내용 주제 체계 (대주제 7 · 소주제 40, 키워드) ← 슬라이드를 주제로 묶는 기준
  topic_map.py        슬라이드 → 주제 배정, 중복 슬라이드 합치기 → graph/topics.json
  vocab.py            개념·고객사·문서유형·과정 묶음 사전
  build.py            그래프 빌드 (로컬 폴더 --src / Drive 다운로드 --raw, 증분)
  query.py            search · pack(재료팩) · doc · concept · client · stats
  drive_sync.py       클라우드 세션용 Drive 매니페스트 갱신·다운로드 디코딩
  drive_fetch.py      GitHub Actions용 Drive API 동기화 (바뀐 파일만 다운로드)
  map_template.html   강의 콘텐츠 지도 화면
graph/                빌드 산출물 (INDEX.md, documents.json, chunks.jsonl, graph.json, topics.json, viewer.html)
site/                 배포용: index.html(콘텐츠 지도) + p/<fileId>.html(강의안 원본 미리보기)
data/drive_manifest.json   Drive 폴더 파일 목록
scripts/sync_local.*       로컬 전체 빌드 + push
.claude/skills/lecture-kg/ Claude가 이 그래프를 쓰는 절차
```

## 강의 콘텐츠 지도 (화면)

`site/index.html`(또는 `graph/viewer.html`)을 열면 됩니다.

- **지도**: 대주제 7개 안에 소주제 40개가 버블로 들어 있습니다. 버블 크기는 슬라이드 수, 색 진하기는 그 주제를 다룬 강의안 수입니다.
- **주제 선택**: 오른쪽에 그 주제로 가르친 슬라이드가 모입니다. 여러 강의안에 똑같이 들어간 슬라이드는 한 장으로 합치고 "강의안 N개에서 사용"으로 표시합니다.
  함께 가르친 주제, 강의안별로 좁혀 보기도 할 수 있습니다.
- **미리보기**: 슬라이드 제목을 누르면 팝업이 열립니다. '원본 화면' 탭은 강의안 HTML을 그대로 띄우고 해당 슬라이드로 이동합니다.
  '핵심 내용' 탭은 그 강의안의 목차와 슬라이드 본문을 보여 줍니다.
- **컨텍스트 만들기**: 슬라이드를 체크하고 버튼을 누르면 새 강의안 작성용 마크다운이 만들어집니다. 복사해서 Claude에게 붙여 넣으면 됩니다.

## 그래프 모델

- **노드**: 강의 주제(11개), 문서(강의안 계열), 개념(55개, 7개 분류), 분류, 고객사, 문서유형
- **과정 묶음**: `kg/vocab.py`의 `TOPICS`. 강의안(파일) 단위로 어떤 과정에 속하는지 나눕니다. `python kg/query.py course`에서 씁니다.
- **내용 주제**: `kg/content_topics.py`. 슬라이드 단위로 무엇을 가르쳤는지 나눕니다. 콘텐츠 지도와 `context` 명령이 씁니다.
- **엣지**
  - `다룸`: 문서→개념 (가중치 = 본문 언급 수, 제목에 나오면 가중)
  - `함께 등장`: 개념↔개념 (같은 문서에 3회 이상 함께 등장)
  - `유사`: 문서↔문서 (개념·키워드 코사인 ≥ 0.35)
  - `주제`: 문서→강의 주제
  - `고객사`, `유형`
- 버전 사본(`(1)`, `_v2`, `__1`, `_edited` 등)은 한 문서로 묶고, 가장 최근 판을 대표로 씁니다. 나머지 판은 `versions`에 남깁니다.

## 쓰는 법

```bash
# 새 강의안 재료팩
python kg/query.py pack "제조업 현장 관리자 대상 AI 데이터분석 8시간" -o pack.md

# 슬라이드 단위 검색
python kg/query.py search "하네스 권한 로그"

# 한 문서 목차·본문
python kg/query.py doc 에이전틱AI_실무활용 --full

# 내용 주제별 컨텍스트 (슬라이드 원문 모음)
python kg/query.py topics
python kg/query.py context "MCP" -n 20 -o ctx.md

# 과정 묶음별 강의안 목록
python kg/query.py course
python kg/query.py course 데이터분석

# 개념·고객사 이력
python kg/query.py concept MCP
python kg/query.py client 삼성전자
```

클라우드 세션의 Claude에게는 "내 강의안 지식그래프로 ○○ 강의안 써줘"라고 요청하면 됩니다.
Claude가 `CLAUDE.md`와 `lecture-kg` 스킬을 따라 재료팩을 만들고, 필요한 원본은 Drive 커넥터로 엽니다.

## 갱신

- **자동 (GitHub Actions)**: `.github/workflows/sync-drive.yml`이 6시간마다 Drive를 확인해 바뀐 파일만 받아 증분 빌드하고 커밋합니다.
  Claude 토큰을 쓰지 않습니다. 처음 한 번 서비스 계정 설정이 필요합니다: [docs/drive-sync-setup.md](docs/drive-sync-setup.md)
- **로컬 (전체 색인)**: Windows는 `powershell -ExecutionPolicy Bypass -File scripts\sync_local.ps1 -LectureDir "G:\내 드라이브\강의안\01_강의관련"`
  (경로는 PC의 Drive 동기화 위치에 맞게 바꾸세요.) macOS·Linux는 `LECTURE_DIR=... scripts/sync_local.sh`
- **클라우드**: Claude에게 "강의안 그래프를 드라이브와 동기화해줘"라고 요청하면 됩니다.
  새로 생기거나 바뀐 파일 중 40KB~9.5MB인 파일만 받아서 증분 빌드합니다.

`site/p/`의 미리보기는 저장소 용량을 줄이려고 1.5MB가 넘는 원본에서 base64 이미지를 뺀 판입니다(현재 약 46MB).
