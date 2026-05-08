"""
Google Sheets 동기화
수집된 아이템을 Sheets viral_archive 시트에 추가합니다.

설정:
  1. console.cloud.google.com → Google Sheets API 활성화
  2. IAM → 서비스 계정 생성 → JSON 키 다운로드 → credentials.json으로 저장
  3. 구글 시트 생성 → 서비스 계정 이메일을 편집자로 공유
  4. .env에 SPREADSHEET_ID, GOOGLE_CREDENTIALS_PATH 입력
"""
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

SHEET_NAME = "viral_archive"

# Sheets 컬럼 순서 (헤더 행)
HEADERS = [
    "ID", "제목", "채널", "유형", "분류", "작성자",
    "원본날짜", "수집일", "조회수", "좋아요", "댓글",
    "URL", "AI요약", "태그", "내메모"
]


def push_to_sheets(items: list[dict]) -> int:
    """아이템 목록을 Sheets에 추가. 반환값: 추가된 행 수"""
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    spreadsheet_id = os.getenv("SPREADSHEET_ID", "")

    if not spreadsheet_id:
        raise RuntimeError(
            "SPREADSHEET_ID가 .env에 설정되지 않았습니다.\n"
            "구글 시트 URL에서 /d/ 뒤의 ID를 복사하세요."
        )
    if not os.path.exists(creds_path):
        raise RuntimeError(
            f"credentials.json이 없습니다: {creds_path}\n"
            "console.cloud.google.com → IAM → 서비스 계정 → JSON 키 다운로드"
        )

    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(spreadsheet_id)

    # 시트가 없으면 생성
    try:
        ws = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=20)
        ws.append_row(HEADERS)

    # 기존 데이터에서 중복 URL 확인
    existing = ws.col_values(12)  # URL 컬럼 (12번째)
    existing_urls = set(existing[1:])  # 헤더 제외

    new_rows = []
    for item in items:
        url = item.get("url", "")
        if url in existing_urls:
            continue
        existing_urls.add(url)

        row_id = f"v_{int(datetime.now().timestamp())}_{len(new_rows)}"
        new_rows.append([
            row_id,
            item.get("title", ""),
            item.get("channel", ""),
            item.get("type", "바이럴"),
            "",  # 분류는 나중에 수동 입력 또는 AI 분류
            item.get("author", ""),
            item.get("originalDate", ""),
            item.get("collectedAt", ""),
            item.get("views", 0),
            item.get("likes", 0),
            item.get("comments", 0),
            url,
            item.get("aiSummary", ""),
            ", ".join(item.get("tags", [])),
            item.get("myMemo", ""),
        ])

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    return len(new_rows)


def pull_from_sheets() -> list[dict]:
    """Sheets에서 viral_archive를 읽어 아이템 목록으로 반환"""
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
    spreadsheet_id = os.getenv("SPREADSHEET_ID", "")

    if not spreadsheet_id or not os.path.exists(creds_path):
        return []

    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(spreadsheet_id).worksheet(SHEET_NAME)
    records = ws.get_all_records()

    items = []
    for rec in records:
        items.append({
            "id": rec.get("ID", ""),
            "title": rec.get("제목", ""),
            "channel": rec.get("채널", ""),
            "type": rec.get("유형", "바이럴"),
            "category": rec.get("분류", ""),
            "author": rec.get("작성자", ""),
            "originalDate": rec.get("원본날짜", ""),
            "collectedAt": rec.get("수집일", ""),
            "views": int(rec.get("조회수", 0) or 0),
            "likes": int(rec.get("좋아요", 0) or 0),
            "comments": int(rec.get("댓글", 0) or 0),
            "url": rec.get("URL", ""),
            "aiSummary": rec.get("AI요약", ""),
            "tags": [t.strip() for t in rec.get("태그", "").split(",") if t.strip()],
            "myMemo": rec.get("내메모", ""),
            "isBest": False,
            "isPublished": False,
            "publishedAt": None,
        })

    return items


if __name__ == "__main__":
    print("Sheets 연결 테스트 중...")
    try:
        items = pull_from_sheets()
        print(f"✅ 연결 성공 — 기존 데이터: {len(items)}개")
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
