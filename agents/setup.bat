@echo off
chcp 65001 >nul
echo ============================================================
echo  스마트 아카이브 수집 에이전트 - 초기 설치
echo ============================================================
echo.

REM Python 버전 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되지 않았습니다.
    echo  python.org/downloads 에서 Python 3.11 이상을 설치하세요.
    pause
    exit /b 1
)

echo [1/4] Python 패키지 설치 중...
pip install -r requirements.txt
if errorlevel 1 (
    echo [오류] 패키지 설치 실패
    pause
    exit /b 1
)

echo.
echo [2/4] Playwright 브라우저 설치 중...
playwright install chromium
if errorlevel 1 (
    echo [오류] Playwright 설치 실패
    pause
    exit /b 1
)

echo.
echo [3/4] .env 파일 설정...
if not exist ".env" (
    copy ".env.example" ".env"
    echo .env.example을 복사했습니다.
    echo 메모장으로 .env 파일을 열어 설정값을 입력하세요.
    notepad .env
) else (
    echo .env 파일이 이미 존재합니다. 건너뜀.
)

echo.
echo [4/4] Chrome 프로필 폴더 생성...
if not exist "C:\Chrome_Profile_Archive" (
    mkdir "C:\Chrome_Profile_Archive"
    echo C:\Chrome_Profile_Archive 폴더 생성됨
)

echo.
echo ============================================================
echo  설치 완료!
echo ============================================================
echo.
echo 다음 단계:
echo  1. .env 파일에 API 키 및 설정값 입력
echo  2. Chrome으로 Threads, X, Instagram 로그인:
echo     run_login_chrome.bat 실행
echo  3. 수동 테스트: python collect_agent.py
echo  4. 자동 스케줄 등록: register_scheduler.bat
echo.
pause
