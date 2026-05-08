@echo off
chcp 65001 >nul
echo ============================================================
echo  Windows Task Scheduler 등록
echo  매일 오전 9:00에 수집 에이전트를 자동 실행합니다.
echo ============================================================
echo.

REM 현재 폴더 경로
set AGENT_DIR=%~dp0
set AGENT_DIR=%AGENT_DIR:~0,-1%

REM Python 경로
for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i

echo 에이전트 경로: %AGENT_DIR%
echo Python 경로: %PYTHON_PATH%
echo.

REM 기존 작업 삭제 (있으면)
schtasks /delete /tn "SmartArchive_Collect" /f >nul 2>&1

REM 새 작업 등록 — 매일 09:00
schtasks /create ^
  /tn "SmartArchive_Collect" ^
  /tr "\"%PYTHON_PATH%\" \"%AGENT_DIR%\collect_agent.py\"" ^
  /sc DAILY ^
  /st 09:00 ^
  /sd TODAY ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f

if errorlevel 1 (
    echo [오류] 작업 등록 실패. 관리자 권한으로 실행하세요.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  ✅ 등록 완료: 매일 09:00 자동 실행
echo ============================================================
echo.
echo 확인: 작업 스케줄러 → SmartArchive_Collect
echo 수동 실행: schtasks /run /tn "SmartArchive_Collect"
echo 작업 삭제: schtasks /delete /tn "SmartArchive_Collect" /f
echo.
pause
