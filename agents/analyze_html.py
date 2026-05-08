import re
from collections import Counter

with open("threads_debug.html", encoding="utf-8") as f:
    html = f.read()

print(f"파일 크기: {len(html):,}자")

# dir="auto" 텍스트 직접 추출
texts = re.findall(r'dir="auto"[^>]*>([^<]{30,200})<', html)
print(f"\ndir=auto 텍스트 {len(texts)}개:")
for t in texts[:8]:
    print(f"  → {t[:100]}")

# 좋아요 관련 aria-label
likes = re.findall(r'aria-label="([^"]*like[^"]*|[^"]*좋아요[^"]*)"', html, re.IGNORECASE)
print(f"\n좋아요 aria-label {len(likes)}개:")
for l in likes[:5]:
    print(f"  → {l}")

# href 패턴 (게시글 링크)
post_links = re.findall(r'href="(/[^/][^"]*?/post/[^"]+)"', html)
print(f"\n게시글 링크 {len(post_links)}개:")
for lk in post_links[:5]:
    print(f"  → {lk}")

# 스크롤 전 로드된 구조 파악
if "threads.com" in html:
    print("\n✅ threads.com 도메인 확인됨")
