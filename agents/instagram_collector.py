"""
Instagram 수집기 (instaloader)
instaloader는 Instagram의 공개 데이터를 수집하는 안정적인 오픈소스 라이브러리입니다.
로그인 없이 공개 계정을 수집하거나, 로그인 후 피드를 수집합니다.

사용 방법:
  1. .env의 INSTAGRAM_TARGET_ACCOUNTS에 수집할 공개 계정 입력 (쉼표 구분)
     예: INSTAGRAM_TARGET_ACCOUNTS=account1,account2
  2. 비워두면 현재 로그인 계정의 팔로잉 피드 최신글 수집

주의: Instagram은 과도한 요청 시 계정을 제한합니다.
      MAX_ITEMS_PER_PLATFORM을 15 이하로 유지하고 딜레이를 지키세요.
"""
import asyncio
import os
import time
from datetime import datetime, timedelta

import instaloader


def collect_instagram(max_items: int = None) -> list[dict]:
    max_items = max_items or int(os.getenv("MAX_ITEMS_PER_PLATFORM", "15"))
    min_likes = int(os.getenv("MIN_LIKES", "500"))
    target_accounts_raw = os.getenv("INSTAGRAM_TARGET_ACCOUNTS", "")
    target_accounts = [a.strip() for a in target_accounts_raw.split(",") if a.strip()]

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        quiet=True,
    )

    # 세션 파일이 있으면 자동 로그인 (수동 로그인 후 생성됨)
    session_file = os.path.join(os.path.dirname(__file__), ".instagram_session")
    if os.path.exists(session_file):
        try:
            L.load_session_from_file(session_file)
        except Exception:
            pass

    items = []
    cutoff = datetime.now() - timedelta(days=14)  # 2주 이내 게시물만

    if target_accounts:
        # 지정 계정 최신 게시물 수집
        for account in target_accounts:
            if len(items) >= max_items:
                break
            try:
                profile = instaloader.Profile.from_username(L.context, account)
                for post in profile.get_posts():
                    if post.date_utc.replace(tzinfo=None) < cutoff:
                        break
                    if post.likes < min_likes:
                        continue

                    caption = (post.caption or "")[:500]
                    title = caption[:80] + ("..." if len(caption) > 80 else "")

                    items.append(
                        _make_insta_item(
                            title=title or f"@{account} 게시물",
                            content=caption,
                            author=f"@{account}",
                            url=f"https://www.instagram.com/p/{post.shortcode}/",
                            likes=post.likes,
                            comments=post.comments,
                            original_date=post.date_utc.strftime("%Y-%m-%d"),
                        )
                    )

                    if len(items) >= max_items:
                        break

                    time.sleep(2)  # Instagram rate limit 방지

            except instaloader.exceptions.ProfileNotExistsException:
                print(f"[경고] Instagram 계정 없음: {account}")
            except Exception as e:
                print(f"[경고] Instagram @{account} 수집 실패: {e}")
    else:
        # 로그인 피드 수집 (세션 필요)
        if not L.context.is_logged_in:
            print(
                "[경고] Instagram 로그인 세션이 없습니다.\n"
                "  INSTAGRAM_TARGET_ACCOUNTS에 수집할 공개 계정을 입력하거나,\n"
                "  아래 명령으로 세션을 생성하세요:\n"
                "  python -c \"import instaloader; L=instaloader.Instaloader();"
                " L.interactive_login('아이디'); L.save_session_to_file('.instagram_session')\""
            )
            return []

        try:
            for post in L.get_feed_posts():
                if len(items) >= max_items:
                    break
                if post.likes < min_likes:
                    continue

                caption = (post.caption or "")[:500]
                title = caption[:80] + ("..." if len(caption) > 80 else "")

                items.append(
                    _make_insta_item(
                        title=title or "Instagram 피드 게시물",
                        content=caption,
                        author=f"@{post.owner_username}",
                        url=f"https://www.instagram.com/p/{post.shortcode}/",
                        likes=post.likes,
                        comments=post.comments,
                        original_date=post.date_utc.strftime("%Y-%m-%d"),
                    )
                )
                time.sleep(1.5)

        except Exception as e:
            print(f"[경고] Instagram 피드 수집 실패: {e}")

    return items


def _make_insta_item(title, content, author, url, likes, comments, original_date) -> dict:
    return {
        "channel": "인스타그램",
        "type": "바이럴",
        "title": title,
        "content": content,
        "author": author,
        "url": url,
        "views": 0,
        "likes": likes,
        "comments": comments,
        "collectedAt": datetime.now().strftime("%Y-%m-%d"),
        "originalDate": original_date,
        "tags": [],
        "aiSummary": "",
        "myMemo": "",
        "isBest": False,
        "isPublished": False,
        "publishedAt": None,
    }


async def collect_instagram_async(max_items: int = None) -> list[dict]:
    return await asyncio.to_thread(collect_instagram, max_items)


if __name__ == "__main__":
    results = collect_instagram()
    print(f"Instagram 수집: {len(results)}개")
    for r in results[:3]:
        print(f"  [{r['likes']}좋아요] {r['title'][:50]}")
