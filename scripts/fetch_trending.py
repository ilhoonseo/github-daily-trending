#!/usr/bin/env python3
"""Fetch GitHub Trending (daily, weekly, monthly) and save it as JSON.

- Sources: https://github.com/trending?since=daily|weekly|monthly
- Output (daily, unchanged layout for backward compatibility):
    data/YYYY-MM-DD.json, data/trending.json, data/index.json
- Output (weekly / monthly):
    data/weekly/YYYY-MM-DD.json, data/weekly.json, data/weekly/index.json
    data/monthly/YYYY-MM-DD.json, data/monthly.json, data/monthly/index.json
- description_ko: tries the free MyMemory translation API (en -> ko).
  If translation fails, it falls back to the original English text,
  so the job never fails just because translation is unavailable.
  Manual Korean edits are preserved per period file: a hand-written
  description_ko in data/weekly/YYYY-MM-DD.json only applies to the
  weekly entry for that repo/date, never to daily or monthly, and
  vice versa.
- Each repo entry carries "stars_period" (stars gained in the period).
  Daily entries also carry "stars_today" (= stars_period) so older
  consumers of data/trending.json keep working.
"""
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# period -> (since query value, stars label on the trending page)
PERIODS = {
    "daily": ("daily", "stars today"),
    "weekly": ("weekly", "stars this week"),
    "monthly": ("monthly", "stars this month"),
}

_translation_cache = {}


def clean(text):
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def parse_number(text):
    text = (text or "").replace(",", "").strip()
    if text.endswith("k"):
        try:
            return int(float(text[:-1]) * 1000)
        except ValueError:
            return None
    try:
        return int(text)
    except ValueError:
        return None


def translate_ko(text):
    """Best-effort English -> Korean via MyMemory. Returns None on failure.

    Results are cached per description text within a run, so a repo that
    appears in more than one period is translated only once.
    """
    if not text:
        return None
    if text in _translation_cache:
        return _translation_cache[text]
    result = None
    try:
        q = urllib.parse.urlencode({"q": text, "langpair": "en|ko"})
        req = urllib.request.Request(
            f"https://api.mymemory.translated.net/get?{q}", headers=HEADERS
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        out = payload.get("responseData", {}).get("translatedText", "")
        out = clean(out)
        if out and out.lower() != text.lower() and "QUERY LENGTH LIMIT" not in out:
            result = out
    except Exception:
        pass
    _translation_cache[text] = result
    return result


def fetch_trending(period):
    since, stars_label = PERIODS[period]
    url = f"https://github.com/trending?since={since}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "replace")

    articles = re.findall(r'<article class="Box-row".*?</article>', html, re.S)
    repos = []
    for art in articles[:10]:
        # Repo link is inside <h2 class="h3 ...">, not the Sponsor link.
        m = re.search(r'<h2[^>]*>.*?<a[^>]*href="/([^"/]+/[^"/]+)"', art, re.S)
        if not m:
            continue
        full_name = m.group(1).strip("/")
        # Description is the <p class="col-9 ..."> paragraph.
        desc_m = re.search(r'<p class="col-9[^"]*"[^>]*>(.*?)</p>', art, re.S) or re.search(
            r'<p[^>]*>(.*?)</p>', art, re.S
        )
        description = clean(re.sub(r"<[^>]+>", "", desc_m.group(1))) if desc_m else ""
        # Strip a leading "owner / repo" that some layouts include in the text.
        description = re.sub(
            rf"^{re.escape(full_name.split('/')[0])}\s*/\s*{re.escape(full_name.split('/')[1])}\s*",
            "",
            description,
        )
        description = re.sub(r"^Star\s+", "", description)
        lang_m = re.search(r'itemprop="programmingLanguage"[^>]*>([^<]+)</', art)
        language = clean(lang_m.group(1)) if lang_m else None
        # Stars / forks: number appears inside the link, after an <svg>.
        def link_number(kind):
            mm = re.search(
                rf'href="/{re.escape(full_name)}/{kind}"[^>]*>(.*?)</a>', art, re.S
            )
            if not mm:
                return None
            txt = clean(re.sub(r"<[^>]+>", " ", mm.group(1)))
            return parse_number(txt.split()[0]) if txt else None

        stars = link_number("stargazers")
        forks = link_number("forks")
        period_m = re.search(rf"([\d,]+)\s+{re.escape(stars_label)}", art)
        stars_period = parse_number(period_m.group(1)) if period_m else None
        entry = {
            "rank": len(repos) + 1,
            "full_name": full_name,
            "url": f"https://github.com/{full_name}",
            "description": description,
            "description_ko": description,
            "language": language,
            "stars": stars,
            "forks": forks,
            "stars_period": stars_period,
        }
        if period == "daily":
            # Backward compatibility with the original daily format.
            entry["stars_today"] = stars_period
        repos.append(entry)
    return repos


def period_dir(period):
    """data/ for daily, data/weekly/ and data/monthly/ otherwise."""
    return DATA if period == "daily" else DATA / period


def latest_filename(period):
    return "trending.json" if period == "daily" else f"{period}.json"


def save_period(period, today, fetched_at):
    repos = fetch_trending(period)
    if not repos:
        raise SystemExit(f"No trending repos parsed for {period}; refusing to overwrite data.")

    # Preserve hand-written Korean explanations for this period/date only.
    date_path = period_dir(period) / f"{today}.json"
    old_ko = {}
    if date_path.exists():
        try:
            old = json.loads(date_path.read_text(encoding="utf-8"))
            old_ko = {r["full_name"]: r.get("description_ko") for r in old.get("repos", [])}
        except Exception:
            old_ko = {}

    for repo in repos:
        if repo["full_name"] in old_ko and old_ko[repo["full_name"]]:
            repo["description_ko"] = old_ko[repo["full_name"]]
        else:
            ko = translate_ko(repo["description"])
            if ko:
                repo["description_ko"] = ko

    period_dir(period).mkdir(parents=True, exist_ok=True)
    payload = {
        "period": period,
        "date": today,
        "fetched_at": fetched_at,
        "source": f"https://github.com/trending?since={PERIODS[period][0]}",
        "repos": repos,
    }
    date_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (period_dir(period) / latest_filename(period)).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    index_path = period_dir(period) / "index.json"
    dates = []
    if index_path.exists():
        try:
            dates = json.loads(index_path.read_text(encoding="utf-8")).get("dates", [])
        except Exception:
            dates = []
    if today not in dates:
        dates.append(today)
    dates = sorted(set(dates))
    index_path.write_text(
        json.dumps({"dates": dates}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Saved {len(repos)} {period} repos for {today}")
    return repos


def main():
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime("%Y-%m-%d")
    fetched_at = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    for period in ("daily", "weekly", "monthly"):
        save_period(period, today, fetched_at)


if __name__ == "__main__":
    main()
