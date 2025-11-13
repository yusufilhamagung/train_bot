# train_ticket_bot

A personal-friendly CLI bot that searches for train tickets on a configurable website, applies filters, notifies you when matches are found, and can optionally step through a guarded auto-book flow. The tool is built with Playwright, asyncio, and modular components so you can adapt it to any railway or OTA site.

## Features
- Loads preferences from `.env` plus optional JSON route/passenger files.
- Launches Playwright in headless mode by default with clean browser lifecycle helpers.
- Periodically searches for tickets, filters results (origin, destination, date, time window, price, seats), and prints a compact table.
- Optional Telegram and email notifications plus a safe auto-book stub guarded by `AUTO_BOOK_ENABLED`.
- Clear TODO markers for selectors and site-specific elements so you can wire it to the target site without scraping aggressively.

## Quickstart
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # or source .venv/bin/activate on Unix
   pip install -r requirements.txt
   python -m playwright install
   ```
2. Copy the sample environment file and adjust values:
   ```bash
   cp .env.example .env
   ```
3. Update every selector constant in `src/train_ticket_bot/scraper/search.py` (and booking modules if you enable them) to match your target website. They are intentionally left as TODO markers.

## Configuration
- `.env` stores the primary route and credentials. See `.env.example` for all keys.
- `ROUTES_FILE` can point to a JSON file (see `src/train_ticket_bot/config/routes_example.json`) describing multiple routes to poll sequentially.
- `PASSENGERS_FILE` (optional) can list passenger profiles for the booking stub.
- Never hard-code credentials; use environment variables only.

## Running the bot
All Python modules live in `src/`, so either install the package or add `src` to `PYTHONPATH` while running commands from the project root:

### Single search
```powershell
$env:PYTHONPATH="src"
python -m train_ticket_bot.cli run-once
```
### Continuous watch mode
```powershell
$env:PYTHONPATH="src"
python -m train_ticket_bot.cli watch
```
Add `--show-browser` to either command if you want to see the UI.

## Notifications & booking
- Telegram: set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- Email: fill SMTP-related variables; the implementation is a stub awaiting your provider details.
- Auto-booking: set `AUTO_BOOK_ENABLED=true` only if you understand the flow. The code logs every step and stops before payments as an extra safeguard.

## Respect the target site
This project is designed for low-frequency personal automation. Keep polling intervals reasonable, obey robots/ToS, and do not attempt to bypass captchas or rate limits.
