# Drive 자동 동기화 설정 (한 번만)

`.github/workflows/sync-drive.yml`은 6시간마다 Google Drive `강의안/01_강의관련` 폴더를 확인합니다.
새로 생기거나 바뀐 강의안만 받아 지식그래프를 갱신하고 커밋합니다.
GitHub가 Drive를 읽으려면 **서비스 계정** 하나가 필요합니다. 아래는 약 10분 걸리는 1회 설정입니다.

## 1. Google Cloud에서 서비스 계정 만들기

1. https://console.cloud.google.com 에 접속해 새 프로젝트를 만듭니다. 이름 예: `lecture-kg`
2. **API 및 서비스 → 라이브러리**에서 `Google Drive API`를 검색해 **사용**을 누릅니다.
3. **IAM 및 관리자 → 서비스 계정 → 서비스 계정 만들기**를 누릅니다. 이름 예: `drive-sync`
   - 역할은 지정하지 않아도 됩니다.
4. 만든 서비스 계정을 열고 **키 → 키 추가 → 새 키 만들기 → JSON**을 누르면 JSON 파일이 내려받아집니다.
5. 서비스 계정 이메일을 복사합니다. 예: `drive-sync@lecture-kg.iam.gserviceaccount.com`

## 2. Drive 폴더를 서비스 계정에 공유

Google Drive에서 `강의안` 폴더(또는 `01_강의관련` 폴더)를 우클릭 → **공유**를 누르고, 위 이메일을 **뷰어**로 추가합니다.
서비스 계정은 읽기만 할 수 있고 파일을 바꾸지 않습니다.

## 3. GitHub에 키 등록

저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 등록합니다.

- Name: `GDRIVE_SA_KEY`
- Secret: 1-4에서 받은 JSON 파일 내용 전체를 붙여 넣습니다.

## 4. 첫 실행

**Actions → Drive → 지식그래프 동기화 → Run workflow**를 누릅니다.

- 첫 실행에서는 아직 본문이 없는 문서(약 250개, 작은 파일과 10MB 넘는 파일)를 모두 받아 색인합니다.
  클라우드 커넥터로는 받을 수 없던 파일들입니다.
- 이후에는 6시간마다 자동으로 돌고, 바뀐 파일이 없으면 30초 안에 끝납니다.

## 비용

- **Claude 토큰: 0.** 이 Action은 파이썬 스크립트만 돌리고 LLM을 부르지 않습니다.
- **GitHub Actions 시간:** 변경이 없으면 한 번에 약 1분이므로 하루 4회 × 30일 ≈ 120분/월입니다.
  공개 저장소는 무료이고, 비공개 저장소도 무료 한도(월 2,000분) 안에 충분히 들어갑니다.
- 더 자주 또는 덜 자주 돌리려면 워크플로의 `cron` 값을 바꾸세요. 예: 매일 새벽 3시(KST)는 `"0 18 * * *"`
