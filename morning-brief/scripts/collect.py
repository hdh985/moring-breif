"""아침 시황 수집 스크립트.

1) 시세·금리·매크로 지표를 무료 소스에서 받고
2) (선택) Claude API로 헤드라인과 요약만 쓰게 한 뒤
3) docs/data/ 아래 JSON으로 저장합니다.

환경변수 (GitHub Secrets):
  ECOS_API_KEY       한국은행 ECOS 인증키   (없으면 국고채 칸은 비워 둠)
  FRED_API_KEY       FRED API 키            (없으면 매크로·일정 칸은 비워 둠)
  ANTHROPIC_API_KEY  Claude API 키          (없으면 헤드라인 없이 숫자만)
  CLAUDE_MODEL       선택, 기본 claude-sonnet-5
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import config as C  # noqa: E402

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
UA = {"User-Agent": "Mozilla/5.0 (morning-brief)"}
TIMEOUT = 20

log_lines: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)
    log_lines.append(msg)


def get(url: str, **kw):
    """재시도 2번 붙인 GET."""
    for i in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT, **kw)
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001
            if i == 2:
                raise
            log(f"  재시도 {i + 1}: {url[:80]} ({e})")
            time.sleep(2 + i * 3)


# ── 공통: 두 개의 (날짜, 값)으로 화면용 item 만들기 ─────────────────────
def fmt(x: float, dec: int) -> str:
    return f"{x:,.{dec}f}"


def make_item(spec: dict, last: tuple[str, float] | None, prev: tuple[str, float] | None) -> dict:
    item = {"name": spec["name"], "value": None, "change": None, "bar": None, "date": None}
    if spec.get("sub"):
        item["sub"] = spec["sub"]
    if not last:
        return item
    d, v = last
    dec = spec.get("dec", 2)
    kind = spec.get("kind", "index")
    item["date"] = d
    item["value"] = (fmt(v, dec) + "%") if kind == "yield" else fmt(v, dec)
    if prev:
        p = prev[1]
        diff = v - p
        if kind == "yield":
            bp = round(diff * 100, 1)
            item["change"] = f"{abs(bp):g}bp"
            item["bar"] = bp
        else:
            pct = diff / p * 100 if p else 0.0
            item["change"] = f"{fmt(abs(diff), dec)} ({abs(pct):.2f}%)"
            item["bar"] = round(pct, 3)
    return item


# ── yfinance + Stooq 백업 ───────────────────────────────────────────
def yf_last_two(tickers: list[str]) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    try:
        import yfinance as yf

        df = yf.download(tickers, period="15d", interval="1d", group_by="ticker",
                         auto_adjust=False, progress=False, threads=True)
        for t in tickers:
            try:
                s = df[t]["Close"].dropna() if len(tickers) > 1 else df["Close"].dropna()
                pts = [(idx.strftime("%Y-%m-%d"), float(val)) for idx, val in s.tail(2).items()
                       if not math.isnan(float(val))]
                if pts:
                    out[t] = pts
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001
        log(f"yfinance 실패: {e}")
    return out


def stooq_last_two(sym: str) -> list[tuple[str, float]]:
    r = get("https://stooq.com/q/d/l/", params={"s": sym, "i": "d"})
    rows = list(csv.DictReader(io.StringIO(r.text)))
    rows = [x for x in rows if x.get("Close") not in (None, "", "N/D")]
    return [(x["Date"], float(x["Close"])) for x in rows[-2:]]


def collect_market() -> list[dict]:
    tickers = [it["yf"] for sec in C.YF_SECTIONS for it in sec["items"]]
    log(f"yfinance: {len(tickers)}개 티커 요청")
    got = yf_last_two(tickers)
    sections = []
    for sec in C.YF_SECTIONS:
        items = []
        for spec in sec["items"]:
            pts = got.get(spec["yf"], [])
            if len(pts) < 2 and spec.get("stooq"):
                try:
                    pts = stooq_last_two(spec["stooq"])
                    log(f"  Stooq 백업 사용: {spec['name']}")
                except Exception as e:  # noqa: BLE001
                    log(f"  Stooq 실패 {spec['name']}: {e}")
            if not pts:
                log(f"  값 없음: {spec['name']}")
            last = pts[-1] if pts else None
            prev = pts[-2] if len(pts) >= 2 else None
            items.append(make_item(spec, last, prev))
        sections.append({"title": sec["title"], "hint": sec.get("hint"), "items": items})
    return sections


# ── 미 재무부 국채 수익률 ────────────────────────────────────────────
def collect_ust() -> list[dict]:
    rows: list[dict] = []
    today = datetime.now(KST).date()
    years = sorted({today.year, (today - timedelta(days=10)).year})
    for y in years:
        url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
               f"daily-treasury-rates.csv/{y}/all")
        params = {"type": "daily_treasury_yield_curve", "field_tdr_date_value": str(y),
                  "page": "", "_format": "csv"}
        try:
            r = get(url, params=params)
            rows += list(csv.DictReader(io.StringIO(r.text)))
        except Exception as e:  # noqa: BLE001
            log(f"미 재무부 {y} 실패: {e}")

    def to_iso(s: str) -> str:
        return datetime.strptime(s.strip(), "%m/%d/%Y").strftime("%Y-%m-%d")

    rows = [r for r in rows if r.get("Date")]
    rows.sort(key=lambda r: to_iso(r["Date"]))
    items = []
    for name, col in C.UST_TENORS:
        pts = [(to_iso(r["Date"]), float(r[col])) for r in rows if r.get(col) not in (None, "")]
        spec = {"name": name, "kind": "yield", "dec": 3}
        items.append(make_item(spec, pts[-1] if pts else None, pts[-2] if len(pts) > 1 else None))
    log(f"미 재무부: {len(rows)}행")
    # 2-10 스프레드
    v = {i["name"]: i for i in items}
    try:
        two = float(v["미 2년물"]["value"].rstrip("%"))
        ten = float(v["미 10년물"]["value"].rstrip("%"))
        items.append({"name": "미 2-10년 스프레드", "value": f"{(ten - two) * 100:.1f}bp",
                      "change": None, "bar": None, "date": v["미 10년물"]["date"]})
    except Exception:  # noqa: BLE001
        pass
    return items


# ── 한국은행 ECOS ───────────────────────────────────────────────────
def collect_ecos() -> list[dict]:
    key = os.getenv("ECOS_API_KEY")
    items = []
    end = datetime.now(KST).date()
    start = end - timedelta(days=20)
    for spec in C.ECOS_ITEMS:
        base = {"name": spec["name"], "kind": "yield", "dec": 3}
        if not key:
            items.append(make_item(base, None, None))
            continue
        url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/100/"
               f"{spec['stat']}/{spec['cycle']}/{start:%Y%m%d}/{end:%Y%m%d}/{spec['item']}")
        try:
            data = get(url).json()
            rows = data.get("StatisticSearch", {}).get("row", [])
            if not rows:
                log(f"ECOS 응답 없음 {spec['name']}: {json.dumps(data, ensure_ascii=False)[:200]}")
            else:
                log(f"ECOS {spec['name']} → ECOS 항목명: {rows[-1].get('ITEM_NAME1')}")
            pts = [(f"{r['TIME'][:4]}-{r['TIME'][4:6]}-{r['TIME'][6:8]}", float(r["DATA_VALUE"]))
                   for r in rows if r.get("DATA_VALUE")]
            items.append(make_item(base, pts[-1] if pts else None, pts[-2] if len(pts) > 1 else None))
        except Exception as e:  # noqa: BLE001
            log(f"ECOS 실패 {spec['name']}: {e}")
            items.append(make_item(base, None, None))
    return items


# ── FRED ────────────────────────────────────────────────────────────
def fred_obs(series: str, key: str, limit: int = 15) -> list[tuple[str, float]]:
    r = get("https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": series, "api_key": key, "file_type": "json",
                    "sort_order": "desc", "limit": limit})
    obs = [(o["date"], float(o["value"])) for o in r.json()["observations"] if o["value"] != "."]
    return list(reversed(obs))


def collect_fred_macro() -> list[dict]:
    key = os.getenv("FRED_API_KEY")
    items = []
    for spec in C.FRED_MACRO:
        it = {"name": spec["name"], "sub": spec.get("sub"), "value": None, "change": None,
              "bar": None, "date": None}
        if not key:
            items.append(it)
            continue
        try:
            obs = fred_obs(spec["series"], key)
            dec, unit = spec["dec"], spec["unit"]
            if spec["mode"] == "yoy" and len(obs) >= 14:
                cur = (obs[-1][1] / obs[-13][1] - 1) * 100
                prv = (obs[-2][1] / obs[-14][1] - 1) * 100
            elif spec["mode"] == "diff" and len(obs) >= 3:
                cur = obs[-1][1] - obs[-2][1]
                prv = obs[-2][1] - obs[-3][1]
            else:
                cur, prv = obs[-1][1], obs[-2][1]
            d = obs[-1][0]
            it["date"] = d
            it["value"] = f"{cur:,.{dec}f}{unit}"
            it["change"] = f"직전 {prv:,.{dec}f}{unit}"
            it["bar"] = None if abs(cur - prv) < 1e-9 else (1 if cur > prv else -1)
            it["note"] = f"{d[:7]} 기준" if spec["series"] != "DFEDTARU" else None
        except Exception as e:  # noqa: BLE001
            log(f"FRED 실패 {spec['name']}: {e}")
        items.append(it)
    return items


def collect_fred_calendar() -> list[dict]:
    key = os.getenv("FRED_API_KEY")
    if not key:
        return []
    today = datetime.now(KST).date()
    try:
        r = get("https://api.stlouisfed.org/fred/releases/dates",
                params={"api_key": key, "file_type": "json",
                        "realtime_start": today.isoformat(),
                        "realtime_end": (today + timedelta(days=9)).isoformat(),
                        "include_release_dates_with_no_data": "true",
                        "sort_order": "asc", "limit": 1000})
        seen, out = set(), []
        for rd in r.json().get("release_dates", []):
            for kw, ko in C.FRED_RELEASE_KEYWORDS.items():
                if kw.lower() in rd.get("release_name", "").lower():
                    k = (rd["date"], ko)
                    if k not in seen:
                        seen.add(k)
                        d = date.fromisoformat(rd["date"])
                        out.append({"date": f"{d.month}/{d.day} {'월화수목금토일'[d.weekday()]}",
                                    "title": ko, "detail": rd["release_name"], "_iso": rd["date"]})
        out.sort(key=lambda x: x["_iso"])
        for x in out:
            x.pop("_iso")
        return out[:10]
    except Exception as e:  # noqa: BLE001
        log(f"FRED 일정 실패: {e}")
        return []


# ── CoinGecko ───────────────────────────────────────────────────────
def collect_crypto() -> list[dict]:
    items = []
    try:
        ids = ",".join(i for _, i in C.CRYPTO)
        j = get("https://api.coingecko.com/api/v3/simple/price",
                params={"ids": ids, "vs_currencies": "usd", "include_24hr_change": "true"}).json()
        for name, cid in C.CRYPTO:
            d = j.get(cid, {})
            px, ch = d.get("usd"), d.get("usd_24h_change")
            items.append({"name": name, "sub": "달러, 24시간 변동",
                          "value": fmt(px, 0) if px else None,
                          "change": f"{abs(ch):.2f}%" if ch is not None else None,
                          "bar": round(ch, 3) if ch is not None else None,
                          "date": datetime.now(KST).strftime("%Y-%m-%d")})
    except Exception as e:  # noqa: BLE001
        log(f"CoinGecko 실패: {e}")
        items = [{"name": n, "value": None, "change": None, "bar": None, "date": None} for n, _ in C.CRYPTO]
    return items


# ── Claude: 숫자를 받아 헤드라인·요약만 작성 ─────────────────────────
def summarize(brief: dict) -> dict:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return {}
    compact = []
    for s in brief["sections"]:
        for i in s["items"]:
            if i.get("value"):
                sign = "" if i.get("bar") is None else ("+" if i["bar"] > 0 else "-" if i["bar"] < 0 else "")
                compact.append(f"{s['title']} | {i['name']} | {i['value']} | {sign}{i.get('change') or ''} | {i.get('date')}")
    prompt = (
        "아래는 오늘 아침 시황판에 들어갈 지표 데이터다. 형식: 섹션 | 지표 | 값 | 전일대비 | 기준일\n"
        + "\n".join(compact)
        + "\n\n이 데이터만 근거로 한국어 아침 시황 헤드라인과 요약을 써라.\n"
        "규칙:\n"
        "- 데이터에 없는 수치, 뉴스, 원인(예: 특정 발언, 지정학 이벤트)을 지어내지 마라. 원인을 모르면 움직임만 서술한다.\n"
        "- headline: 40자 이내 한 문장, 가장 중요한 흐름 하나.\n"
        "- summary: 4~5개 문장. 주식·금리·외환·원자재 사이의 연결(예: 금리 상승과 성장주)을 짚되 단정하지 말 것.\n"
        "- 투자 권유 표현 금지.\n"
        '응답은 JSON만: {"headline": "...", "summary": ["...", "..."]}'
    )
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": os.getenv("CLAUDE_MODEL") or "claude-sonnet-5", "max_tokens": 1200,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=90,
        )
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        out = json.loads(text)
        return {"headline": str(out.get("headline", "")), "summary": [str(x) for x in out.get("summary", [])][:6]}
    except Exception as e:  # noqa: BLE001
        log(f"Claude 요약 실패 (숫자만 게시): {e}")
        return {}


# ── 조립 ────────────────────────────────────────────────────────────
def main() -> None:
    now = datetime.now(KST)
    brief_id = now.strftime("%Y-%m-%d")
    log(f"== 아침 시황 수집 {now:%Y-%m-%d %H:%M} KST ==")

    market = collect_market()
    rates = collect_ust() + collect_ecos()
    sections = [market[0],
                {"title": "금리", "hint": "변동폭은 bp(0.01%p)", "items": rates},
                *market[1:3],
                {"title": "미국 매크로 지표", "hint": "최근 발표치 · 직전치", "items": collect_fred_macro()},
                {"title": "변동성 · 가상자산", "items": market[3]["items"] + collect_crypto()}]

    by_name = {i["name"]: i for s in sections for i in s["items"]}
    keys = [{k: by_name[n].get(k) for k in ("name", "value", "change", "bar")}
            for n in C.KEY_TILES if n in by_name]

    us_dates = [i["date"] for i in market[0]["items"] if i["name"] == "S&P 500" and i["date"]]
    kr_dates = [i["date"] for i in market[0]["items"] if i["name"] == "코스피" and i["date"]]
    basis = "기준: " + " · ".join(filter(None, [
        f"한국 {kr_dates[0][5:].replace('-', '/')} 종가" if kr_dates else None,
        f"미국 {us_dates[0][5:].replace('-', '/')} 종가" if us_dates else None,
    ])) + f" · {now:%m/%d %H:%M} 자동 수집"

    filled = sum(1 for s in sections for i in s["items"] if i.get("value"))
    total = sum(len(s["items"]) for s in sections)
    log(f"채워진 지표 {filled}/{total}")

    brief = {
        "date": brief_id,
        "label": f"{now.month}월 {now.day}일 ({'월화수목금토일'[now.weekday()]}) 아침",
        "basis": basis,
        "headline": "",
        "summary": [],
        "keys": keys,
        "sections": sections,
        "events": {"past": [], "upcoming": collect_fred_calendar()},
        "sources": [
            {"name": "Yahoo Finance(yfinance)", "url": "https://finance.yahoo.com"},
            {"name": "Stooq", "url": "https://stooq.com"},
            {"name": "미 재무부", "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates"},
            {"name": "한국은행 ECOS", "url": "https://ecos.bok.or.kr"},
            {"name": "FRED", "url": "https://fred.stlouisfed.org"},
            {"name": "CoinGecko", "url": "https://www.coingecko.com"},
        ],
        "stats": {"filled": filled, "total": total},
    }
    brief.update(summarize(brief))
    if not brief["headline"]:
        brief["headline"] = "오늘의 지표"

    if filled < total * 0.3:
        log("채워진 지표가 너무 적어 저장하지 않습니다 (소스 장애 의심).")
        sys.exit(1)

    (DATA / "briefs").mkdir(parents=True, exist_ok=True)
    (DATA / "briefs" / f"{brief_id}.json").write_text(json.dumps(brief, ensure_ascii=False, indent=1), "utf-8")
    (DATA / "latest.json").write_text(json.dumps(brief, ensure_ascii=False, indent=1), "utf-8")
    ids = sorted((p.stem for p in (DATA / "briefs").glob("*.json")), reverse=True)[:120]
    (DATA / "index.json").write_text(json.dumps(ids, ensure_ascii=False), "utf-8")
    log(f"저장 완료: docs/data/briefs/{brief_id}.json")


if __name__ == "__main__":
    main()
