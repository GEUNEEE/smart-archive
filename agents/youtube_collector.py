"""
YouTube 수집기 (YouTube Data API v3)
API 키만 있으면 됩니다 — Playwright 불필요.

발급: console.cloud.google.com
  → 새 프로젝트 → YouTube Data API v3 활성화 → 사용자 인증 정보 → API 키
무료 할당량: 10,000 유닛/일 (검색 1회=100, 동영상 정보=1)
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import requests


def collect_youtube(max_items: int = None) -> list[dict]:
    max_items = max_items or int(os.getenv("MAX_ITEMS_PER_PLATFORM", "15"))
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "YOUTUBE_API_KEY 환경변수가 설정되지 않았습니다.\n"
            "console.cloud.google.com → YouTube Data API v3 → API 키 발급 후 .env에 입력하세요."
        )

    min_views = int(os.getenv("YOUTUBE_MIN_VIEWS", "50000"))
    keywords_raw = os.getenv(
        "YOUTUBE_KEYWORDS", "마케팅,퍼스널브랜딩,부업,온라인비즈니스,콘텐츠마케팅"
    )
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    # 최근 7일 이내 영상
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=7)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    raw: list[dict] = []
    seen_ids: set[str] = set()

    # 키워드당 검색 (최대 3개 — API 유닛 절약)
    for keyword in keywords[:3]:
        video_ids = _search_videos(api_key, keyword, published_after, count=10)
        new_ids = [vid for vid in video_ids if vid not in seen_ids]
        seen_ids.update(new_ids)

        if not new_ids:
            continue

        for video in _get_video_stats(api_key, new_ids):
            stats = video.get("statistics", {})
            snippet = video.get("snippet", {})
            views = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            comments = int(stats.get("commentCount", 0))

            if views < min_views:
                continue

            title = snippet.get("title", "")
            raw.append(
                {
                    "channel": "유튜브",
                    "type": "바이럴",
                    "title": title,
                    "content": snippet.get("description", "")[:500],
                    "author": snippet.get("channelTitle", ""),
                    "url": f"https://www.youtube.com/watch?v={video['id']}",
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "collectedAt": datetime.now().strftime("%Y-%m-%d"),
                    "originalDate": snippet.get("publishedAt", "")[:10],
                    "tags": snippet.get("tags", [])[:5],
                    "aiSummary": "",
                    "myMemo": "",
                    "isBest": False,
                    "isPublished": False,
                    "publishedAt": None,
                }
            )

    # 조회수 내림차순
    raw.sort(key=lambda x: x["views"], reverse=True)
    return raw[:max_items]


def _search_videos(api_key: str, keyword: str, published_after: str, count: int) -> list[str]:
    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "key": api_key,
            "q": keyword,
            "part": "id",
            "type": "video",
            "order": "viewCount",
            "publishedAfter": published_after,
            "regionCode": "KR",
            "relevanceLanguage": "ko",
            "maxResults": count,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return [item["id"]["videoId"] for item in resp.json().get("items", [])]


def _get_video_stats(api_key: str, video_ids: list[str]) -> list[dict]:
    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "key": api_key,
            "id": ",".join(video_ids),
            "part": "statistics,snippet",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


# async wrapper — collect_agent.py에서 await 가능하도록
async def collect_youtube_async(max_items: int = None) -> list[dict]:
    return await asyncio.to_thread(collect_youtube, max_items)


if __name__ == "__main__":
    results = collect_youtube()
    print(f"YouTube 수집: {len(results)}개")
    for r in results[:5]:
        print(f"  [{r['views']:,}조회 | {r['likes']:,}좋아요] {r['title'][:50]}")
