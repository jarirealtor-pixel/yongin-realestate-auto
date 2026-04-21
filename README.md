# 🏠 용인 부동산 자동화 시스템

노션 매물 DB ↔ Claude AI ↔ 네이버 포스팅 자동화 파이프라인

---

## 📁 구조

```
.
├── .github/workflows/
│   ├── weekly_report.yml     # 매주 월요일 주간 시세 리포트
│   └── auto_post.yml         # 매일 3회 신규 매물 포스팅
├── scripts/
│   ├── weekly_report.py      # 주간 시세 리포트 생성기
│   └── auto_post_new.py      # 신규 매물 자동 포스팅 생성기
└── README.md
```

---

## ⚙️ GitHub Secrets 설정

GitHub 저장소 → Settings → Secrets and variables → Actions → New repository secret

| Secret 이름              | 값                                                            |
|--------------------------|---------------------------------------------------------------|
| `ANTHROPIC_API_KEY`      | Anthropic API 키 (https://console.anthropic.com)              |
| `NOTION_API_KEY`         | 노션 Integration 키 (https://www.notion.so/my-integrations)   |
| `NOTION_DB_ID`           | 매물 DB collection ID: `a7c0d8f0-872b-4430-8e0d-fb5b1a67300b` |
| `NOTION_DRAFT_PAGE_ID`   | 포스팅 초안 DB 페이지 ID: `3492d8c6-dae5-81b4-9eba-d0fdf892bade` |
| `MOLIT_API_KEY`          | 국토부 실거래가 API 키 (선택, https://www.data.go.kr)          |

---

## 🚀 배포 방법

### 1단계: 노션 Integration 연결

1. https://www.notion.so/my-integrations → 새 통합 생성
2. "부동산 자동화 봇" 이름으로 생성 → API 키 복사
3. 노션 매물 DB 페이지 → "..." → 연결 추가 → 방금 만든 봇 선택
4. 포스팅 초안 DB 페이지도 동일하게 연결

### 2단계: GitHub 저장소 생성

```bash
git init
git add .
git commit -m "초기 설정"
git remote add origin https://github.com/YOUR_ID/yongin-realestate-auto.git
git push -u origin main
```

### 3단계: Secrets 등록

GitHub → Settings → Secrets → 위 표의 값들 등록

### 4단계: 워크플로우 활성화

- GitHub → Actions 탭 → 워크플로우 활성화 확인
- "신규 매물 자동 포스팅 생성" → Run workflow 클릭해서 테스트

---

## ⏰ 자동 실행 스케줄

| 워크플로우          | 실행 시각            | 동작                            |
|---------------------|----------------------|---------------------------------|
| 주간 시세 리포트    | 매주 월요일 08:00 KST | 용인 부동산 주간 리포트 → 노션  |
| 신규 매물 포스팅    | 매일 09:00 KST        | 접수 매물 감지 → 포스팅 → 노션  |
|                     | 매일 13:00 KST        | 〃                              |
|                     | 매일 18:00 KST        | 〃                              |

---

## 📊 Make(구 Integromat) Zapier 연동

Make 시나리오로 노션 DB 변경 감지 + 추가 자동화:

```
노션 DB 매물 상태 변경 (접수→진행중)
  └→ Make Webhook 트리거
      └→ Claude API 포스팅 생성
          └→ 노션 초안 저장
              └→ 카카오채널 알림 발송
```

자세한 설정은 노션 "자동화 설정 가이드" 페이지를 참고하세요.

---

## 🔧 수동 실행

```bash
# 주간 리포트 로컬 테스트
cd scripts
ANTHROPIC_API_KEY=sk-... NOTION_API_KEY=secret_... \
NOTION_DRAFT_PAGE_ID=3492d8c6... python weekly_report.py

# 신규 매물 포스팅 테스트
ANTHROPIC_API_KEY=sk-... NOTION_API_KEY=secret_... \
NOTION_DB_ID=a7c0d8f0... NOTION_DRAFT_PAGE_ID=3492d8c6... \
python auto_post_new.py
```
