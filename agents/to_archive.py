"""
아카이브 JSON 생성 (v5 스키마)
수집된 아이템을 data/archive.json (v5 스키마) 형식으로 변환해 append한다.

v5 스키마 필드:
  id, date, type, platform, url, ytid, thumbnail,
  title, summary, memo, tags, status, source, raw

사용법:
  from agents.to_archive import append_to_archive
  append_to_archive(items)  # items는 수집기에서 받은 dict 목록

  또는 CLI:
  python agents/to_archive.py  (더미 데이터로 테스트)
"""
import json
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).parent.parent
ARCHIVE_PATH = ROOT / "data" / "archive.json"
IMPORTS_DIR  = ROOT / "imports"

PLATFORM_MAP = {
    "스레드":    "threads",
    "유튜브":    "youtube",
    "x":         "x",
    "X":         "x",
    "인스타그램": "instagram",
    "틱톡":      "tiktok",
    "instagram": "instagram",
    "youtube":   "youtube",
    "threads":   "threads",
    "tiktok":    "tiktok",
}


def extract_ytid(url: str) -> str | None:
    if not url:
        return None
    m = re.search(r"(?:youtu\.be/|[?&]v=|embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def gen_id(prefix: str = "sa") -> str:
    ts = int(datetime.now().timestamp() * 1000)
    rand = uuid.uuid4().hex[:6]
    return f"{prefix}_{ts}_{rand}"


def to_v5_item(raw: dict, source: str = "agent") -> dict:
    """
    수집기 dict를 v5 스키마로 변환.
    raw 필드에 v4 필드명이 있어도 올바르게 매핑한다.
    """
    now = datetime.now().strftime("%Y-%m-%d")

    url      = raw.get("url") or ""
    channel  = raw.get("channel") or raw.get("platform") or ""
    platform = PLATFORM_MAP.get(channel, channel.lower() if channel else None) or None

    ytid      = extract_ytid(url) if platform == "youtube" else None
    thumbnail = f"https://img.youtube.com/vi/{ytid}/hqdefault.jpg" if ytid else raw.get("thumbnail")

    return {
        "id":        raw.get("id") or gen_id(),
        "date":      raw.get("collectedAt") or raw.get("date") or now,
        "type":      raw.get("type") or "바이럴",
        "platform":  platform,
        "url":       url,
        "ytid":      ytid,
        "thumbnail": thumbnail,
        "title":     raw.get("title") or "",
        "summary":   raw.get("aiSummary") or raw.get("summary") or "",
        "memo":      raw.get("myMemo") or raw.get("memo") or "",
        "tags":      raw.get("tags") or [],
        "status":    raw.get("status") or "보관",
        "source":    source,
        "raw":       raw.get("content") or raw.get("raw") or "",
        # 보존 필드 (앱에서 활용)
        "author":   raw.get("author") or "",
        "views":    int(raw.get("views") or 0),
        "likes":    int(raw.get("likes") or 0),
        "comments": int(raw.get("comments") or 0),
        "category": raw.get("category") or "",
        "originalDate": raw.get("originalDate") or "",
    }


def load_archive() -> list[dict]:
    if ARCHIVE_PATH.exists():
        with open(ARCHIVE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_archive(items: list[dict]) -> None:
    ARCHIVE_PATH.parent.mkdir(exist_ok=True)
    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def append_to_archive(
    raw_items: list[dict],
    source: str = "agent",
    git_push: bool = True,
) -> int:
    """
    raw_items를 v5 스키마로 변환해 archive.json 앞에 prepend.
    URL 또는 id 기준으로 중복 제거.
    git_push=True이면 git add/commit/push 실행.

    반환값: 실제 추가된 항목 수
    """
    existing = load_archive()
    existing_urls = {i.get("url") for i in existing if i.get("url")}
    existing_ids  = {i.get("id")  for i in existing if i.get("id")}

    new_items: list[dict] = []
    for raw in raw_items:
        v5 = to_v5_item(raw, source)
        if v5["url"] and v5["url"] in existing_urls:
            continue
        if v5["id"] and v5["id"] in existing_ids:
            continue
        new_items.append(v5)
        existing_urls.add(v5["url"])
        existing_ids.add(v5["id"])

    if not new_items:
        return 0

    merged = new_items + existing
    save_archive(merged)

    # imports/latest.json 도 v4 형식으로 유지 (기존 앱 호환)
    _update_imports_latest(new_items)

    if git_push:
        _git_push(len(new_items))

    return len(new_items)


def _update_imports_latest(new_items: list[dict]) -> None:
    """기존 autoImportFromServer용 imports/latest.json 도 업데이트 (v4 형식)"""
    payload = {
        "version": "4.0",
        "exportedAt": datetime.now().isoformat(),
        "data": {
            "viral": [
                {
                    "id": i["id"],
                    "title": i["title"],
                    "channel": i.get("platform") or i.get("channel") or "",
                    "type": i["type"],
                    "category": i.get("category") or "",
                    "author": i.get("author") or "",
                    "originalDate": i.get("originalDate") or i["date"],
                    "collectedAt": i["date"],
                    "views": i.get("views") or 0,
                    "likes": i.get("likes") or 0,
                    "comments": i.get("comments") or 0,
                    "url": i["url"],
                    "content": i.get("raw") or "",
                    "aiSummary": i.get("summary") or "",
                    "tags": i.get("tags") or [],
                    "myMemo": i.get("memo") or "",
                    "isBest": False,
                    "isPublished": False,
                    "publishedAt": None,
                }
                for i in new_items if i.get("type") == "바이럴"
            ]
        },
    }
    IMPORTS_DIR.mkdir(exist_ok=True)
    with open(IMPORTS_DIR / "latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _git_push(count: int) -> None:
    date_str = datetime.now().strftime("%Y-%m-%d")
    msg = f"archive: +{count} items {date_str}"
    try:
        subprocess.run(["git", "add", "data/archive.json", "imports/latest.json"],
                       cwd=ROOT, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", msg],
                       cwd=ROOT, check=True, capture_output=True)
        subprocess.run(["git", "push"],
                       cwd=ROOT, check=True, capture_output=True)
        print(f"[git push] {msg}")
    except subprocess.CalledProcessError as e:
        print(f"[git push failed] {e.stderr.decode(errors='replace') if e.stderr else e}")


if __name__ == "__main__":
    dummy = [
        {
            "channel": "스레드",
            "type": "바이럴",
            "title": "테스트 게시글",
            "content": "이것은 테스트입니다",
            "author": "@test",
            "url": f"https://www.threads.net/t/test_{uuid.uuid4().hex[:6]}",
            "views": 0,
            "likes": 1200,
            "comments": 45,
            "collectedAt": datetime.now().strftime("%Y-%m-%d"),
            "originalDate": datetime.now().strftime("%Y-%m-%d"),
            "tags": ["테스트"],
            "aiSummary": "",
        }
    ]
    added = append_to_archive(dummy, source="test", git_push=False)
    print(f"added: {added}")
