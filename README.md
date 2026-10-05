# Clocked

Guess the NFL player from a blacked-out card. Active, Retired, and Last Week modes, four difficulties.

`index.html` is the whole site. Everything else is the machinery that rebuilds it with fresh stats.

## Put it online (one time, ~15 minutes)

1. **GitHub:** create a free account, make a new repository called `clocked`, and upload everything in this folder (drag the files into the "uploading an existing file" page). Upload the hidden `.github` folder too; if your computer hides it, create the file `.github/workflows/update.yml` in GitHub's editor and paste its contents.
2. **Hosting:** sign up for Cloudflare Pages (or Netlify), choose "Connect to Git", pick the `clocked` repo. Build command: *(leave empty)*. Output directory: `/`. Deploy. You get a free `something.pages.dev` link right away.
3. **Domain (optional, ~$10–20/yr):** buy one (e.g. playclocked.com) and add it under your Pages project's "Custom domains".
4. **Share link:** in the GitHub repo go to Settings → Secrets and variables → Actions → Variables, add `SITE_URL` = your site address (e.g. `https://playclocked.com`). Posts to X will include this link.
5. **First update:** Actions tab → "Weekly data update" → Run workflow. After that it runs by itself every Tuesday and Friday morning.

## Daily limit

Players get 6 per day each in Active, Retired, and Last Week (shared across difficulties; the daily counts as one). A player counts on the first guess, so browsing is free, and an unfinished game survives a refresh. Resets at midnight local time. To change it, edit `const LIMIT=6;` in `src/template.html` and rebuild. This limit lives in the browser, so a determined person can clear their storage to reset it; a real Pro tier needs accounts on a server.

## How updates work

The GitHub job downloads fresh nflverse data (built on Pro Football Reference), rebuilds `index.html`, and commits it. Cloudflare/Netlify sees the commit and redeploys. You don't touch anything.

Safety check: the build compares Pro Football Reference career totals against game logs. If more than 10% of active players disagree, it stops and keeps the old site up instead of publishing bad stats. You'll get a failed-run email from GitHub if that happens.

## Logos

Team logos come from the `nfl-team-logos` npm package. To override one (the Titans' 2026 logo isn't in the package yet), save the official file as `logos/TEN.svg` or `logos/TEN.png` and commit it. Files in `logos/` always win.

## Headshots

On your own site, player headshots load from ESPN's servers. That's fine for a personal project, but ESPN's photos aren't licensed for public use: before you grow this or add ads, switch to licensed or free (Wikimedia Commons) photos.

## Run it yourself

```
npm install
pip install -r requirements.txt
SITE_URL=https://playclocked.com npm run build
```
