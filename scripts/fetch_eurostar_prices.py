#!/usr/bin/env python3
"""Fetch Eurostar fare data for fixed Brussels <-> Paris travel windows.

This script uses the same private JSON/GraphQL endpoint currently used by the
Eurostar web search app. Private endpoints can change without notice, so keep
the request shape isolated here and fail with date-level errors when possible.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as clock_time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GATEWAY_URL = "https://site-api.eurostar.com/gateway"
SITE_API_KEY = "NGktEpCX5R2jYamA9WejQ5b5ryxxUhq51pg7iNXm"
MARKET = "be"
CURRENCY = "EUR"

BRUSSELS = {
    "name": "Brussels-South",
    "uic": "8814001",
}
PARIS = {
    "name": "Paris-Nord",
    "uic": "8727100",
}

EUROSTAR_SERVICE_CODES = {"ES", "ER", "TH"}
STANDARD_CLASS_MARKERS = ("STANDARD", "STD")

# Travel preferences. Change these values when your preferred days or windows change.
BRUSSELS_TO_PARIS_WEEKDAY = "friday"
BRUSSELS_TO_PARIS_DEPART_AFTER = "13:00"
BRUSSELS_TO_PARIS_ARRIVE_BEFORE = "17:45"
BRUSSELS_TO_PARIS_ARRIVE_INCLUSIVE = False

PARIS_TO_BRUSSELS_WEEKDAY = "sunday"
PARIS_TO_BRUSSELS_DEPART_AFTER = "18:30"
PARIS_TO_BRUSSELS_ARRIVE_BEFORE = "22:30"
PARIS_TO_BRUSSELS_ARRIVE_INCLUSIVE = True

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

NEW_BOOKING_SEARCH_QUERY = """
query NewBookingSearch(
  $origin: String!
  $destination: String!
  $outbound: String!
  $inbound: String
  $productFamilies: [String] = ["PUB"]
  $contractCode: String = "EIL_ALL"
  $adult: Int
  $child: Int
  $infant: Int
  $youth: Int
  $senior: Int
  $adults16Plus: Int = 0
  $children4Only: Int = 0
  $children5To11: Int = 0
  $adultsWheelchair: Int = 0
  $childrenWheelchair: Int = 0
  $guideDogs: Int = 0
  $wheelchairCompanions: Int = 0
  $nonWheelchairCompanions: Int = 0
  $filteredClassesOfService: [ClassOfServiceEnum]
  $filteredClassesOfAccommodation: [ClassEnum]
  $currency: Currency!
  $isAftersales: Boolean = false
  $multipleFlexibility: Boolean = true
  $subscriptionCode: TravelPassTemplateCode
  $showAllSummatedFares: Boolean = false
  $seniorsAges: [Int!]
  $childAges: [Int!]
  $youthAges: [Int!]
  $prioritiseShortHaulODTrains: Boolean = false
  $hideExternalCarrierTrains: Boolean = true
  $hideDirectExternalCarrierTrains: Boolean = true
  $maxTransfers: Int
) {
  journeySearch(
    outboundDate: $outbound
    inboundDate: $inbound
    origin: $origin
    destination: $destination
    adults: $adult
    seniors: $senior
    productFamilies: $productFamilies
    contractCode: $contractCode
    adults16Plus: $adults16Plus
    children: $child
    youths: $youth
    children4Only: $children4Only
    children5To11: $children5To11
    infants: $infant
    adultsWheelchair: $adultsWheelchair
    childrenWheelchair: $childrenWheelchair
    guideDogs: $guideDogs
    wheelchairCompanions: $wheelchairCompanions
    nonWheelchairCompanions: $nonWheelchairCompanions
    isAftersales: $isAftersales
    currency: $currency
    multipleFlexibility: $multipleFlexibility
    subscriptionCode: $subscriptionCode
    showAllSummatedFares: $showAllSummatedFares
    seniorsAges: $seniorsAges
    childAges: $childAges
    youthAges: $youthAges
    prioritiseShortHaulODTrains: $prioritiseShortHaulODTrains
    maxTransfers: $maxTransfers
  ) {
    outbound {
      ...searchBound
    }
  }
}

