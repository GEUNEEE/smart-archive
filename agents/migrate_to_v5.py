"""
v4 백업 → v5 스키마 마이그레이션 스크립트

입력: agents/smart_archive_backup_2026-05-18.json (v4 형식)
출력: data/archive.json (v5 스키마)

v5 스키마 필드:
  id, date, type, platform, url, ytid, thumbnail,
  title, summary, memo, tags, status, source, raw

실행: python agents/migrate_to_v5.py
"""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
BACKUP = ROOT / "agents" / "smart_archive_backup_2026-05-18.json"
OUTPUT = ROOT / "data" / "archive.json"

CHANNEL_TO_PLATFORM = {
    "스레드": "threads",
    "유튜브": "youtube",
    "x": "x",
    "X": "x",
    "인스타그램": "instagram",
    "틱톡": "tiktok",
}

MEMO_TYPE_TO_PLATFORM = {
    "유튜브링크": "youtube",
    "인스타링크": "instagram",
    "기타링크": "web",
}

CALL_TYPE_MAP = {
    "미팅": "회의",
    "브레인스토밍": "회의",
    "상담": "통화",
    "업무협의": "통화",
    "기타": "통화",
}


def extract_ytid(url: str) -> str | None:
    if not url:
        return None
    m = re.search(r"(?:youtu\.be/|[?&]v=|embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def make_id(prefix: str = "") -> str:
    return (prefix + "_" if prefix else "") + uuid.uuid4().hex[:12]


def migrate_viral(item: dict) -> dict:
    platform = CHANNEL_TO_PLATFORM.get(item.get("channel", ""), None)
    url = item.get("url") or ""
    ytid = extract_ytid(url) if platform == "youtube" else None
    thumbnail = f"https://img.youtube.com/vi/{ytid}/hqdefault.jpg" if ytid else None

    raw_parts = []
    if item.get("content"):
        raw_parts.append(item["content"])
    if item.get("author"):
        raw_parts.append(f"@{item['author'].lstrip('@')}")
    if item.get("originalDate"):
        raw_parts.append(f"originalDate:{item['originalDate']}")

    return {
        "id": item.get("id") or make_id("v"),
        "date": item.get("collectedAt") or item.get("originalDate") or datetime.now().strftime("%Y-%m-%d"),
        "type": "바이럴",
        "platform": platform,
        "url": url,
        "ytid": ytid,
        "thumbnail": thumbnail,
        "title": item.get("title") or "",
        "summary": item.get("aiSummary") or "",
        "memo": item.get("myMemo") or "",
        "tags": item.get("tags") or [],
        "status": "보관",
        "source": "import-v4",
        "raw": " | ".join(raw_parts) if raw_parts else "",
        # 보존 필드 (앱에서 활용 가능)
        "author": item.get("author") or "",
        "views": item.get("views") or 0,
        "likes": item.get("likes") or 0,
        "comments": item.get("comments") or 0,
        "category": item.get("category") or "",
    }


def migrate_memo(item: dict) -> dict:
    url = item.get("url") or ""
    subtype = item.get("type") or ""
    platform = MEMO_TYPE_TO_PLATFORM.get(subtype, None)
    ytid = extract_ytid(url) if platform == "youtube" else None
    thumbnail = f"https://img.youtube.com/vi/{ytid}/hqdefault.jpg" if ytid else None

    raw_parts = []
    if item.get("content"):
        raw_parts.append(item["content"])

    return {
        "id": item.get("id") or make_id("m"),
        "date": item.get("savedAt") or datetime.now().strftime("%Y-%m-%d"),
        "type": "메모",
        "platform": platform,
        "url": url,
        "ytid": ytid,
        "thumbnail": thumbnail,
        "title": item.get("title") or "",
        "summary": item.get("aiSummary") or "",
        "memo": item.get("myThought") or "",
        "tags": item.get("tags") or [],
        "status": "보관",
        "source": "import-v4",
        "raw": " | ".join(raw_parts) if raw_parts else "",
        # 보존 필드
        "subtype": subtype,
        "content": item.get("content") or "",
    }


def migrate_call(item: dict) -> dict:
    subtype = item.get("type") or "기타"
    v5_type = CALL_TYPE_MAP.get(subtype, "통화")

    raw_parts = []
    if item.get("fullContent"):
        raw_parts.append(item["fullContent"][:200])  # 원문 앞 200자만

    return {
        "id": item.get("id") or make_id("c"),
        "date": item.get("date") or item.get("createdAt") or datetime.now().strftime("%Y-%m-%d"),
        "type": v5_type,
        "platform": None,
        "url": "",
        "ytid": None,
        "thumbnail": None,
        "title": item.get("title") or "",
        "summary": item.get("aiSummary") or "",
        "memo": item.get("myMemo") or "",
        "tags": item.get("tags") or [],
        "status": "보관",
        "source": "import-v4",
        "raw": " | ".join(raw_parts) if raw_parts else "",
        # 보존 필드
        "subtype": subtype,
        "duration": item.get("duration") or 0,
        "attendees": item.get("attendees") or [],
        "actionItems": item.get("actionItems") or [],
        "fullContent": item.get("fullContent") or "",
    }


def migrate_image(item: dict) -> dict:
    return {
        "id": item.get("id") or make_id("img"),
        "date": item.get("date") or item.get("createdAt") or datetime.now().strftime("%Y-%m-%d"),
        "type": "이미지",
        "platform": None,
        "url": "",
        "ytid": None,
        "thumbnail": None,
        "title": item.get("title") or "",
        "summary": "",
        "memo": item.get("memo") or "",
        "tags": item.get("tags") or [],
        "status": "보관",
        "source": "import-v4",
        "raw": item.get("filename") or "",
        # 보존 필드
        "category": item.get("category") or "",
        "filename": item.get("filename") or "",
        "mimeType": item.get("mimeType") or "",
        "sizeBytes": item.get("sizeBytes") or 0,
    }


def main():
    print(f"[backup] {BACKUP}")
    with open(BACKUP, encoding="utf-8") as f:
        backup = json.load(f)

    data = backup.get("data", {})
    items: list[dict] = []

    viral = data.get("viral", [])
    memo = data.get("memo", [])
    calls = data.get("calls", [])
    images = data.get("imgMeta", data.get("images", []))

    print(f"  viral: {len(viral)}, memo: {len(memo)}, calls: {len(calls)}, images: {len(images)}")

    for item in viral:
        items.append(migrate_viral(item))

    for item in memo:
        items.append(migrate_memo(item))

    for item in calls:
        items.append(migrate_call(item))

    for item in images:
        items.append(migrate_image(item))

    # 날짜 내림차순 정렬 (최신 먼저)
    items.sort(key=lambda x: x.get("date") or "", reverse=True)

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"\n[done] {OUTPUT}")
    print(f"   total {len(items)} items")

    type_counts: dict[str, int] = {}
    for item in items:
        t = item["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, n in sorted(type_counts.items()):
        print(f"   {t}: {n}개")


if __name__ == "__main__":
    main()
