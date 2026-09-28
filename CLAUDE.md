# ai-lecure — 강의안 지식그래프

신성진(CDSA)의 HTML 강의안(Google Drive `강의안/01_강의관련`)을 지식그래프로 만든 저장소다.

- 새 강의안 작성, 기존 강의 검색, 그래프 갱신 요청이 오면 먼저 `.claude/skills/lecture-kg/SKILL.md`를 읽고 따른다.
- 빠른 시작: `python kg/query.py context "<주제>" -o /tmp/ctx.md`(주제별 슬라이드 원문 모음) 또는
  `python kg/query.py pack "<주제·대상·시간>" -o /tmp/pack.md`(비슷한 강의안·흐름) → 기존 문체·디자인 스킬로 작성.
- 내용 주제 체계는 `kg/content_topics.py`, 개념·고객사·과정 묶음 사전은 `kg/vocab.py`.
- 그래프 산출물(`graph/`)은 `kg/build.py`가 생성한다. 손으로 고치지 말고 `kg/vocab.py`(개념·고객사·유형 사전)를 고친 뒤 다시 빌드한다.
- 파이썬 표준 라이브러리만 쓴다(설치 불필요). Python 3.10 이상.
- Drive 폴더 ID: 루트 `1OdmNbitrwKcJ01WvUVMNKzMPSEYNOb9f`, 강의관련 `1RwIqsIMKoCry1-19KqCxSov9-wUbRQ9W`.
