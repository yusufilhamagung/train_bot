from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from .config import load_settings
from .scheduler import run_search_once, watch_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="train_ticket_bot command-line interface")
    parser.add_argument("--routes-file", type=Path, default=None, help="Optional JSON file listing routes")
    parser.add_argument("--log-level", default="INFO", help="Logging level (INFO, DEBUG, ...)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_once_parser = subparsers.add_parser("run-once", help="Run a single search cycle")
    run_once_parser.add_argument("--show-browser", action="store_true", help="Show the browser window")
    watch_parser = subparsers.add_parser("watch", help="Continuously poll for tickets")
    watch_parser.add_argument("--show-browser", action="store_true", help="Show the browser window")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    settings = load_settings(routes_file=args.routes_file)
    headless = not getattr(args, "show_browser", False)

    if args.command == "run-once":
        asyncio.run(run_search_once(settings, headless=headless))
    elif args.command == "watch":
        asyncio.run(watch_loop(settings, headless=headless))
    else:  # pragma: no cover - argparse enforces valid commands
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
