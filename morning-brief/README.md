# 아침 시황판

평일 아침 6시(KST) 무렵 GitHub Actions가 지표를 모아 `docs/data/`에 JSON으로 저장하고, GitHub Pages가 그 JSON으로 화면을 그립니다. 서버는 없습니다.

## 데이터 흐름

| 영역 | 소스 | 키 필요 |
|---|---|---|
| 주가지수 · 환율 · 원자재 선물 · VIX | yfinance (실패 시 Stooq) | 없음 |
| 미 국채 2·10·30년 | 미 재무부 일별 수익률 곡선 | 없음 |
| 국고채 3·10년 | 한국은행 ECOS | `ECOS_API_KEY` |
| 미 CPI·고용·PCE·기준금리, 발표 일정 | FRED | `FRED_API_KEY` |
| 비트코인 · 이더리움 | CoinGecko | 없음 |
| 헤드라인 · 요약 문장 | Claude API (숫자만 입력) | `ANTHROPIC_API_KEY` |

키가 없는 소스는 건너뛰고 해당 칸만 "—"로 비웁니다. 키 없이도 절반 이상은 채워집니다.

## 설정 (한 번만)

1. 이 폴더를 새 GitHub 저장소에 올립니다.
2. **API 키 발급** (모두 무료, Claude API만 사용량 과금)
   - ECOS: ecos.bok.or.kr → 개발 명세서 → 인증키 신청
   - FRED: fredaccount.stlouisfed.org → API Keys
   - Claude: console.anthropic.com → API Keys
3. 저장소 **Settings → Secrets and variables → Actions → New repository secret**에 `ECOS_API_KEY`, `FRED_API_KEY`, `ANTHROPIC_API_KEY`를 넣습니다. 코드에는 절대 키를 적지 마세요.
4. **Settings → Pages**에서 Source를 `Deploy from a branch`, 브랜치 `main`, 폴더 `/docs`로 지정합니다.
5. **Actions 탭 → 아침 시황 수집 → Run workflow**로 한 번 수동 실행해 봅니다. 몇 분 뒤 Pages 주소에 첫 브리프가 뜹니다.

## 첫 실행 후 확인할 것

- **ECOS 항목 코드**: 실행 로그에 `ECOS 국고채 3년 → ECOS 항목명: ...`이 찍힙니다. 이름이 국고채 3년/10년이 아니면 ECOS 개발가이드의 통계 세부항목 목록에서 코드를 찾아 `scripts/config.py`의 `ECOS_ITEMS`를 고치세요.
- **"값 없음" 로그**: yfinance 티커가 바뀌었거나 일시 장애입니다. 며칠 계속되면 `config.py`에서 티커를 바꾸거나 `stooq` 백업 심볼을 추가하세요.
- 채워진 지표가 30% 미만이면 소스 장애로 보고 저장하지 않습니다(전날 화면 유지).

## 알아둘 점

- 실행 시각은 GitHub 서버 사정에 따라 수 분~수십 분 늦을 수 있습니다. 더 이르게 받고 싶으면 `.github/workflows/morning.yml`의 크론을 앞당기세요. 크론은 UTC 기준입니다.
- 공개 저장소는 60일간 활동이 없으면 예약 실행이 꺼지지만, 매일 데이터를 커밋하므로 보통은 문제없습니다.
- yfinance는 야후의 비공식 API라 예고 없이 막힐 수 있고, 데이터 재배포에 약관상 제약이 있을 수 있습니다. 개인용이 아니라 공개 서비스로 운영할 계획이면 약관을 확인하세요.
- 원자재는 근월물 선물 기준이라, 만기 교체 시점에 전일 대비가 튀어 보일 수 있습니다.
- 요약 문장은 Claude가 수치만 보고 쓰도록 지시되어 있어 뉴스 원인(예: 특정 발언)은 담기지 않습니다.

## 지표 추가·변경

`scripts/config.py`만 고치면 됩니다. 예를 들어 코스피200을 추가하려면 주식 섹션 `items`에 한 줄을 넣으세요.

```python
{"name": "코스피 200", "yf": "^KS200", "kind": "index", "dec": 2},
```

## 로컬 실행

```bash
pip install -r requirements.txt
export FRED_API_KEY=... ECOS_API_KEY=... ANTHROPIC_API_KEY=...
python scripts/collect.py
cd docs && python -m http.server 8000   # http://localhost:8000
```
