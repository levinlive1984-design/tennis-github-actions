import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from curl_cffi import requests

# ==========================================
# 參數設定區
# ==========================================
ENABLE_ODDS_FILTER = True
MIN_ODDS = 1.70
MAX_ODDS = 1.80
TIMEZONE_OFFSET_HOURS = 8  # Taiwan = UTC+8
OUTPUT_DIR = Path("docs")


class PinnacleCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Referer": "https://www.pinnacle.com/",
            "x-api-key": "VjI6d2ViLWRlc2t0b3A6Z3Vlc3Q6Z3Vlc3Q=",
        }
        self.matchups_url = "https://guest.api.arcadia.pinnacle.com/0.1/sports/33/matchups?withSpecials=false"
        self.odds_url = "https://guest.api.arcadia.pinnacle.com/0.1/sports/33/markets/straight?primaryOnly=false&withSpecials=false"

    def fetch_data(self):
        try:
            matchups_response = requests.get(
                self.matchups_url,
                headers=self.headers,
                impersonate="chrome110",
                timeout=30,
            )
            odds_response = requests.get(
                self.odds_url,
                headers=self.headers,
                impersonate="chrome110",
                timeout=30,
            )
            matchups_response.raise_for_status()
            odds_response.raise_for_status()
            return matchups_response.json(), odds_response.json()
        except Exception as exc:
            print(f"❌ 數據抓取異常: {exc}")
            return [], []

    @staticmethod
    def convert_odds(american):
        if american in ["鎖盤中", None]:
            return None
        try:
            val = float(american)
            return round((val / 100.0) + 1.0 if val > 0 else (100.0 / abs(val)) + 1.0, 3)
        except Exception:
            return None

    @staticmethod
    def parse_time(item):
        utc_time = item.get("startTime")
        if not utc_time:
            for period in item.get("periods", []):
                if period.get("period") == 0:
                    utc_time = period.get("cutoffAt")
                    break

        if not utc_time:
            return {
                "start_time_raw": None,
                "start_time_taiwan": "未知",
            }

        try:
            dt_utc = datetime.fromisoformat(utc_time.replace("Z", "+00:00"))
            dt_tw = dt_utc + timedelta(hours=TIMEZONE_OFFSET_HOURS)
            return {
                "start_time_raw": utc_time,
                "start_time_taiwan": dt_tw.strftime("%Y-%m-%d %H:%M"),
            }
        except Exception:
            return {
                "start_time_raw": utc_time,
                "start_time_taiwan": "錯誤",
            }


def build_odds_map(crawler, odds):
    odds_map = {}
    for market in odds:
        if market.get("type") == "moneyline" and market.get("period") == 0:
            prices = {p.get("designation"): p.get("price") for p in market.get("prices", [])}
            odds_map[market.get("matchupId")] = {
                "home": crawler.convert_odds(prices.get("home")),
                "away": crawler.convert_odds(prices.get("away")),
            }
    return odds_map


def find_low_odds_side(home_name, away_name, home_odds, away_odds):
    candidates = []
    if isinstance(home_odds, float) and MIN_ODDS <= home_odds <= MAX_ODDS:
        candidates.append(("home", home_name, home_odds))
    if isinstance(away_odds, float) and MIN_ODDS <= away_odds <= MAX_ODDS:
        candidates.append(("away", away_name, away_odds))

    if not candidates:
        return None

    # 若兩邊都剛好落在區間，取較低賠的一方作為 low_odds_player。
    candidates.sort(key=lambda x: x[2])
    side, player, odds = candidates[0]
    return {
        "low_odds_side": side,
        "low_odds_player": player,
        "low_odds": odds,
    }


