"""
YouTube 전문(자막) 수집 + Groq AI 요약 → imports/transcripts.json 패치 생성
"""
import sys, json, re, time, os
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')

from youtube_transcript_api import YouTubeTranscriptApi
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # .env 또는 환경변수로 설정
GROQ_MODEL   = "llama-3.3-70b-versatile"
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_PATH  = os.path.join(BASE_DIR, "agents", "smart_archive_backup_2026-05-18.json")
OUTPUT_PATH  = os.path.join(BASE_DIR, "imports", "transcripts.json")

# ──────────────────────────────────────────────
def extract_video_id(url: str) -> str | None:
    patterns = [
        r"youtu\.be/([A-Za-z0-9_\-]{11})",
        r"youtube\.com/watch\?v=([A-Za-z0-9_\-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_\-]{11})",
        r"youtube\.com/embed/([A-Za-z0-9_\-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def fetch_transcript(video_id: str) -> str | None:
    api = YouTubeTranscriptApi()
    for langs in [['ko'], ['en'], ['ko', 'en'], ['en', 'ko']]:
        try:
            snippets = list(api.fetch(video_id, languages=langs))
            return " ".join(s.text for s in snippets).strip()
        except Exception:
            pass
    # 자동생성 포함 전체 시도
    try:
        transcript_list = api.list(video_id)
        for t in transcript_list:
            try:
                snippets = list(t.fetch())
                return " ".join(s.text for s in snippets).strip()
            except Exception:
                pass
    except Exception:
        pass
    return None


def groq_summary(title: str, transcript: str) -> str:
    prompt = f"""아래는 유튜브 영상 자막입니다. 마케터·크리에이터 관점에서 핵심 인사이트를 3~5줄로 한국어로 요약해주세요.
핵심 포인트, 실행 가능한 팁, 인상적인 데이터/사례가 있으면 포함하세요.

영상 제목: {title}
자막 (앞 3000자):
{transcript[:3000]}

요약:"""
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 400,
                "temperature": 0.3,
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[AI 요약 실패: {e}]"


# ──────────────────────────────────────────────
def main():
    # 백업에서 메모 아이템 로드
    with open(BACKUP_PATH, encoding='utf-8') as f:
        backup = json.load(f)
    memo_items = backup['data']['memo']

    # YouTube 동영상만 추출 (채널 페이지 제외)
    yt_pattern = re.compile(r'youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/')
    seen_ids = set()
    targets = []
    for item in memo_items:
        url = item.get('url', '')
        if not url or not yt_pattern.search(url):
            continue
        if any(x in url for x in ['/@', '/channel/', '/c/', '/user/']):
            continue
        vid_id = extract_video_id(url)
        if not vid_id or vid_id in seen_ids:
            continue
        seen_ids.add(vid_id)
        targets.append({
            'id': item['id'],
            'url': url,
            'vid_id': vid_id,
            'title': item.get('title', ''),
            'has_ai': bool(item.get('aiSummary', '')),
            'has_tr': bool(item.get('transcript', '')),
        })

    print(f"처리 대상: {len(targets)}개 YouTube 영상\n")

    # 우선순위: AI 없는 것 먼저
    targets.sort(key=lambda x: (x['has_ai'], x['has_tr']))

    # 기존 patches 로드
    existing_patches = {}
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, encoding='utf-8') as f:
                old = json.load(f)
            for p in old.get('patches', []):
                if p.get('url'):
                    existing_patches[p['url']] = p
        except Exception:
            pass

    patches = dict(existing_patches)  # url → patch

    for i, t in enumerate(targets):
        url   = t['url']
        vid   = t['vid_id']
        title = t['title']
        print(f"[{i+1:2d}/{len(targets)}] {vid}  {title[:40]}", end='  ', flush=True)

        # 이미 처리된 것 스킵 (실패도 재시도)
        if url in patches and patches[url].get('status') == 'done':
            print("[SKIP - 이미 완료]")
            continue

        # 자막 가져오기
        transcript = fetch_transcript(vid)
        if not transcript:
            print("[SKIP - 자막 없음]")
            patches[url] = {'url': url, 'videoId': vid, 'status': 'failed', 'analyzedAt': datetime.now().strftime('%Y-%m-%d')}
            _save(patches)
            continue

        print(f"자막 {len(transcript)}자", end='  ', flush=True)

        # AI 요약
        summary = groq_summary(title, transcript)
        print(f"요약 완료")

        patches[url] = {
            'url': url,
            'videoId': vid,
            'transcript': transcript,
            'aiSummary': summary,
            'analyzedAt': datetime.now().strftime('%Y-%m-%d'),
            'status': 'done',
            'force': True,  # 앱에서 기존 AI요약도 덮어씀
        }
        _save(patches)
        time.sleep(0.5)  # Groq rate limit 여유

    print(f"\n완료: {sum(1 for p in patches.values() if p.get('status')=='done')}개 성공, "
          f"{sum(1 for p in patches.values() if p.get('status')=='failed')}개 실패")


def _save(patches: dict):
    output = {
        "version": "1.0",
        "exportedAt": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
        "patches": list(patches.values()),
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
