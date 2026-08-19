"""
Agent-Reach(yt-dlp) 기반 유튜브 영상/강의 요약 -> 스마트 아카이브 연동
YOUTUBE_API_KEY 없이, 특정 URL 하나를 바로 아카이브에 저장할 때 사용.
(youtube_collector.py는 키워드로 새 영상을 "찾는" 용도, 이 스크립트는
사용자가 이미 가진 URL을 "저장/요약"하는 용도로 역할이 다름)

사용법:
  1) 자막 + 메타데이터 가져오기 (요약은 안 함, AI가 읽고 요약문을 만들 재료)
     python agents/agent_reach_youtube.py fetch <URL>

  2) AI가 만든 요약을 파일로 저장한 뒤, 아카이브에 반영
     python agents/agent_reach_youtube.py save <URL> --summary-file <경로> [--memo "..."] [--no-push]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.to_archive import append_to_archive


def extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:youtu\.be/|[?&]v=|shorts/|embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def _fmt_date(d: str | None) -> str:
    if not d or len(d) != 8:
        return ""
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _run_yt_dlp(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["yt-dlp", *args], capture_output=True, text=True, timeout=timeout)


def fetch_metadata(url: str) -> dict:
    r = _run_yt_dlp(["--dump-json", "--skip-download", url], timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"yt-dlp 메타데이터 조회 실패: {r.stderr[-500:]}")
    return json.loads(r.stdout)


def fetch_transcript_text(url: str, video_id: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out_tmpl = os.path.join(tmp, "%(id)s")
        _run_yt_dlp(
            [
                "--skip-download", "--write-auto-sub", "--write-sub",
                "--sub-lang", "ko,en", "-o", out_tmpl, url,
            ],
            timeout=60,
        )
        vtt_files = list(Path(tmp).glob(f"{video_id}*.vtt"))
        if not vtt_files:
            return ""
        return _vtt_to_text(vtt_files[0].read_text(encoding="utf-8"))


def _vtt_to_text(vtt: str) -> str:
    lines: list[str] = []
    for raw_line in vtt.splitlines():
        line = raw_line.strip()
        if not line or "-->" in line or line == "WEBVTT" or line.startswith(("Kind:", "Language:")):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return " ".join(lines)


def cmd_fetch(args: argparse.Namespace) -> None:
    vid = extract_video_id(args.url)
    if not vid:
        print(json.dumps({"error": "유효한 유튜브 URL이 아닙니다"}, ensure_ascii=False))
        sys.exit(1)

    meta = fetch_metadata(args.url)
    transcript = fetch_transcript_text(args.url, vid)

    result = {
        "url": args.url,
        "videoId": vid,
        "title": meta.get("title", ""),
        "author": meta.get("uploader", ""),
        "description": (meta.get("description") or "")[:1000],
        "views": meta.get("view_count") or 0,
        "likes": meta.get("like_count") or 0,
        "comments": meta.get("comment_count") or 0,
        "originalDate": _fmt_date(meta.get("upload_date")),
        "tags": (meta.get("tags") or [])[:5],
        "transcript": transcript,
        "transcriptLength": len(transcript),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_update_batch(args: argparse.Namespace) -> None:
    """
    이미 아카이브에 있는 URL들의 summary/raw(+title 비어있으면 title)를 채운다.
    --data-file: [{"url": "...", "summary": "...", "raw": "..." (선택)}, ...] 형식의 JSON.
    새 항목을 추가하지 않고, url이 일치하는 기존 항목만 in-place로 갱신한다.
    """
    ARCHIVE_PATH = Path(__file__).parent.parent / "data" / "archive.json"
    with open(args.data_file, encoding="utf-8") as f:
        updates = json.load(f)
    by_url = {u["url"]: u for u in updates if u.get("url")}

    with open(ARCHIVE_PATH, encoding="utf-8") as f:
        archive = json.load(f)

    updated = 0
    not_found = list(by_url.keys())
    for item in archive:
        u = by_url.get(item.get("url"))
        if not u:
            continue
        item["summary"] = u["summary"]
        if u.get("raw"):
            item["raw"] = u["raw"]
        if u.get("title") and (not item.get("title") or item["title"].startswith("YouTube -") or item["title"].startswith("YouTube 쇼츠")):
            item["title"] = u["title"]
        updated += 1
        not_found.remove(item["url"])

    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    if not args.no_push and updated:
        import subprocess as sp
        root = Path(__file__).parent.parent
        date_str = datetime.now().strftime("%Y-%m-%d")
        msg = f"archive: youtube 요약 보완 {updated}건 {date_str}"
        sp.run(["git", "add", "data/archive.json"], cwd=root, check=True)
        sp.run(["git", "commit", "-m", msg], cwd=root, check=True)
        sp.run(["git", "push"], cwd=root, check=True)

    print(json.dumps({"updated": updated, "not_found": not_found}, ensure_ascii=False, indent=2))


def cmd_save(args: argparse.Namespace) -> None:
    vid = extract_video_id(args.url)
    if not vid:
        print(json.dumps({"error": "유효한 유튜브 URL이 아닙니다"}, ensure_ascii=False))
        sys.exit(1)

    meta = fetch_metadata(args.url)
    summary = Path(args.summary_file).read_text(encoding="utf-8").strip()

    item = {
        "channel": "유튜브",
        "type": "바이럴",
        "title": meta.get("title", ""),
        "content": (meta.get("description") or "")[:1000],
        "author": meta.get("uploader", ""),
        "url": args.url,
        "views": meta.get("view_count") or 0,
        "likes": meta.get("like_count") or 0,
        "comments": meta.get("comment_count") or 0,
        "collectedAt": datetime.now().strftime("%Y-%m-%d"),
        "originalDate": _fmt_date(meta.get("upload_date")),
        "tags": (meta.get("tags") or [])[:5],
        "aiSummary": summary,
        "myMemo": args.memo or "",
    }

    added = append_to_archive([item], source="agent-reach", git_push=not args.no_push)
    print(json.dumps({"added": added, "title": item["title"], "url": args.url}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="자막+메타데이터만 가져오기 (아카이브에 쓰지 않음)")
    p_fetch.add_argument("url")
    p_fetch.set_defaults(func=cmd_fetch)

    p_save = sub.add_parser("save", help="요약 텍스트와 함께 아카이브에 저장 + git push")
    p_save.add_argument("url")
    p_save.add_argument("--summary-file", required=True, help="AI가 작성한 요약이 담긴 텍스트 파일 경로")
    p_save.add_argument("--memo", default="")
    p_save.add_argument("--no-push", action="store_true", help="git push 생략")
    p_save.set_defaults(func=cmd_save)

    p_update = sub.add_parser("update-batch", help="기존 아카이브 항목들의 summary/raw를 일괄 갱신 + git push")
    p_update.add_argument("--data-file", required=True, help="[{url, summary, raw?}] 형식의 JSON 경로")
    p_update.add_argument("--no-push", action="store_true", help="git push 생략")
    p_update.set_defaults(func=cmd_update_batch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