def collect_matches():
    crawler = PinnacleCrawler()
    matchups, odds = crawler.fetch_data()
    odds_map = build_odds_map(crawler, odds)

    results = []
    for matchup in matchups:
        matchup_id = matchup.get("id")
        participants = {p.get("alignment"): p.get("name") for p in matchup.get("participants", [])}
        home_name = participants.get("home", "未知")
        away_name = participants.get("away", "未知")
        home_odds = odds_map.get(matchup_id, {}).get("home")
        away_odds = odds_map.get(matchup_id, {}).get("away")

        low_odds_info = find_low_odds_side(home_name, away_name, home_odds, away_odds)
        if ENABLE_ODDS_FILTER and not low_odds_info:
            continue

        time_info = crawler.parse_time(matchup)
        league = matchup.get("league", {}).get("name")

        results.append({
            "matchup_id": matchup_id,
            "start_time_taiwan": time_info["start_time_taiwan"],
            "start_time_raw": time_info["start_time_raw"],
            "league": league,
            "home": home_name,
            "away": away_name,
            "home_odds": home_odds,
            "away_odds": away_odds,
            "low_odds_side": low_odds_info["low_odds_side"] if low_odds_info else None,
            "low_odds_player": low_odds_info["low_odds_player"] if low_odds_info else None,
            "low_odds": low_odds_info["low_odds"] if low_odds_info else None,
            "source": "Pinnacle guest API",
        })

    results.sort(key=lambda row: row.get("start_time_raw") or "")
    return results


def write_outputs(matches):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at_utc = datetime.now(timezone.utc)
    generated_at_tw = generated_at_utc + timedelta(hours=TIMEZONE_OFFSET_HOURS)

    payload = {
        "generated_at_utc": generated_at_utc.isoformat(timespec="seconds"),
        "generated_at_taiwan": generated_at_tw.strftime("%Y-%m-%d %H:%M:%S"),
        "filter": {
            "market": "tennis moneyline",
            "low_odds_min": MIN_ODDS,
            "low_odds_max": MAX_ODDS,
            "timezone": "Asia/Taipei",
        },
        "count": len(matches),
        "matches": matches,
    }

    json_path = OUTPUT_DIR / "today_matches.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append(f"更新時間：{payload['generated_at_taiwan']} 台灣時間")
    lines.append(f"篩選條件：低賠方歐賠 {MIN_ODDS:.2f}～{MAX_ODDS:.2f}")
    lines.append(f"符合場數：{len(matches)}")
    lines.append("")

    for idx, match in enumerate(matches, start=1):
        lines.append(
            f"{idx}. {match['start_time_taiwan']} | {match['league']} | "
            f"{match['home']} vs {match['away']} | "
            f"主勝 {match['home_odds']} / 客勝 {match['away_odds']} | "
            f"低賠方：{match['low_odds_player']} ({match['low_odds']})"
        )

    txt_path = OUTPUT_DIR / "today_matches.txt"
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    html_rows = "\n".join(
        f"<tr><td>{m['start_time_taiwan']}</td><td>{m['league']}</td>"
        f"<td>{m['home']} vs {m['away']}</td>"
        f"<td>{m['home_odds']}</td><td>{m['away_odds']}</td>"
        f"<td>{m['low_odds_player']} ({m['low_odds']})</td></tr>"
        for m in matches
    )
    if not html_rows:
        html_rows = "<tr><td colspan='6'>目前沒有符合條件的賽事</td></tr>"

    html = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>今日網球 1.70-1.80 低賠方篩選</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; line-height: 1.55; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f3f3f3; }}
    code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>今日網球 1.70–1.80 低賠方篩選</h1>
  <p>更新時間：{payload['generated_at_taiwan']} 台灣時間</p>
  <p>符合場數：{len(matches)}</p>
  <p>GPT 專案建議讀取：<code>today_matches.json</code></p>
  <p><a href="today_matches.json">JSON</a> / <a href="today_matches.txt">TXT</a></p>
  <table>
    <thead>
      <tr>
        <th>開賽時間</th><th>聯賽</th><th>對戰</th><th>主勝</th><th>客勝</th><th>低賠方</th>
      </tr>
    </thead>
    <tbody>
      {html_rows}
    </tbody>
  </table>
</body>
</html>
"""
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")

    print(f"✅ 已輸出 {json_path}, {txt_path}, {OUTPUT_DIR / 'index.html'}")
    if matches:
        print(pd.DataFrame(matches))
    else:
        print("⚠️ 無符合篩選條件的賽事")


def main():
    matches = collect_matches()
    write_outputs(matches)


if __name__ == "__main__":
    main()
