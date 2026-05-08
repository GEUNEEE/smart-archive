# 스마트 아카이브 수집 에이전트 (2단계)

Threads · X · YouTube · Instagram에서 바이럴 콘텐츠를 자동 수집합니다.

---

## 빠른 시작 (처음 설치)

```
1. setup.bat 실행          ← Python 패키지 + Playwright 설치
2. .env 파일 편집           ← API 키 입력 (최소: YOUTUBE_API_KEY)
3. run_login_chrome.bat    ← Threads, X, Instagram 로그인
4. python collect_agent.py ← 테스트 실행
5. register_scheduler.bat  ← 매일 09:00 자동 실행 등록
```

---

## 파일 설명

| 파일 | 역할 |
|------|------|
| `collect_agent.py` | 메인 실행 파일. 모든 수집기를 순서대로 실행 |
| `threads_collector.py` | Threads 수집 (Playwright) |
| `x_collector.py` | X(트위터) 수집 (Playwright) |
| `youtube_collector.py` | YouTube 수집 (Data API v3) |
| `instagram_collector.py` | Instagram 수집 (instaloader) |
| `sheets_sync.py` | Google Sheets 업로드/다운로드 |
| `to_archive.py` | 수집 결과 → 아카이브 임포트 JSON 변환 |
| `setup.bat` | 초기 설치 |
| `run_login_chrome.bat` | SNS 로그인용 Chrome 실행 |
| `register_scheduler.bat` | Windows Task Scheduler 등록 |
| `.env.example` | 환경변수 템플릿 → `.env`로 복사해서 사용 |

---

## 필수 설정 (.env)

### YouTube (권장 — 가장 안정적)
1. `console.cloud.google.com` → 새 프로젝트
2. YouTube Data API v3 활성화
3. 사용자 인증 정보 → API 키 생성
4. `.env`의 `YOUTUBE_API_KEY`에 입력

### Threads / X / Instagram (Playwright)
1. `run_login_chrome.bat` 실행
2. 각 플랫폼에 로그인
3. `CHROME_PROFILE_PATH` 경로에 세션 자동 저장

### Google Sheets (선택)
1. `console.cloud.google.com` → Google Sheets API 활성화
2. IAM → 서비스 계정 생성 → JSON 키 다운로드 → `credentials.json`으로 저장
3. 구글 시트 생성 → 서비스 계정 이메일을 편집자로 공유
4. `.env`의 `SPREADSHEET_ID` 입력

---

## 수집 결과 아카이브에 가져오기

수집 실행 후 `archive_import_YYYY-MM-DD.json` 파일이 생성됩니다.

1. 스마트 아카이브 사이트 접속
2. ⚙️ 설정 → 데이터 관리 → **전체 가져오기**
3. 생성된 JSON 파일 선택
4. **"병합"** 선택 → 기존 데이터 유지하며 새 항목만 추가

---

## 트러블슈팅

**Threads/X 셀렉터 오류**
플랫폼이 HTML 구조를 변경하면 셀렉터가 맞지 않을 수 있습니다.
`collect_log.txt`에서 오류 내용 확인 후 각 수집기 파일의 셀렉터를 수정하세요.

**YouTube API 할당량 초과**
무료 할당량은 10,000 유닛/일입니다. 검색 키워드를 3개 이하로 유지하세요.

**Instagram Rate Limit**
instaloader가 너무 빠르게 요청하면 계정이 일시 제한될 수 있습니다.
`MAX_ITEMS_PER_PLATFORM=10` 이하로 설정하세요.
