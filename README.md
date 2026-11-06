# GitHub Daily Trending

Daily archive of GitHub Trending repositories — auto-updated every day and published as a GitHub Pages site.

**Live site:** https://ilhoonseo.github.io/github-daily-trending/

The site UI is in English. Each repository's explanation is in Korean (`description_ko` in the data files), with the original English description shown underneath.

## How it works

- Every day at 09:00 KST, GitHub Actions runs `scripts/fetch_trending.py`.
- It fetches the top 10 from [github.com/trending?since=daily](https://github.com/trending?since=daily) and saves:
  - `data/YYYY-MM-DD.json` — that day's archive
  - `data/trending.json` — the latest day
  - `data/index.json` — list of archived dates
- Pushing the update triggers the Pages deployment, so the site updates automatically.

## Data

Each entry has `full_name`, `url`, `description` (English), `description_ko` (Korean), `language`, `stars`, `forks`, and `stars_today`.
