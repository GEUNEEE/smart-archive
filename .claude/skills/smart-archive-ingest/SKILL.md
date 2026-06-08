---
name: smart-archive-ingest
description: 카카오 "나에게 보내기" 덤프를 분리·분류·요약해 data/archive.json에 추가하고 커밋한다. "오늘 메모 정리", "아카이브에 넣어줘", "카카오 덤프 정리" 등에서 사용.
---

# 스마트 아카이브 인제스트 스킬

## 역할
카카오 "나에게 보내기" 대화 덤프를 입력받아 메시지를 분리·분류한 뒤 `data/archive.json`에 v5 스키마로 추가하고 git push한다.

---

## 동작 순서

### 1단계 — 현재 아카이브 로드
```
data/archive.json을 읽어서 기존 URL 목록과 id 목록을 추출한다.
(중복 제거 기준으로 사용)
```

### 2단계 — 덤프 파싱

#### 날짜 헤더 인식
다음 패턴으로 날짜 구분:
- `YYYY년 M월 D일` (예: `2026년 6월 8일`)
- `YYYY. M. D.`
- `[오전/오후 HH:MM]` 앞에 오는 날짜

#### 메시지 단위 분리
- 빈 줄 2개 이상으로 구분
- 또는 새 날짜 헤더 등장 시 구분
- 한 메시지에 링크+메모가 붙어있으면 하나의 항목으로 처리

#### 카카오 형식 예시
```
2026년 6월 8일

[오후 2:30] https://youtu.be/abc123
반드시 봐야할 영상

[오후 3:00] 오늘 회의 내용
마케팅 전략 논의 - Q3 예산 확정

[오후 4:00] 주문 현황 확인
스마트스토어 매출 집계 필요
```

### 3단계 — 항목 분류

각 메시지에 다음 기준을 순서대로 적용:

| 조건 | type | platform |
|------|------|----------|
| URL 포함 (youtube/youtu.be) | 바이럴 | youtube |
| URL 포함 (instagram.com) | 바이럴 | instagram |
| URL 포함 (tiktok.com) | 바이럴 | tiktok |
| URL 포함 (threads.net/threads.com) | 바이럴 | threads |
| URL 포함 (그 외) | 바이럴 | web |
| 주문·매출·스마트스토어·정산·키워드분석·리마인드·업무 키워드 | 업무 | null |
| 회의·미팅·MTG 키워드 | 회의 | null |
| 통화·전화·상담 키워드 | 통화 | null |
| 그 외 텍스트 | 메모 | null |

### 4단계 — 메타 추출

**YouTube:**
- URL에서 ytid 추출: `(?:youtu\.be/|[?&]v=)([A-Za-z0-9_-]{11})`
- thumbnail: `https://img.youtube.com/vi/{ytid}/hqdefault.jpg`
- title: URL이 있으면 WebFetch로 `<title>` 태그 추출 시도

**Threads/Instagram:**
- title: 텍스트 첫 줄 또는 본문 앞 50자

**업무/회의/통화:**
- title: 텍스트 첫 줄
- tags: 키워드 자동 추출 (2~4개)

### 5단계 — 중복 제거

- 동일 URL이 기존 archive.json에 있으면 건너뜀
- URL 없는 항목은 title이 95% 이상 유사하면 건너뜀

### 6단계 — v5 스키마로 변환

각 항목을 아래 형식으로 생성:
```json
{
  "id": "sa_{timestamp}_{random6}",
  "date": "YYYY-MM-DD",
  "type": "바이럴 | 메모 | 업무 | 통화 | 이미지 | 회의",
  "platform": "youtube | instagram | tiktok | threads | web | null",
  "url": "https://...",
  "ytid": "11자리 YouTube ID 또는 null",
  "thumbnail": "썸네일 URL 또는 null",
  "title": "제목 또는 첫 줄",
  "summary": "",
  "memo": "링크에 붙은 메모 텍스트",
  "tags": ["태그1", "태그2"],
  "status": "할일",
  "source": "kakao-memo",
  "raw": "원문 메시지 전체"
}
```

새 항목은 배열 앞에 prepend (최신 먼저).

### 7단계 — archive.json 업데이트 & git push

```bash
# 새 항목을 기존 배열 앞에 추가한 뒤 저장
git add data/archive.json
git commit -m "archive: +N items YYYY-MM-DD"
git push
```

---

## 출력 보고

작업 완료 후 다음 형식으로 보고:

```
추가된 항목: N개
건너뜀 (중복): M개

유형별 집계:
  바이럴: N개 (youtube N, threads N, ...)
  메모: N개
  업무: N개
  회의: N개
  통화: N개

추가된 항목 목록:
  [바이럴] 제목... (platform)
  [메모] 제목...
  ...

git push 완료
```

---

## 사용 예시

**입력**: 카카오 메모챗 복사 내용을 붙여넣고 "오늘 메모 정리해서 아카이브에 넣어줘"라고 요청

**지원 표현**:
- "오늘 메모 정리"
- "아카이브에 넣어줘"
- "카카오 덤프 정리"
- "나에게 보내기 내용 저장"
- "이거 분류해서 넣어줘"
