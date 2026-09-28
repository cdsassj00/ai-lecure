"""내용 주제 체계: 슬라이드(섹션)를 '무엇을 가르치는가' 기준으로 묶는다.

CONTENT_TOPICS = [(대주제, [(소주제, [키워드...]), ...]), ...]
  - 슬라이드 제목에 키워드가 나오면 3점, 본문에 나오면 1점(최대 6점).
  - '#'로 시작하는 키워드는 너무 흔한 말이라 제목에 나올 때만 센다 (예: "#에이전트").
  - 4점 이상이고 최고점의 60% 이상인 소주제에 최대 2개까지 배정한다.
  - 새 강의 주제가 생기면 여기에 소주제 한 줄을 추가하고 `python kg/build.py`를 다시 실행한다.
"""
from __future__ import annotations

import re

CONTENT_TOPICS: list[tuple[str, list[tuple[str, list[str]]]]] = [
    ("AI 이해", [
        ("LLM 작동 원리", ["#LLM", "토큰", "파라미터", "트랜스포머", "transformer", "어텐션", "attention", "다음 단어",
                        "확률", "사전학습", "학습 데이터", "컨텍스트 윈도우", "KV 캐시", "가중치", "언어모델"]),
        ("한계·할루시네이션·검증", ["할루시네이션", "환각", "hallucination", "사실 확인", "팩트체크", "#검증", "출처 확인",
                             "그럴듯한", "초안이다", "한계"]),
        ("모델·서비스 비교", ["#ChatGPT", "#Claude", "#Gemini", "Perplexity", "퍼플렉시티", "NotebookLM", "Copilot",
                        "서비스 비교", "모델 비교", "요금제", "GPT-5", "Grok", "DeepSeek"]),
        ("산업별 AI 활용 사례", ["활용 사례", "업계", "#사례", "#동향", "기업 사례", "도입 사례", "Case Study", "#엔터"]),
        ("AI 트렌드·변화", ["트렌드", "#시대", "패러다임", "#AX", "#DX", "일자리", "전망", "프론티어", "산업 변화", "소버린"]),
    ]),
    ("프롬프트·컨텍스트", [
        ("프롬프트 작성법", ["#프롬프트", "#prompt", "역할 부여", "출력 형식", "지시문", "few-shot", "퓨샷", "예시를",
                        "5개 항목", "구조화된 요청", "질문법"]),
        ("컨텍스트 엔지니어링", ["컨텍스트 엔지니어링", "context engineering", "#컨텍스트", "맥락 설계", "Context Injection",
                           "컨텍스트 주입", "쥐여주"]),
        ("지침 파일·메모리·GPTs", ["CLAUDE.md", "AGENTS.md", "메모리", "memory", "프로젝트 지침", "커스텀 지침", "GPTs",
                             "Gems", "프로젝트 기능", "시스템 프롬프트"]),
        ("스킬·플러그인·커넥터", ["스킬", "Skills", "SKILL.md", "플러그인", "plugin", "커넥터", "connector"]),
    ]),
    ("AI 에이전트", [
        ("에이전트 개념", ["#에이전트", "#agent", "에이전틱", "agentic", "#자율", "ReAct", "계획하고", "Plan", "루프"]),
        ("하네스·실행 구조", ["하네스", "harness", "오케스트레이션", "실행 구조", "런타임", "runtime", "#권한", "샌드박스",
                         "sandbox", "#로그", "실행 환경"]),
        ("MCP·도구 연결", ["MCP", "Model Context Protocol", "도구 호출", "tool use", "function calling", "API 연결",
                        "외부 시스템", "도구 연결"]),
        ("멀티에이전트·서브에이전트", ["멀티에이전트", "멀티 에이전트", "multi-agent", "서브에이전트", "subagent",
                               "#병렬", "역할 분담", "에이전트 팀"]),
        ("RAG·문서 검색·지식베이스", ["RAG", "검색 증강", "임베딩", "embedding", "#벡터", "시맨틱 검색", "semantic",
                                "문서 검색", "지식베이스", "온톨로지", "지식그래프", "#위키"]),
        ("로컬 AI·SLM", ["로컬 AI", "로컬 LLM", "Ollama", "SLM", "온디바이스", "사내망", "오픈소스 모델", "LM Studio",
                       "gemma", "llama"]),
    ]),
    ("바이브코딩·개발", [
        ("바이브코딩 개념·원칙", ["바이브코딩", "바이브 코딩", "vibe coding", "비개발자", "노코드", "자연어로 만드",
                            "1인 개발", "풀스택"]),
        ("코딩 에이전트 도구", ["Claude Code", "클로드 코드", "Codex", "코덱스", "Cursor", "커서", "코딩 에이전트",
                          "코딩에이전트", "Antigravity", "Lovable", "Replit", "Windsurf", "#터미널", "#CLI"]),
        ("웹앱·화면 만들기", ["#HTML", "CSS", "JavaScript", "웹앱", "웹 앱", "화면 구성", "#UI", "랜딩페이지", "프론트엔드",
                         "단일 파일", "브라우저에서"]),
        ("배포·버전관리", ["배포", "deploy", "GitHub", "깃허브", "Git", "커밋", "commit", "Vercel", "Netlify", "호스팅",
                       "GitHub Pages"]),
        ("백엔드·데이터베이스", ["백엔드", "backend", "데이터베이스", "Supabase", "SQL", "SQLite", "#서버", "#인증",
                           "#로그인", "Cloudflare", "Firebase"]),
        ("오류 해결·디버깅", ["오류", "에러", "error", "디버깅", "debug", "트러블슈팅", "막혔을 때", "수정 요청", "재현"]),
        ("기획·PRD·요구사항", ["PRD", "요구사항", "기획서", "명세", "사용자 스토리", "기능 목록", "화면 설계", "MVP"]),
    ]),
    ("데이터 분석", [
        ("분석 기획·질문 설계", ["분석 질문", "분석 계획", "가설", "#지표", "KPI", "조작적 정의", "분석 기획", "#문제 정의",
                            "#의사결정"]),
        ("전처리·EDA", ["EDA", "탐색적", "전처리", "결측", "이상치", "pandas", "판다스", "DataFrame", "describe",
                      "데이터 정제", "info()"]),
        ("시각화·대시보드", ["시각화", "차트", "chart", "그래프 그리", "대시보드", "dashboard", "히트맵", "matplotlib",
                        "plotly", "seaborn"]),
        ("통계·머신러닝", ["머신러닝", "machine learning", "회귀", "분류 모델", "군집", "클러스터링", "예측 모델",
                       "#상관", "PCA", "#통계", "식스시그마"]),
        ("데이터 수집·공공데이터", ["공공데이터", "data.go.kr", "크롤링", "스크래핑", "scraping", "오픈API", "Open API",
                              "#수집", "RSS"]),
        ("파이썬·실행 환경", ["파이썬", "Python", "Colab", "코랩", "Jupyter", "주피터", "노트북 환경", "Anaconda",
                         "가상환경", "pip"]),
    ]),
    ("업무 자동화", [
        ("엑셀·스프레드시트", ["엑셀", "Excel", "스프레드시트", "구글 시트", "Google Sheets", "VLOOKUP", "피벗", "#수식",
                          "#함수", "#시트"]),
        ("Apps Script·매크로", ["Apps Script", "앱스스크립트", "앱스 스크립트", "매크로", "VBA", "#트리거"]),
        ("문서·보고서 작성", ["#보고서", "문서 작성", "공문", "HWP", "HWPX", "한글 문서", "초안 작성", "#서식", "#양식"]),
        ("비정형 문서 구조화·추출", ["JSON", "구조화", "비정형", "추출", "OCR", "#PDF", "파싱", "필드 대응", "스키마"]),
        ("이미지·영상·콘텐츠 제작", ["#이미지", "영상 생성", "#영상", "카드뉴스", "포스터", "멀티모달", "숏폼", "썸네일",
                                "Midjourney", "Sora", "Veo", "음성 합성", "아바타"]),
        ("발표자료·PPT 제작", ["PPT", "파워포인트", "PowerPoint", "#슬라이드", "발표자료", "Gamma", "감마", "프레젠테이션"]),
        ("메일·회의·일정", ["#메일", "이메일", "회의록", "#회의", "#일정", "캘린더", "미팅"]),
        ("워크플로 자동화 도구", ["n8n", "Zapier", "Make.com", "워크플로 자동화", "RPA", "Power Automate", "자동화 흐름",
                            "#파이프라인"]),
    ]),
    ("조직·공공 적용", [
        ("공공행정 활용 사례", ["#행정", "#공무원", "민원", "공공기관", "지자체", "보도자료", "#정책", "행안부"]),
        ("AI 도입 전략·거버넌스", ["도입 전략", "거버넌스", "로드맵", "변화관리", "#리더", "#조직", "병목", "#성과", "ROI",
                               "#도입"]),
        ("보안·윤리·개인정보", ["#보안", "개인정보", "윤리", "저작권", "#가이드라인", "기밀", "유출", "망분리", "민감정보"]),
        ("교육 설계·실습 운영", ["커리큘럼", "교육과정", "차시", "학습목표", "실습 과제", "해커톤", "평가 기준", "#수업",
                           "#교육생"]),
    ]),
]


