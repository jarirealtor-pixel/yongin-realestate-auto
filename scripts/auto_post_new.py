"""
노션 매물 DB 신규 등록 감지 → 포스팅 자동 생성
- 매일 3회 실행 (09:00 / 13:00 / 18:00 KST)
- 상태=접수 이면서 포스팅이 아직 없는 매물 감지
- Claude AI + 웹검색으로 포스팅 자동 생성 후 노션 저장
"""

import os
import json
import datetime
import urllib.request
import urllib.parse

ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
NOTION_KEY = os.environ["NOTION_API_KEY"]
NOTION_DB_ID = os.environ["NOTION_DB_ID"]           # 매물 DB collection ID
NOTION_DRAFT_PAGE = os.environ["NOTION_DRAFT_PAGE_ID"]

POST_TYPE = os.environ.get("POST_TYPE", "blog")     # blog | cafe
TONE = os.environ.get("TONE", "pro")                # pro | fri | inv

# ── Notion API 헬퍼 ────────────────────────────────────────
def notion_request(path: str, method: str = "GET", body: dict = None):
    url = f"https://api.notion.com/v1{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {NOTION_KEY}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def get_new_properties() -> list:
    """상태=접수 매물 목록 조회"""
    result = notion_request(
        f"/databases/{NOTION_DB_ID}/query",
        method="POST",
        body={
            "filter": {
                "property": "상태",
                "status": {"equals": "접수"},
            },
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
            "page_size": 20,
        },
    )
    props = []
    for page in result.get("results", []):
        p = page.get("properties", {})
        def txt(k): return (p.get(k, {}).get("rich_text") or p.get(k, {}).get("title") or [{}])[0].get("text", {}).get("content", "") if k in p else ""
        def num(k): return p.get(k, {}).get("number") or 0
        def sel(k): v = p.get(k, {}).get("select"); return v["name"] if v else ""

        props.append({
            "id": page["id"],
            "매물명": txt("매물명") or (p.get("매물명", {}).get("title") or [{}])[0].get("text", {}).get("content", ""),
            "매물유형": sel("매물유형"),
            "지역": sel("지역"),
            "주소": txt("주소"),
            "매매가": num("매매가"),
            "보증금": num("보증금"),
            "월세": num("월세"),
            "대지면적평": num("대지면적(평)"),
            "연면적평": num("연면적(평)"),
            "대지평당가": num("대지평당가"),
            "특징": txt("특징"),
            "비고": txt("비고"),
            "연식": num("연식"),
            "상태": sel("상태"),
        })
    return props

# ── 이미 포스팅된 매물 ID 체크 ────────────────────────────
def get_posted_ids() -> set:
    """노션 초안 페이지에서 이미 처리된 매물 ID 파싱"""
    try:
        result = notion_request(f"/blocks/{NOTION_DRAFT_PAGE}/children")
        titles = []
        for block in result.get("results", []):
            t = block.get("child_page", {}).get("title", "")
            if t:
                titles.append(t)
        # 제목에서 ID 추출 (저장 시 ID를 제목에 포함하는 방식)
        posted = set()
        for t in titles:
            if "[ID:" in t:
                pid = t.split("[ID:")[1].split("]")[0].strip()
                posted.add(pid)
        return posted
    except Exception as e:
        print(f"[경고] 포스팅 이력 조회 실패: {e}")
        return set()

# ── Claude API 호출 ────────────────────────────────────────
def call_claude(system: str, prompt: str) -> str:
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 2000,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": ANTHROPIC_KEY,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "web-search-2025-03-05",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.loads(r.read())
    return "\n".join(b["text"] for b in resp.get("content", []) if b.get("type") == "text").strip()

def fp(w):
    if not w: return "-"
    if w >= 100000000: return f"{w/100000000:.1f}억"
    if w >= 10000: return f"{round(w/10000)}만"
    return f"{w:,}"

