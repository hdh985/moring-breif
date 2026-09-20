"""수집할 지표 목록. 여기만 고치면 화면에 반영됩니다.

kind
  index : 지수·가격. 변동을 '포인트 (퍼센트)'로 표시, 막대는 퍼센트
  fx    : 환율. 변동을 절대값으로 표시, 막대는 퍼센트
  yield : 금리(%). 변동을 bp로 표시, 막대는 bp
"""

# ── yfinance (속도 우선) ──────────────────────────────────────────────
# stooq: yfinance가 실패할 때 쓰는 Stooq 심볼 (없으면 백업 없음)
YF_SECTIONS = [
    {
        "title": "주식",
        "hint": "국내 · 미국 · 아시아 · 유럽",
        "items": [
            {"name": "코스피", "yf": "^KS11", "kind": "index", "dec": 2},
            {"name": "코스닥", "yf": "^KQ11", "kind": "index", "dec": 2},
            {"name": "S&P 500", "yf": "^GSPC", "kind": "index", "dec": 2, "stooq": "^spx"},
            {"name": "나스닥 종합", "yf": "^IXIC", "kind": "index", "dec": 2, "stooq": "^ndq"},
            {"name": "다우존스", "yf": "^DJI", "kind": "index", "dec": 2, "stooq": "^dji"},
            {"name": "러셀 2000", "yf": "^RUT", "kind": "index", "dec": 2},
            {"name": "필라델피아 반도체", "sub": "SOX", "yf": "^SOX", "kind": "index", "dec": 2},
            {"name": "닛케이 225", "yf": "^N225", "kind": "index", "dec": 2, "stooq": "^nkx"},
            {"name": "상해종합", "yf": "000001.SS", "kind": "index", "dec": 2, "stooq": "^shc"},
            {"name": "항셍", "yf": "^HSI", "kind": "index", "dec": 2, "stooq": "^hsi"},
            {"name": "유로스톡스 50", "yf": "^STOXX50E", "kind": "index", "dec": 2},
        ],
    },
    {
        "title": "외환",
        "items": [
            {"name": "원/달러", "yf": "KRW=X", "kind": "fx", "dec": 1, "stooq": "usdkrw"},
            {"name": "달러인덱스", "sub": "DXY", "yf": "DX-Y.NYB", "kind": "index", "dec": 2},
            {"name": "달러/엔", "yf": "JPY=X", "kind": "fx", "dec": 2, "stooq": "usdjpy"},
            {"name": "유로/달러", "yf": "EURUSD=X", "kind": "fx", "dec": 4, "stooq": "eurusd"},
            {"name": "달러/위안", "yf": "CNY=X", "kind": "fx", "dec": 4, "stooq": "usdcny"},
        ],
    },
    {
        "title": "원자재",
        "hint": "에너지 · 귀금속 · 산업금속 · 농산물 (근월물 선물)",
        "items": [
            {"name": "WTI", "sub": "$/배럴", "yf": "CL=F", "kind": "index", "dec": 2, "stooq": "cl.f"},
            {"name": "브렌트", "sub": "$/배럴", "yf": "BZ=F", "kind": "index", "dec": 2, "stooq": "cb.f"},
            {"name": "천연가스", "sub": "$/MMBtu", "yf": "NG=F", "kind": "index", "dec": 3, "stooq": "ng.f"},
            {"name": "금", "sub": "$/온스", "yf": "GC=F", "kind": "index", "dec": 1, "stooq": "gc.f"},
            {"name": "은", "sub": "$/온스", "yf": "SI=F", "kind": "index", "dec": 2, "stooq": "si.f"},
            {"name": "구리", "sub": "$/파운드", "yf": "HG=F", "kind": "index", "dec": 3, "stooq": "hg.f"},
            {"name": "옥수수", "sub": "¢/부셸", "yf": "ZC=F", "kind": "index", "dec": 2},
            {"name": "밀", "sub": "¢/부셸", "yf": "ZW=F", "kind": "index", "dec": 2},
            {"name": "대두", "sub": "¢/부셸", "yf": "ZS=F", "kind": "index", "dec": 2},
        ],
    },
    {
        "title": "변동성",
        "items": [
            {"name": "VIX", "yf": "^VIX", "kind": "index", "dec": 2},
        ],
    },
]

# ── 미 재무부 일별 국채 수익률 (공식) ─────────────────────────────────
UST_TENORS = [("미 2년물", "2 Yr"), ("미 10년물", "10 Yr"), ("미 30년물", "30 Yr")]

# ── 한국은행 ECOS (공식) ──────────────────────────────────────────────
# 통계표 817Y002 = 시장금리(일별). 항목 코드는 ECOS 개발가이드의
# '통계 세부항목 목록'에서 확인하세요. 실행 로그에 ECOS가 돌려준
# 항목 이름이 찍히므로, 첫 실행 후 이름이 맞는지 꼭 확인하세요.
ECOS_ITEMS = [
    {"name": "국고채 3년", "stat": "817Y002", "item": "010200000", "cycle": "D"},
    {"name": "국고채 10년", "stat": "817Y002", "item": "010210000", "cycle": "D"},
]

# ── FRED 매크로 지표 (공식) ───────────────────────────────────────────
# mode: yoy = 전년비(%), level = 수준, diff = 전월비 증감(천 명 등)
FRED_MACRO = [
    {"name": "미 CPI", "sub": "전년비", "series": "CPIAUCSL", "mode": "yoy", "dec": 1, "unit": "%"},
    {"name": "미 근원 CPI", "sub": "전년비", "series": "CPILFESL", "mode": "yoy", "dec": 1, "unit": "%"},
    {"name": "미 실업률", "series": "UNRATE", "mode": "level", "dec": 1, "unit": "%"},
    {"name": "미 비농업 고용", "sub": "전월비, 천 명", "series": "PAYEMS", "mode": "diff", "dec": 0, "unit": ""},
    {"name": "미 PCE 물가", "sub": "전년비", "series": "PCEPI", "mode": "yoy", "dec": 1, "unit": "%"},
    {"name": "연방기금금리 상단", "series": "DFEDTARU", "mode": "level", "dec": 2, "unit": "%"},
]

# FRED 발표 일정 중 화면에 보여줄 것 (이름에 포함된 단어로 거름)
FRED_RELEASE_KEYWORDS = {
    "Consumer Price Index": "미 CPI",
    "Employment Situation": "미 고용보고서",
    "Gross Domestic Product": "미 GDP",
    "Personal Income and Outlays": "미 PCE·개인소득",
    "Advance Monthly Sales for Retail": "미 소매판매",
    "Producer Price Index": "미 PPI",
    "Job Openings and Labor Turnover": "미 JOLTS",
    "Unemployment Insurance Weekly Claims": "미 신규 실업수당 청구",
    "Industrial Production": "미 산업생산",
}

# ── CoinGecko ───────────────────────────────────────────────────────
CRYPTO = [("비트코인", "bitcoin"), ("이더리움", "ethereum")]

# 화면 상단 핵심 6개 (위에서 정의한 name과 똑같이)
KEY_TILES = ["코스피", "S&P 500", "원/달러", "미 10년물", "WTI", "금"]
