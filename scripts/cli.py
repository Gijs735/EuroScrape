from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

from eurostar_api import CURRENCY
from fetcher import fetch_prices
from profile_builder import PROFILES, FetchProfile
from config import DEFAULT_DAYS_AHEAD, DEFAULT_SLEEP_SECONDS, DEFAULT_TIMEOUT_SECONDS


def profile_names() -> list[str]:
    return sorted(PROFILES)


def profile_choices() -> str:
    return ", ".join(profile_names())


def choose_profile_interactively() -> FetchProfile:
    print("Which profile should be fetched?", file=sys.stderr)
    for index, name in enumerate(profile_names(), start=1):
        profile = PROFILES[name]
        print(f"{index}. {name} ({profile.blob_name})", file=sys.stderr)

    while True:
        try:
            choice = input("Profile: ").strip().lower()
        except EOFError as exc:
            raise SystemExit(f"Please pass --profile with one of: {profile_choices()}") from exc

        if choice in PROFILES:
            return PROFILES[choice]
        if choice.isdigit():
            index = int(choice)
            names = profile_names()
            if 1 <= index <= len(names):
                return PROFILES[names[index - 1]]
        print(f"Choose one of: {profile_choices()}", file=sys.stderr)


def parse_cli_args() -> argparse.Namespace:
    today = date.today()
    parser = argparse.ArgumentParser(
        description="Fetch Eurostar Brussels <-> Paris fares for a configured profile."
    )
    parser.add_argument(
        "--profile",
        choices=profile_names(),
        help="Profile to fetch. If omitted, the script asks which profile to use.",
    )
    parser.add_argument(
        "--start-date",
        default=today.isoformat(),
        help="First date to consider, YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--end-date",
        default=(today + timedelta(days=DEFAULT_DAYS_AHEAD)).isoformat(),
        help=f"Last date to consider, YYYY-MM-DD. Defaults to {DEFAULT_DAYS_AHEAD} days from today.",
    )
    parser.add_argument(
        "--output",
        help="JSON output path. Defaults to the selected profile's JSON filename.",
    )
    parser.add_argument(
        "--currency",
        default=CURRENCY,
        help=f"Currency code sent to Eurostar. Defaults to {CURRENCY}.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help=f"Seconds to pause between search requests. Defaults to {DEFAULT_SLEEP_SECONDS}.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"HTTP timeout in seconds. Defaults to {DEFAULT_TIMEOUT_SECONDS}.",
    )
    return parser.parse_args()


def parse_cli_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid date {value!r}; expected YYYY-MM-DD") from exc


def main() -> int:
    args = parse_cli_args()
    profile = PROFILES[args.profile] if args.profile else choose_profile_interactively()
    output = fetch_prices(
        profile=profile,
        start=parse_cli_date(args.start_date),
        end=parse_cli_date(args.end_date),
        currency=args.currency,
        sleep_seconds=args.sleep,
        timeout=args.timeout,
    )
    output_path = args.output or profile.blob_name
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Wrote {output_path} with {len(output['trains'])} journeys.", file=sys.stderr)
    return 0