# ── 포스팅 생성 ───────────────────────────────────────────
def generate_post(p: dict) -> str:
    price = f"{fp(p['매매가'])}원" if p["매매가"] else (f"보증금 {fp(p['보증금'])}" if p["보증금"] else "협의")
    tone_map = {"pro": "전문적이고 신뢰감 있게", "fri": "친근하고 쉽게", "inv": "투자자 관점 중심으로"}
    type_guide = {
        "공장/창고": "고속도로IC 거리·도로폭·용도지역(공업)·대형차 진출입·물류 인프라",
        "상가": "배후세대(반경 500m/1km)·공실률·임대수익률·집객시설",
        "토지": "용도지역·지목·인근 개발계획·도로 접도·맹지 여부",
        "건물": "임대 현황·공실률·리모델링 여부·층별 임대료",
        "사무실": "역세권·주차·주변 기업체 밀도·임대 시세",
        "지식산업센터": "입주 가능 업종·관리비·지하철 거리",
    }.get(p["매물유형"], "입지·교통·생활 인프라·주변 시세")

    return call_claude(
        f"당신은 용인시 전문 부동산 블로거입니다. 어조: {tone_map.get(TONE, tone_map['pro'])}. "
        "웹 검색으로 최신 지역 정보와 실거래 시세를 반드시 포함하세요. "
        "## 소제목과 이모지를 활용해 가독성 높게. 블로그 본문만 출력.",
        f"""{'네이버 블로그' if POST_TYPE=='blog' else '네이버 카페'} 포스팅 작성:

매물: {p['매물명']} / {p['매물유형']} / 용인시 {p['지역']} {p['주소']}
가격: {price} / 대지 {p['대지면적평'] or '-'}평 / 연면적 {p['연면적평'] or '-'}평
평당가: {f"{p['대지평당가']:,.0f}만원" if p['대지평당가'] else '-'} / 연식: {p['연식'] or '-'}년
특징: {p['특징'] or '-'}  비고: {p['비고'] or '-'}

구성:
1. 용인 {p['지역']} 최신 지역 현황 (웹검색)
2. 주변 환경 분석 — {type_guide}
3. 인근 유사 {p['매물유형']} 실거래 시세 비교 (웹검색)
4. 매물 상세 소개
5. 장점 / 고려사항
6. 투자 포인트 요약 & 문의 안내""",
    )

# ── 노션 저장 ──────────────────────────────────────────────
def save_draft(p: dict, post: str) -> str:
    price = f"{fp(p['매매가'])}원" if p["매매가"] else f"보증금{fp(p['보증금'])}"
    title = f"[{p['매물유형']}] {p['지역']} {price} — {p['매물명']} [ID:{p['id']}]"
    today = datetime.date.today().isoformat()
    header = f"> **매물**: {p['매물명']} | **유형**: {p['매물유형']} | **가격**: {price}\n> **생성일**: {today} | **채널**: {'블로그' if POST_TYPE=='blog' else '카페'}\n\n---\n\n"
    content = header + post

    chunks = [content[i:i+1900] for i in range(0, min(len(content), 20000), 1900)]
    body = {
        "parent": {"page_id": NOTION_DRAFT_PAGE},
        "icon": {"emoji": "📋"},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
        "children": [
            {"object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [{"type": "text", "text": {"content": c}}]}}
            for c in chunks
        ],
    }
    result = notion_request("/pages", method="POST", body=body)
    return result.get("url", "")

# ── 메인 ──────────────────────────────────────────────────
def main():
    print(f"[시작] 신규 매물 포스팅 자동 생성 — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    props = get_new_properties()
    print(f"[조회] 접수 상태 매물 {len(props)}건")
    if not props:
        print("[종료] 신규 매물 없음")
        return

    posted = get_posted_ids()
    new_props = [p for p in props if p["id"] not in posted]
    print(f"[필터] 미포스팅 {len(new_props)}건")

    results = []
    for i, p in enumerate(new_props, 1):
        print(f"[{i}/{len(new_props)}] {p['매물명']} ({p['매물유형']}) 포스팅 생성 중...")
        try:
            post = generate_post(p)
            url = save_draft(p, post)
            print(f"  → 노션 저장 완료: {url}")
            results.append({"매물명": p["매물명"], "status": "ok", "url": url})
        except Exception as e:
            print(f"  → 실패: {e}")
            results.append({"매물명": p["매물명"], "status": "err", "error": str(e)})

    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n[완료] 성공 {ok}/{len(results)}건")
    with open("auto_post_output.json", "w", encoding="utf-8") as f:
        json.dump({"results": results, "run_at": datetime.datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
