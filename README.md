# BTTS Live Score Tracker

A self-hosted football sweepstake tracker for a fixed group of players.

This project is designed for a 6-person **Both Teams To Score (BTTS)** game where each person is assigned one match. The app shows live scores, BTTS status, season points, group splits, and an admin panel for setting up each round.

## What it does

- tracks 6 assigned matches live
- shows whether **BTTS has landed** for each match
- supports **Top Bet**, **Bottom Bet**, and optional **Sixer Bet** modes
- includes an **admin page** for loading upcoming fixtures and assigning matches
- stores **season points**, stats, and game history in JSON files
- includes a public **leaderboard** page
- includes an **odds / predictions** page
- includes a **notification page** for Telegram / WhatsApp-related controls used by this build

## Current live versions on server

This repository is published with two branches:

- `main` → stable branch
- `dev` → development branch with newer UI / notification work

The server currently runs both side by side for testing.

## Stack

- Python 3
- Flask
- plain HTML / CSS / JavaScript
- Docker
- JSON file storage
- external football data APIs consumed by the backend

## Main features

### Public tracker
- displays one card per player
- live match scores and status
- BTTS hit / miss highlighting
- red card display
- group sections for Top / Bottom / Sixer
- mobile-friendly layout

### Admin area
- password-protected admin login
- search/load upcoming matches
- assign matches to players
- assign players to top / bottom / sixer groups
- edit site title and message banner
- save season points

### Leaderboard
- public standings page
- total season points
- secondary stats including BTTS hits, clinchers, donuts, costers and red-card related counts

### Data / history
- assignments
- group rotation / next groups
- fixtures and results cache
- season points and season stats
- game history

## Repository layout

Typical important files:

- `app.py` — Flask backend
- `templates/` — HTML templates for tracker, admin, leaderboard, odds, notify pages
- `static/js/` — front-end logic
- `static/css/style.css` — main styling
- `Dockerfile` — container build
- `requirements.txt` — Python dependencies
- `assignments.json` — current player → match assignments
- `groups.json` / `next_groups.json` — group allocations
- `results.json`, `fixtures.json` — match/result data
- `season_points.json`, `season_stats.json`, `game_history.json` — season state

## Running locally

### 1. Clone
```bash
git clone https://github.com/Clem-H-Fandango1/btts-live-score-tracker.git
cd btts-live-score-tracker
```

### 2. Install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run directly
```bash
python3 app.py
```

Then open the app in your browser.

## Running with Docker

Build:
```bash
docker build -t btts-live-score-tracker .
```

Run:
```bash
docker run -d \
  --name btts-live-score-tracker \
  -p 8094:8094 \
  --restart unless-stopped \
  btts-live-score-tracker
```

Adjust the exposed port to match your deployment.

## Configuration

Important environment variables used by the app include:

- `SECRET_KEY` — Flask session secret
- `ADMIN_PASSWORD` — admin login password
- `ODDS_PASSWORD` — password for the odds page

Some notification settings are also saved through the UI into JSON-backed settings.

## Notes about persistence

This app currently stores operational data in local JSON files rather than a database.
That keeps it simple and portable, but means you should mount the working directory or bind the relevant files if you want persistent container data.

## Branches

### `main`
Stable branch intended for normal use.

### `dev`
Development branch containing UI/layout experiments, newer match-card layout changes, and newer notification / WhatsApp control work.

## Intended use case

This is not a generic fantasy football platform. It is a small, purpose-built tracker for a private BTTS sweepstake / side game.

If you want to adapt it for a different group size or different scoring rules, the code is straightforward enough to customise.

## Sharing / open source note

Before sharing more widely, you should:

- review any hard-coded defaults
- check passwords and tokens are not committed
- replace any private artwork/assets you do not want to publish
- consider documenting the external football API source more explicitly

## License

No explicit license has been added yet.
If you plan to share this publicly for reuse, add a license file first.
