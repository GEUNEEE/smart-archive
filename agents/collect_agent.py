"""
스마트 아카이브 수집 에이전트 - 메인 실행 파일
매일 Task Scheduler에서 자동 실행됩니다.

수집 순서: Threads → X → YouTube → Instagram
결과:
  1. Google Sheets viral_archive 시트에 신규 항목 추가
  2. archive_import_YYYY-MM-DD.json 생성 (아카이브에서 가져오기 사용)
  3. collect_log.txt에 실행 기록 저장
"""
import asyncio
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# .env 로드
load_dotenv(Path(__file__).parent / ".env")

LOG_FILE = Path(__file__).parent / "collect_log.txt"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    # Windows cp949 콘솔 호환: 인코딩 불가 문자는 ? 로 대체
    print(line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace"))
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


async def run():
    log("=" * 60)
    log("수집 에이전트 시작")

    all_items: list[dict] = []
    summary: list[str] = []
    errors: list[str] = []

    # ── 플랫폼별 수집 ─────────────────────────────────────
    tasks = {
        "Threads": _run_collector("Threads"),
        "X": _run_collector("X"),
        "YouTube": _run_collector("YouTube"),
        "Instagram": _run_collector("Instagram"),
    }

    for name, coro in tasks.items():
        log(f"{name} 수집 중...")
        try:
            items = await coro
            log(f"{name} 완료 - {len(items)}개 수집")
            all_items.extend(items)
            summary.append(f"  {_channel_emoji(name)} {name}: +{len(items)}개")
        except Exception as exc:
            msg = f"{name} 실패: {exc}"
            log(f"[오류] {msg}")
            errors.append(msg)
            summary.append(f"  ❌ {name}: 실패")

    log(f"전체 수집 합계: {len(all_items)}개")

    # ── Google Sheets 업로드 ──────────────────────────────
    sheets_count = 0
    if all_items and os.getenv("SPREADSHEET_ID"):
        try:
            from sheets_sync import push_to_sheets
            sheets_count = push_to_sheets(all_items)
            log(f"Sheets 업로드: {sheets_count}개 추가 (중복 제외)")
        except Exception as exc:
            msg = f"Sheets 업로드 실패: {exc}"
            log(f"[오류] {msg}")
            errors.append(msg)
    else:
        log("Sheets 업로드 건너뜀 (SPREADSHEET_ID 미설정)")

    # ── archive_import.json 생성 + GitHub 자동 push ───────
    json_path = ""
    if all_items:
        try:
            from to_archive import generate_archive_json
            json_path = generate_archive_json(all_items)
            log(f"archive_import.json 생성: {json_path}")
        except Exception as exc:
            log(f"[오류] JSON 생성 실패: {exc}")
            errors.append(f"JSON 생성 실패: {exc}")

        # imports/latest.json 을 GitHub Pages에 자동 push
        if json_path:
            try:
                _git_push_imports()
                log("GitHub Pages 자동 업데이트 완료 (imports/latest.json)")
            except Exception as exc:
                log(f"[경고] git push 실패 (수동 push 필요): {exc}")

    # ── Telegram 알림 ─────────────────────────────────────
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        try:
            _send_telegram_summary(all_items, summary, errors, json_path)
            log("Telegram 알림 전송 완료")
        except Exception as exc:
            log(f"[경고] Telegram 알림 실패: {exc}")
    else:
        log("Telegram 알림 건너뜀 (토큰 미설정)")

    log(f"수집 에이전트 종료 - 성공: {len(all_items)}개 | 오류: {len(errors)}개")
    log("=" * 60)

    return all_items


async def _run_collector(platform: str) -> list[dict]:
    """플랫폼 이름으로 수집기를 동적 임포트해 실행"""
    if platform == "Threads":
        from threads_collector import collect_threads
        return await collect_threads()

    elif platform == "X":
        from x_collector import collect_x
        return await collect_x()

    elif platform == "YouTube":
        from youtube_collector import collect_youtube_async
        return await collect_youtube_async()

    elif platform == "Instagram":
        from instagram_collector import collect_instagram_async
        return await collect_instagram_async()

    return []


def _git_push_imports():
    """imports/latest.json 을 GitHub에 커밋·push해서 GitHub Pages 자동 업데이트"""
    repo_root = Path(__file__).parent.parent
    today = datetime.now().strftime("%Y-%m-%d")
    subprocess.run(
        ["git", "-C", str(repo_root), "add", "imports/latest.json"],
        check=True, capture_output=True,
    )
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain", "imports/latest.json"],
        capture_output=True, text=True,
    )
    if not result.stdout.strip():
        log("imports/latest.json 변경 없음 — push 건너뜀")
        return
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-m", f"chore: auto-update imports {today}"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "push"],
        check=True, capture_output=True,
    )


def _channel_emoji(name: str) -> str:
    return {"Threads": "🧵", "X": "🐦", "YouTube": "▶️", "Instagram": "📸"}.get(name, "•")


def _send_telegram_summary(items, summary_lines, errors, json_path):
    import requests

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    today = datetime.now().strftime("%Y-%m-%d")

    # 조회수/좋아요 Top 3
    top3 = sorted(items, key=lambda x: x.get("views", 0) + x.get("likes", 0) * 10, reverse=True)[:3]
    top_lines = "\n".join(
        f"  • [{t['channel']}] {t['title'][:40]}... ({t['likes']:,}♥)"
        for t in top3
    ) or "  (없음)"

    error_text = "\n".join(f"  ⚠️ {e}" for e in errors) if errors else "  없음"

    text = (
        f"🔍 <b>수집 완료 - {today}</b>\n\n"
        + "\n".join(summary_lines)
        + f"\n\n<b>오늘의 Best 후보 Top 3</b>\n{top_lines}"
        + (f"\n\n<b>오류</b>\n{error_text}" if errors else "")
        + (f"\n\n📂 archive_import.json 생성됨\n→ 아카이브 ⚙️설정 → 전체 가져오기 → 병합 선택" if json_path else "")
    )

    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )


if __name__ == "__main__":
    asyncio.run(run())
