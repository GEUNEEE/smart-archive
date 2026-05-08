"""
아카이브 임포트 JSON 생성
수집된 아이템을 smart_archive의 "전체 가져오기" 형식으로 변환합니다.

생성 파일: archive_import_YYYY-MM-DD.json
사용법: 스마트 아카이브 ⚙️ 설정 → 전체 가져오기 → 생성된 JSON 파일 선택
        "병합" 선택 시 기존 데이터 유지하며 새 항목만 추가
"""
import json
import os
import random
import string
from datetime import datetime
from pathlib import Path


OUTPUT_DIR = Path(__file__).parent


def generate_archive_json(items: list[dict], output_path: str = None) -> str:
    """
    items: 수집기에서 받은 dict 목록 (channel, title, type, url, ... 포함)
    output_path: 저장 경로 (None이면 자동 생성)
    반환값: 저장된 파일 경로
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    viral_items = []
    for item in items:
        item_id = _gen_id("v")
        viral_items.append({
            "id": item_id,
            "title": item.get("title", ""),
            "channel": item.get("channel", ""),
            "type": item.get("type", "바이럴"),
            "category": item.get("category", ""),
            "author": item.get("author", ""),
            "originalDate": item.get("originalDate", date_str),
            "collectedAt": item.get("collectedAt", date_str),
            "views": int(item.get("views", 0)),
            "likes": int(item.get("likes", 0)),
            "comments": int(item.get("comments", 0)),
            "url": item.get("url", ""),
            "aiSummary": item.get("aiSummary", ""),
            "tags": item.get("tags", []),
            "myMemo": item.get("myMemo", ""),
            "isBest": False,
            "isPublished": False,
            "publishedAt": None,
        })

    payload = {
        "version": "4.0",
        "exportedAt": now.isoformat(),
        "data": {
            "viral": viral_items,
            # memo, calls, imgMeta는 포함하지 않음 → 가져오기 시 기존 데이터 유지
        },
    }

    if output_path is None:
        output_path = str(OUTPUT_DIR / f"archive_import_{date_str}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return output_path


def _gen_id(prefix: str) -> str:
    ts = int(datetime.now().timestamp() * 1000)
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{prefix}_{ts}_{rand}"


if __name__ == "__main__":
    # 테스트용 더미 데이터
    dummy = [
        {
            "channel": "스레드",
            "type": "바이럴",
            "title": "테스트 게시글입니다",
            "content": "이것은 테스트입니다",
            "author": "@test",
            "url": "https://www.threads.net/t/test",
            "views": 0,
            "likes": 1200,
            "comments": 45,
            "collectedAt": datetime.now().strftime("%Y-%m-%d"),
            "originalDate": datetime.now().strftime("%Y-%m-%d"),
            "tags": ["테스트"],
            "aiSummary": "",
        }
    ]
    path = generate_archive_json(dummy)
    print(f"✅ 생성됨: {path}")
