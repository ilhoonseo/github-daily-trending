#!/usr/bin/env python3
"""Fetch GitHub Trending (daily) and save it as JSON + Markdown.

- Source: https://github.com/trending?since=daily
- Output: data/YYYY-MM-DD.json, data/trending.json, data/index.json
- description_ko: tries the free MyMemory translation API (en -> ko).
  If translation fails, it falls back to the original English text,
  so the daily job never fails just because translation is unavailable.
  Manual Korean edits in data files are preserved only for that date;
  the script does not overwrite a date file that already has
  hand-written description_ko values unless the repo list changed.
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
TRENDING_URL = "https://github.com/trending?since=daily"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


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
    """Best-effort English -> Korean via MyMemory. Returns None on failure."""
    if not text:
        return None
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
            return out
    except Exception:
        pass
    return None


def fetch_trending():
    req = urllib.request.Request(TRENDING_URL, headers=HEADERS)
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
        today_m = re.search(r"([\d,]+)\s+stars today", art)
        stars_today = parse_number(today_m.group(1)) if today_m else None
        repos.append(
            {
                "rank": len(repos) + 1,
                "full_name": full_name,
                "url": f"https://github.com/{full_name}",
                "description": description,
                "description_ko": description,
                "language": language,
                "stars": stars,
                "forks": forks,
                "stars_today": stars_today,
            }
        )
    return repos


def main():
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).strftime("%Y-%m-%d")
    fetched_at = datetime.now(kst).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    repos = fetch_trending()
    if not repos:
        raise SystemExit("No trending repos parsed; refusing to overwrite data.")

    # Preserve hand-written Korean explanations for the same date, if any.
    date_path = DATA / f"{today}.json"
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

    DATA.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": today,
        "fetched_at": fetched_at,
        "source": TRENDING_URL,
        "repos": repos,
    }
    date_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DATA / "trending.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    index_path = DATA / "index.json"
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
    print(f"Saved {len(repos)} repos for {today}")


if __name__ == "__main__":
    main()
