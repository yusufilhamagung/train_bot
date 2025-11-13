# Train Ticket Bot

```
 _____________________________________________________________________________
| Train Ticket Bot - command-line conductor for personal ticket hunting      |
|____________________________________________________________________________|
     o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o
```

Your friendly automation helper that refreshes train availability, filters the results you care about, and pings you the very moment a matching seat appears. Built for Playwright + asyncio so it stays fast, headless, and easy to wire into any trusted site.

## Quick Look
| Item | Details |
| --- | --- |
| Runtime | Python 3.11+, asyncio-native workflow |
| Browser | Playwright (Chromium) with safe headless defaults |
| Modes | `run-once` single poll or `watch` continuous loop |
| Alerts | Telegram bot, SMTP email stub, console dashboard |
| Booking | Guarded assisted flow behind `AUTO_BOOK_ENABLED` |
| Config | `.env` core settings + JSON manifests for routes & passengers |

## Feature Highlights
- Reusable scraper pipeline (`src/scraper`) with selectors isolated in one place, ready to be mapped to your target site.
- Lightweight scheduler (`src/scheduler/job.py`) that spaces out polls and protects the server from accidental hammering.
- Modular notifiers (Telegram + email) so you can opt-in per channel.
- Booking helpers stubbed in `src/booking/` for those who want to extend past search once selectors are stable.
- Clear logging format that keeps time stamps, log level, and module names aligned for easy tracing.

## Project Map
```
src/
|- cli.py                # argparse-powered entry point (run-once / watch)
|- booking/              # login + booking helpers (disabled by default)
|- config/               # .env loader, JSON parsing, typed settings
|- models/               # dataclasses representing tickets and passengers
|- notifier/             # Telegram + email notification clients
|- scheduler/            # search loop orchestration
`- scraper/              # browser automation + search parsing
```

Keep an eye on `src/scraper/search.py` and `src/booking/*.py`; the selectors in those files are intentionally left as TODO markers so you can bind them to the real site you are targeting.

## Getting Started
1. **Create a virtual environment and install dependencies.**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m playwright install
   ```
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python -m playwright install
   ```
2. **Copy and fill your environment file.**
   ```bash
   cp .env.example .env
   ```
   Update all placeholders (stations, credentials, tokens). If you maintain different profiles, create separate `.env.<name>` files and switch via `set -a; source`.
3. **Wire selectors to your target website.**
   - Search form, result rows, and CTA buttons live in `src/scraper/search.py`.
   - Booking-specific form fields sit under `src/booking/`.
   - Keep the delays and waits polite; the defaults mimic human pacing.
4. **Run the CLI from the project root.** The package follows a `src/` layout, so just execute `python -m src.cli ...` (no extra installs required for local use).

## Configuration Cheatsheet
| Category | Key(s) | Purpose | Notes |
| --- | --- | --- | --- |
| Core route | `ORIGIN_STATION`, `DESTINATION_STATION`, `DEPARTURE_DATE` | Required search coordinates | Dates use `YYYY-MM-DD`. |
| Time window | `PREFERRED_DEPARTURE_TIME_START`, `PREFERRED_DEPARTURE_TIME_END` | Limit departures to a clock range | Leave empty to accept all departures. |
| Capacity & price | `PASSENGER_COUNT`, `MIN_SEATS_AVAILABLE`, `MAX_PRICE` | Enforce seat counts and budget | `MIN_SEATS_AVAILABLE` defaults to passenger count. |
| Polling | `POLLING_INTERVAL_MINUTES`, `HEADLESS`, `AUTO_BOOK_ENABLED` | Tune watch cadence and UI visibility | Booking should stay `false` until selectors are verified end-to-end. |
| Files | `ROUTES_FILE`, `PASSENGERS_FILE` | Point to optional JSON manifests | Use `src/config/routes_example.json` as a template. |
| Notifications | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `EMAIL_*` | Configure outbound alerts | Email implementation is a skeletal SMTP example - fill in provider details. |
| Credentials | `TICKET_SITE_USERNAME`, `TICKET_SITE_PASSWORD` | Used only when booking is enabled | Never commit these values; `.env` is git-ignored. |
| Misc | `BASE_URL`, `CURRENCY` | Override host or display currency | `BASE_URL` should match the site you legally control or have permission to automate. |

## CLI Recipes & Flags
All commands run from the repository root.

```powershell
# Single poll
python -m src.cli run-once --log-level DEBUG

# Continuous monitoring with UI visible
python -m src.cli watch --show-browser

# Watch a custom route playlist
python -m src.cli watch --routes-file data/routes.json
```

Helpful switches:
- `--routes-file`: override `ROUTES_FILE` for one-off runs.
- `--log-level`: promote to `DEBUG` when tuning selectors.
- `--show-browser`: flip Playwright into headed mode for visual debugging.

## Notifications & Booking Matrix
| Feature | Toggle / Requirement | What You Get |
| --- | --- | --- |
| Telegram pings | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Instant push when matching tickets drop. |
| Email stub | `EMAIL_*` (SMTP host, port, user, password, sender, recipient) | Basic transactional email, ready to swap for your provider. |
| Auto booking prototype | `AUTO_BOOK_ENABLED=true` plus passenger JSON | Carefully steps through login + booking helpers; stops short of payment for safety. |

### Telegram alert details
- The bot scrapes the route and travel date labels directly from the KAI page, so the header in Telegram always mirrors the UI (even if you tweak the search manually).
- Each train card is rendered in a tidy block that shows name/number, origin/destination, the departure label reported by the site, duration, class + subclass, price in Indonesian formatting, and seat/status info.
- The summary includes total/available/unavailable counts; long runs are auto-split into multiple messages so you never hit the 4096-character Telegram limit.
- Configure your credentials once via `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`, then optionally tune the message template by editing `src/notifier/telegram.py`.

## Respect the Rails
- Keep `POLLING_INTERVAL_MINUTES` humane; abusing a public ticketing site may violate ToS.
- Do not bypass captchas, throttles, or payment walls.
- Run the bot only for personal use or where you have explicit approval.
- Always monitor the terminal during booking flows - human oversight remains the final safeguard.

## Roadmap Ideas
- Add richer diffing in notifications (e.g., show what changed since last ping).
- Introduce persistent storage for search history and false positives.
- Wire in additional channels (WhatsApp Web, Slack) via the notifier layer.
- Expand tests (`test_telegram.py` is a starting point) to cover schedulers and search parsing.

Happy hacking, and may your preferred train never sell out again.