def _pat(term: str) -> re.Pattern:
    t = term.strip()
    if re.fullmatch(r"[A-Z0-9.]{2,5}", t):
        return re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])")
    if re.fullmatch(r"[A-Za-z0-9 .\-()]+", t):
        return re.compile(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", re.I)
    return re.compile(re.escape(t), re.I)


SUBTOPICS: list[dict] = []
for gi, (group, subs) in enumerate(CONTENT_TOPICS):
    for si, (name, kws) in enumerate(subs):
        SUBTOPICS.append({"id": f"t{gi + 1}{si + 1:02d}", "group": group, "name": name, "keywords": kws,
                          "_pats": [(_pat(k.lstrip("#")), k.startswith("#")) for k in kws]})


def score_section(heading: str, text: str) -> list[tuple[str, float]]:
    """섹션 → [(소주제 id, 점수)] 상위 최대 2개."""
    scores = []
    for st in SUBTOPICS:
        h = sum(1 for p, _ in st["_pats"] if p.search(heading))
        b = sum(len(p.findall(text)) * (0.5 if only_head else 1) for p, only_head in st["_pats"])
        s = 3 * h + min(b, 6)
        if s >= 4:
            scores.append((st["id"], s))
    if not scores:
        return []
    scores.sort(key=lambda x: -x[1])
    top = scores[0][1]
    return [(i, s) for i, s in scores[:2] if s >= 0.6 * top]
