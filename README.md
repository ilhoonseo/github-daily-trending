# GitHub Trending Archive

Archive of GitHub Trending repositories — daily, weekly and monthly — auto-updated every day and published as a GitHub Pages site.

**Live site:** https://ilhoonseo.github.io/github-daily-trending/

The site UI is in English. Each repository's explanation is in Korean (`description_ko` in the data files), with the original English description shown underneath. Use the Daily / Weekly / Monthly tabs to switch periods; the date picker shows the archive for the selected day.

## How it works

- Every day at 09:00 KST, GitHub Actions runs `scripts/fetch_trending.py`.
- It fetches the top 10 from [github.com/trending](https://github.com/trending) for each period — `?since=daily`, `?since=weekly`, `?since=monthly` — and saves:
  - Daily: `data/YYYY-MM-DD.json` (that day's archive), `data/trending.json` (the latest day), `data/index.json` (list of archived dates)
  - Weekly: `data/weekly/YYYY-MM-DD.json`, `data/weekly.json` (latest), `data/weekly/index.json`
  - Monthly: `data/monthly/YYYY-MM-DD.json`, `data/monthly.json` (latest), `data/monthly/index.json`
- Pushing the update triggers the Pages deployment, so the site updates automatically.

## Data

Each entry has `full_name`, `url`, `description` (English), `description_ko` (Korean), `language`, `stars`, `forks`, and `stars_period` (stars gained in that period — today / this week / this month). Daily entries also carry `stars_today` (= `stars_period`) for backward compatibility with the original daily format.

Hand-written Korean explanations (`description_ko`) are preserved per period file: an edit in a weekly file only affects that weekly entry, never the daily or monthly entry for the same repo.
