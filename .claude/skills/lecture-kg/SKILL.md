---
name: lecture-kg
description: 신성진(CDSA)의 기존 HTML 강의안 지식그래프(이 저장소의 graph/)에서 관련 강의안·슬라이드·개념을 찾아 새 강의안의 재료로 쓰고, Google Drive 강의 폴더와 그래프를 동기화한다. "새 강의안 써줘", "예전에 했던 ○○ 강의 찾아줘", "○○ 주제로 강의안", "내 강의안에서", "지식그래프", "강의안 그래프 갱신", "드라이브랑 동기화" 요청에 사용한다. 문체·디자인은 ssj-lecture-voice, ssjhtml4 등 기존 스킬과 함께 쓴다.
---

# 강의안 지식그래프 활용

이 저장소는 Google Drive `강의안/01_강의관련` 폴더(HTML 강의안 약 890개, 버전 묶음 기준 약 500개 문서)를
지식그래프로 바꿔 둔 것이다. 그래프 파일은 git에 들어 있으므로 클라우드 세션에서도 바로 쓸 수 있다.

| 파일 | 내용 |
|---|---|
| `graph/INDEX.md` | 개념별·고객사별·유형별 문서 카탈로그 (먼저 훑어볼 것) |
| `graph/documents.json` | 문서 카드: 유형, 고객사, 날짜, 개념 가중치, 목차, 요약, 버전, Drive fileId |
| `graph/chunks.jsonl` | 슬라이드/섹션 단위 본문 (섹션당 최대 1,200자) |
| `graph/graph.json` | 노드(문서·개념·분류·고객사·유형)와 엣지(다룸·함께 등장·유사·고객사) |
| `graph/viewer.html` | 브라우저용 인터랙티브 그래프 |
| `data/drive_manifest.json` | Drive 폴더의 전체 파일 목록(fileId·수정시각·크기) |

## A. 새 강의안을 쓸 때

1. **재료팩 만들기** — 주제, 대상, 시간을 한 문장으로 넣는다.
   ```bash
   python kg/query.py pack "공공기관 공무원 대상 AI 에이전트·MCP 입문 4시간" -o /tmp/pack.md
   ```
   재료팩에는 가장 가까운 기존 강의안 10개, 재사용 후보 슬라이드 원문 발췌, 기존 강의 흐름(목차), 체크리스트가 담긴다.
2. **더 깊이 보기**
   - `python kg/query.py search "하네스 권한 로그"`: 슬라이드 단위 검색
   - `python kg/query.py doc <fileId 또는 파일명 일부> --full`: 한 문서의 목차와 섹션 본문 전체
   - `python kg/query.py topic` / `topic 데이터분석`: 강의 주제(11개) 묶음별 이력
   - `python kg/query.py concept 바이브코딩` / `client 행정안전부`: 개념별·고객사별 이력
3. **원본이 필요하면** Drive 커넥터로 연다. `mcp__Google_Drive__download_file_content(fileId)`를 호출한다.
   큰 파일은 결과가 디스크에 저장된다. 그다음 `python kg/drive_sync.py decode /tmp/raw` 후
   `python kg/extract.py /tmp/raw/<fileId>.html`로 읽는다. 40KB 미만 파일은 base64가 대화창으로 바로 들어오므로
   가능하면 `doc --full`의 색인 본문으로 대신한다.
4. **작성 원칙**
   - 같은 고객사에 이미 한 강의가 있으면 중복되지 않게 하고, 이전 판에서 발전한 부분을 반영한다.
   - 발췌 문장은 새 대상의 업무 사례로 다시 쓴다. 그대로 붙여 넣지 않는다.
   - 문체는 `ssj-lecture-voice`, 레이아웃은 `ssjhtml4`/`ssjhtml3`/`lecture-deck` 스킬을 따른다.
   - 재료팩에서 참고한 기존 강의안의 fileId를 작성 메모에 남긴다.
5. 완성본을 Drive에 올릴지는 사용자에게 먼저 묻는다. 올리면 아래 B 절차로 그래프를 갱신한다.

## B. Drive와 그래프 동기화

**평소에는 GitHub Actions(`.github/workflows/sync-drive.yml`)가 6시간마다 자동으로 동기화한다.**
작업 전에 `git pull`로 최신 그래프를 받는다. Actions가 설정되지 않았거나(`docs/drive-sync-setup.md`) 즉시 반영이
필요할 때만 아래 클라우드 절차를 쓴다.

1. 폴더 목록 받기. 결과가 크면 디스크에 저장되므로 저장된 경로를 쓴다.
   `mcp__Google_Drive__search_files(query="parentId = '1RwIqsIMKoCry1-19KqCxSov9-wUbRQ9W'", pageSize=1000, excludeContentSnippets=true)`
2. `python kg/drive_sync.py manifest <저장된 결과 경로> --full`: 새 파일·변경 파일을 보고한다.
3. `python kg/drive_sync.py pending`: 본문을 새로 받아야 할 fileId 목록.
   - 목록의 파일을 `download_file_content`로 받는다. 1MB 미만은 몇 개씩 병렬로 받아도 되지만,
     **3MB 이상은 한 번에 하나씩** 받는다. 병렬로 받으면 Drive 세션이 끊긴다. 10MB가 넘는 파일은 커넥터로 받을 수 없다.
   - 파일이 많으면 서브에이전트 2~3개에 나눠 맡긴다. 서브에이전트에게는 "받기만 하고 내용은 읽지 말 것"이라고 지시한다.
4. `python kg/drive_sync.py decode /tmp/raw && python kg/build.py --raw /tmp/raw`:
   증분 빌드다. 원본이 없는 문서는 이전 색인 본문을 그대로 유지한다.
5. `python kg/query.py stats`로 확인한 뒤 `graph/`와 `data/`를 커밋하고 푸시한다.

## C. 로컬 PC 전체 빌드 (가장 완전함)

로컬에서는 Drive 동기화 폴더를 직접 읽으므로 작은 파일과 10MB 넘는 파일까지 모두 색인된다.
사용자에게 `scripts/sync_local.ps1`(Windows) 또는 `scripts/sync_local.sh`를 안내한다.

## 개념·주제 사전 확장

새 주제가 자주 나오는데 개념 노드로 잡히지 않으면 `kg/vocab.py`의 `CONCEPTS`에 한 줄을 추가한다.
형식은 `"대표명": ("분류", ["동의어", ...])`다. 그다음 `python kg/build.py`를 다시 실행한다.
원본 없이도 이전 색인 본문으로 개념이 다시 계산된다. 고객사는 `CLIENTS`, 문서 유형은 `DOC_TYPES`,
강의 주제 묶음(뷰어 첫 화면)은 `TOPICS`에서 고친다. 주제는 파일명 정규식이 먼저 적용되고, 안 맞으면 개념 점수로 정해진다.
