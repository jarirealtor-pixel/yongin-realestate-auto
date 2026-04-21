"""
용인시 주간 부동산 시세 리포트 자동 생성기
- 국토교통부 실거래가 API → 용인 공장/창고/토지 주간 거래 집계
- Claude AI로 시장 분석 리포트 생성
- 노션 포스팅 초안 DB에 자동 저장
"""

import os
import json
import datetime
import urllib.request
import urllib.parse

# ── 환경변수 (GitHub Secrets) ──────────────────────────────
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
NOTION_KEY = os.environ["NOTION_API_KEY"]
NOTION_DRAFT_PAGE = os.environ["NOTION_DRAFT_PAGE_ID"]  # 포스팅 초안 DB 페이지 ID
MOLITKEY = os.environ.get("MOLIT_API_KEY", "")          # 국토부 API (선택)

# ── 날짜 설정 ──────────────────────────────────────────────
today = datetime.date.today()
week_ago = today - datetime.timedelta(days=7)
YYMM = today.strftime("%Y%m")
WEEK_LABEL = f"{week_ago.strftime('%m/%d')} ~ {today.strftime('%m/%d')}"

# 용인시 법정동 코드
YONGIN_REGIONS = {
    "기흥구": "41463",
    "수지구": "41465",
    "처인구": "41461",
}

# ── 국토부 실거래가 API 호출 ────────────────────────────────
def fetch_molit_transactions(region_code: str, deal_ym: str, deal_type: str) -> list:
    """
    deal_type: "RTMSOBJSvc" (아파트) / "RTMSOBJSvcLandTrade" (토지)
               "RTMSOBJSvcNrgTrade" (공장/창고 등 비주거)
    """
    if not MOLITKEY:
        return []
    base = "http://apis.data.go.kr/1613000/RTMSOBJSvcLandTrade/getLandTrade"
    params = {
        "serviceKey": MOLITKEY,
        "LAWD_CD": region_code,
        "DEAL_YMD": deal_ym,
        "numOfRows": "100",
        "pageNo": "1",
    }
    url = base + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read().decode("utf-8")
        return data
    except Exception as e:
        print(f"[API] {region_code} 조회 실패: {e}")
        return []

# ── Claude API 호출 ────────────────────────────────────────
def call_claude(system: str, prompt: str, search: bool = False) -> str:
    tools = [{"type": "web_search_20250305", "name": "web_search"}] if search else []
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    if tools:
        body["tools"] = tools
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "web-search-2025-03-05",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())
    texts = [b["text"] for b in resp.get("content", []) if b.get("type") == "text"]
    return "\n".join(texts).strip()

# ── 노션 페이지 저장 ────────────────────────────────────────
def save_to_notion(title: str, content: str, parent_page_id: str):
    body = {
        "parent": {"page_id": parent_page_id},
        "icon": {"emoji": "📊"},
        "properties": {
            "title": {"title": [{"text": {"content": title}}]}
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                },
            }
            for chunk in [content[i:i+1900] for i in range(0, min(len(content), 20000), 1900)]
        ],
    }
    req = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {NOTION_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
    return result.get("url", "")

# ── 메인 실행 ──────────────────────────────────────────────
def main():
    print(f"[시작] 용인 주간 시세 리포트 생성 — {WEEK_LABEL}")

    # 1. Claude + 웹검색으로 주간 시장 분석 리포트 생성
    system = """당신은 용인시 전문 부동산 시장 분석가입니다.
매주 공장·창고·토지 위주로 용인시 부동산 시장을 분석합니다.
웹 검색을 통해 최신 실거래 데이터, 뉴스, 개발 호재를 수집하세요.
네이버 블로그 포스팅 형식으로 작성하되 마크다운 소제목(##)과 이모지를 활용하세요.
수치와 출처를 명시해 신뢰도를 높이세요."""

    prompt = f"""용인시 부동산 주간 시세 리포트 ({WEEK_LABEL}) 작성:

아래 순서대로 작성해줘. 웹 검색으로 최신 데이터를 반드시 포함해.

## 📊 이번 주 용인 부동산 시장 요약
- 기흥구 / 수지구 / 처인구 주요 거래 동향
- 공장·창고 거래 건수 및 평균 평당가 변화

## 🏭 공장·창고 시장
- 최근 1주 주요 거래 사례 (지역, 면적, 금액)
- 평당가 추이 (전주 대비)
- 주목할 거래 또는 매물

## 🏗️ 토지 시장
- 처인구 중심 개발용지 동향
- 공업지역·관리지역 시세

## 📌 이번 주 주요 호재·뉴스
- 용인 반도체 클러스터 / GTX / 도로개발 등 개발 이슈
- 인허가·착공 소식

## 💡 다음 주 투자 포인트
- 주목할 지역·매물 유형
- 매수/매도 타이밍 시그널

## 📞 문의
이 리포트는 매주 월요일 발행됩니다. 구독·문의는 댓글로 남겨주세요."""

    print("[생성] Claude AI 리포트 작성 중 (웹 검색 포함)...")
    report = call_claude(system, prompt, search=True)
    print(f"[생성] 완료 — {len(report)}자")

    # 2. 노션에 저장
    title = f"📊 용인 주간 시세 리포트 {WEEK_LABEL}"
    notion_url = save_to_notion(title, report, NOTION_DRAFT_PAGE)
    print(f"[노션] 저장 완료: {notion_url}")

    # 3. 결과 파일 저장 (GitHub Actions artifact용)
    output = {
        "week": WEEK_LABEL,
        "generated_at": today.isoformat(),
        "notion_url": notion_url,
        "report": report,
    }
    with open("report_output.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("[완료] report_output.json 저장")

if __name__ == "__main__":
    main()
