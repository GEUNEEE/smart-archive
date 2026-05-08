@echo off
chcp 65001 >nul
echo ============================================================
echo  SNS 로그인 전용 Chrome 실행
echo  이 창에서 Threads, X, Instagram에 로그인 후 창을 닫으세요.
echo  로그인 세션이 C:\Chrome_Profile_Archive 에 저장됩니다.
echo ============================================================
echo.

set PROFILE=C:\Chrome_Profile_Archive

REM Chrome 경로 자동 감지
set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% (
    echo [오류] Chrome을 찾을 수 없습니다.
    echo  Chrome 설치 경로를 확인하고 이 파일을 수정하세요.
    pause
    exit /b 1
)

echo 1단계: Threads 로그인
%CHROME% --user-data-dir="%PROFILE%" --no-first-run "https://www.threads.net/login"
echo Threads 로그인 완료 후 이 창으로 돌아오세요.
pause

echo.
echo 2단계: X 로그인
%CHROME% --user-data-dir="%PROFILE%" --no-first-run "https://x.com/login"
echo X 로그인 완료 후 이 창으로 돌아오세요.
pause

echo.
echo 3단계: Instagram 로그인 (선택)
%CHROME% --user-data-dir="%PROFILE%" --no-first-run "https://www.instagram.com/accounts/login/"
echo Instagram 로그인 완료 후 이 창으로 돌아오세요.
pause

echo.
echo ============================================================
echo  로그인 완료! 이제 python collect_agent.py 로 테스트하세요.
echo ============================================================
pause