fragment searchBound on Offer {
  journeys(
    hideIndirectTrainsWhenDisruptedAndCancelled: false
    hideDepartedTrains: true
    hideExternalCarrierTrains: $hideExternalCarrierTrains
    hideDirectExternalCarrierTrains: $hideDirectExternalCarrierTrains
  ) {
    ...journey
  }
}

fragment journey on Journey {
  timing {
    date
    departureTime: departs
    arrivalTime: arrives
  }
  fares(
    filteredClassesOfService: $filteredClassesOfService
    filteredClassesOfAccommodation: $filteredClassesOfAccommodation
  ) {
    classOfService {
      name
      code
    }
    prices {
      displayPrice
      total
      bundlePrice
    }
    seats
    availabilityOfClassOfService
    legs {
      products {
        price
        passengerAgeGroup {
          name
        }
      }
      serviceName
      serviceType {
        code
        brandCode
      }
    }
  }
}
""".strip()


@dataclass(frozen=True)
class RouteConfig:
    key: str
    origin: dict[str, str]
    destination: dict[str, str]
    weekday: int
    depart_after: clock_time
    arrive_before: clock_time
    arrive_inclusive: bool


def configured_weekday(name: str) -> int:
    try:
        return WEEKDAYS[name.lower()]
    except KeyError as exc:
        valid = ", ".join(WEEKDAYS)
        raise ValueError(f"Unknown weekday {name!r}; expected one of: {valid}") from exc


def configured_time(value: str) -> clock_time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError(f"Invalid time {value!r}; expected HH:MM") from exc


ROUTES = (
    RouteConfig(
        key="brussels_to_paris",
        origin=BRUSSELS,
        destination=PARIS,
        weekday=configured_weekday(BRUSSELS_TO_PARIS_WEEKDAY),
        depart_after=configured_time(BRUSSELS_TO_PARIS_DEPART_AFTER),
        arrive_before=configured_time(BRUSSELS_TO_PARIS_ARRIVE_BEFORE),
        arrive_inclusive=BRUSSELS_TO_PARIS_ARRIVE_INCLUSIVE,
    ),
    RouteConfig(
        key="paris_to_brussels",
        origin=PARIS,
        destination=BRUSSELS,
        weekday=configured_weekday(PARIS_TO_BRUSSELS_WEEKDAY),
        depart_after=configured_time(PARIS_TO_BRUSSELS_DEPART_AFTER),
        arrive_before=configured_time(PARIS_TO_BRUSSELS_ARRIVE_BEFORE),
        arrive_inclusive=PARIS_TO_BRUSSELS_ARRIVE_INCLUSIVE,
    ),
)


class EurostarSearchError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    today = date.today()
    parser = argparse.ArgumentParser(
        description="Fetch Eurostar Brussels <-> Paris fares for the configured Friday/Sunday windows."
    )
    parser.add_argument(
        "--start-date",
        default=today.isoformat(),
        help="First date to consider, YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--end-date",
        default=(today + timedelta(days=365)).isoformat(),
        help="Last date to consider, YYYY-MM-DD. Defaults to one year from today.",
    )
    parser.add_argument(
        "--output",
        default="eurostar_prices.json",
        help="JSON output path. Defaults to eurostar_prices.json.",
    )
    parser.add_argument(
        "--currency",
        default=CURRENCY,
        help="Currency code sent to Eurostar. Defaults to EUR.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Seconds to pause between search requests. Defaults to 0.25.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds. Defaults to 30.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on the first failed date instead of recording per-date errors.",
    )
    return parser.parse_args()


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date {value!r}; expected YYYY-MM-DD") from exc


def parse_hhmm(value: str | None) -> clock_time | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise EurostarSearchError(f"Unexpected time value from Eurostar: {value!r}") from exc


def iter_matching_dates(start: date, end: date, weekday: int) -> list[date]:
    days_until_weekday = (weekday - start.weekday()) % 7
    current = start + timedelta(days=days_until_weekday)
    dates: list[date] = []
    while current <= end:
        dates.append(current)
        current += timedelta(days=7)
    return dates


def eurostar_variables(route: RouteConfig, travel_date: date, currency: str) -> dict[str, Any]:
    return {
        "origin": route.origin["uic"],
        "destination": route.destination["uic"],
        "currency": currency,
        "outbound": travel_date.isoformat(),
        "inbound": None,
        "adult": 1,
        "child": 0,
        "senior": 0,
        "infant": 0,
        "youth": 0,
        "adults16Plus": 0,
        "children4Only": 0,
        "children5To11": 0,
        "adultsWheelchair": 0,
        "childrenWheelchair": 0,
        "guideDogs": 0,
        "wheelchairCompanions": 0,
        "nonWheelchairCompanions": 0,
        "seniorsAges": [],
        "childAges": [],
        "youthAges": [],
        "productFamilies": ["PUB"],
        "contractCode": "EIL_ALL",
        "maxTransfers": 0,
        "multipleFlexibility": True,
        "showAllSummatedFares": False,
        "isAftersales": False,
        "subscriptionCode": None,
        "prioritiseShortHaulODTrains": True,
        "hideExternalCarrierTrains": True,
        "hideDirectExternalCarrierTrains": True,
    }


def search_eurostar(route: RouteConfig, travel_date: date, currency: str, timeout: float) -> dict[str, Any]:
    body = {
        "operationName": "NewBookingSearch",
        "query": NEW_BOOKING_SEARCH_QUERY,
        "variables": eurostar_variables(route, travel_date, currency),
    }
    request = Request(
        GATEWAY_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Accept-Language": "en-BE,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": "https://www.eurostar.com",
            "Referer": "https://www.eurostar.com/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "cid": f"SRCH-{uuid.uuid4()}",
            "x-api-key": SITE_API_KEY,
            "x-market-code": MARKET,
            "x-platform": "web",
            "x-source-url": "search-app/",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise EurostarSearchError(f"HTTP {exc.code}: {body_text[:500]}") from exc
    except URLError as exc:
        raise EurostarSearchError(f"Network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise EurostarSearchError(f"Eurostar returned invalid JSON: {exc}") from exc

    if payload.get("errors"):
        raise EurostarSearchError(json.dumps(payload["errors"], ensure_ascii=False)[:1000])

    return payload


def as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def money_amount(fare: dict[str, Any]) -> Decimal | None:
    prices = fare.get("prices") or {}
    for key in ("displayPrice", "total", "bundlePrice"):
        amount = as_decimal(prices.get(key))
        if amount is not None:
            return amount
    products = fare.get("legs", [{}])[0].get("products") or []
    product_prices = [as_decimal(product.get("price")) for product in products]
    valid_prices = [price for price in product_prices if price is not None]
    if valid_prices:
        return sum(valid_prices, Decimal("0"))
    return None


def is_standard_fare(fare: dict[str, Any]) -> bool:
    class_of_service = fare.get("classOfService") or {}
    haystack = " ".join(
        str(part or "").upper()
        for part in (class_of_service.get("code"), class_of_service.get("name"))
    )
    return any(marker in haystack for marker in STANDARD_CLASS_MARKERS)


def available_fare(fare: dict[str, Any]) -> bool:
    availability = fare.get("availabilityOfClassOfService")
    seats = fare.get("seats")
    if isinstance(availability, (int, float)) and availability <= 0:
        return False
    if isinstance(seats, (int, float)) and seats <= 0:
        return False
    return True


def fare_summary(fare: dict[str, Any], amount: Decimal, currency: str) -> dict[str, Any]:
    class_of_service = fare.get("classOfService") or {}
    return {
        "amount": decimal_to_json(amount),
        "currency": currency,
        "class_code": class_of_service.get("code"),
        "class_name": class_of_service.get("name"),
    }


def decimal_to_json(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def choose_cheapest_relevant_fare(
    fares: list[dict[str, Any]], currency: str
) -> dict[str, Any] | None:
    candidates = []
    for fare in fares:
        if not available_fare(fare):
            continue
        amount = money_amount(fare)
        if amount is None:
            continue
        candidates.append((amount, fare))

    if not candidates:
        return None

    standard_candidates = [(amount, fare) for amount, fare in candidates if is_standard_fare(fare)]
    standard_choice = min(standard_candidates, key=lambda item: item[0], default=None)
    absolute_choice = min(candidates, key=lambda item: item[0])

    if standard_choice is None or absolute_choice[0] < standard_choice[0]:
        amount, fare = absolute_choice
    else:
        amount, fare = standard_choice

    return fare_summary(fare, amount, currency)


def journey_times(journey: dict[str, Any]) -> tuple[clock_time | None, clock_time | None]:
    timing = journey.get("timing") or {}
    return parse_hhmm(timing.get("departureTime")), parse_hhmm(timing.get("arrivalTime"))


def matches_time_window(journey: dict[str, Any], route: RouteConfig) -> bool:
    departure, arrival = journey_times(journey)
    if departure is None or arrival is None:
        return False
    if departure <= route.depart_after:
        return False
    if route.arrive_inclusive:
        return arrival <= route.arrive_before
    return arrival < route.arrive_before


def is_eurostar_journey(journey: dict[str, Any]) -> bool:
    legs = []
    for fare in journey.get("fares") or []:
        legs.extend(fare.get("legs") or [])
    if not legs:
        return True
    for leg in legs:
        service_type = leg.get("serviceType") or {}
        service_code = str(service_type.get("code") or "").upper()
        service_brand = str(service_type.get("brandCode") or "").upper()
        service_name = str(leg.get("serviceName") or "").upper()
        if (
            service_code not in EUROSTAR_SERVICE_CODES
            and "EUROSTAR" not in service_brand
            and "EUROSTAR" not in service_name
            and "THALYS" not in service_name
        ):
            return False
    return True


def summarize_journey(journey: dict[str, Any], route: RouteConfig, currency: str) -> dict[str, Any] | None:
    chosen_fare = choose_cheapest_relevant_fare(journey.get("fares") or [], currency)
    if chosen_fare is None:
        return None

    timing = journey.get("timing") or {}
    return {
        "date": timing.get("date"),
        "departure_station": route.origin["name"],
        "arrival_station": route.destination["name"],
        "departure_time": timing.get("departureTime"),
        "arrival_time": timing.get("arrivalTime"),
        "price": chosen_fare["amount"],
        "currency": chosen_fare["currency"],
        "eurostar_class": chosen_fare["class_name"] or chosen_fare["class_code"],
    }


def extract_trains(payload: dict[str, Any], route: RouteConfig, currency: str) -> list[dict[str, Any]]:
    bound = (((payload.get("data") or {}).get("journeySearch") or {}).get("outbound")) or {}
    trains = []
    for journey in bound.get("journeys") or []:
        if not matches_time_window(journey, route):
            continue
        if not is_eurostar_journey(journey):
            continue
        summary = summarize_journey(journey, route, currency)
        if summary is not None:
            trains.append(summary)
    return sorted(trains, key=lambda item: (item.get("date") or "", item.get("departure_time") or ""))


def fetch_route(
    route: RouteConfig,
    dates: list[date],
    currency: str,
    timeout: float,
    sleep_seconds: float,
    fail_fast: bool,
) -> list[dict[str, Any]]:
    results = []
    for index, travel_date in enumerate(dates, start=1):
        if index > 1 and sleep_seconds > 0:
            time.sleep(sleep_seconds)
        trains: list[dict[str, Any]] = []
        had_error = False
        try:
            payload = search_eurostar(route, travel_date, currency, timeout)
            trains = extract_trains(payload, route, currency)
        except EurostarSearchError as exc:
            if fail_fast:
                raise
            had_error = True
            print(f"{route.key} {travel_date.isoformat()}: {exc}", file=sys.stderr)
        results.extend(trains)
        print(
            f"{route.key} {travel_date.isoformat()}: {len(trains)} matching train(s)"
            + (" [error]" if had_error else ""),
            file=sys.stderr,
        )
    return results


def build_output(args: argparse.Namespace) -> dict[str, Any]:
    start = parse_date(args.start_date)
    end = parse_date(args.end_date)
    if end < start:
        raise SystemExit("--end-date must be on or after --start-date")

    route_dates = {route.key: iter_matching_dates(start, end, route.weekday) for route in ROUTES}
    output = {
        "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trains": [],
    }

    for route in ROUTES:
        output["trains"].extend(
            fetch_route(
                route=route,
                dates=route_dates[route.key],
                currency=args.currency,
                timeout=args.timeout,
                sleep_seconds=args.sleep,
                fail_fast=args.fail_fast,
            )
        )

    return output


def main() -> int:
    args = parse_args()
    output = build_output(args)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
