from __future__ import annotations

import json
import time
import uuid
from datetime import date, datetime, time as clock_time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from eurostar_api import (
    CURRENCY,
    EUROSTAR_SERVICE_CODES,
    GATEWAY_URL,
    MARKET,
    SITE_API_KEY,
    STANDARD_CLASS_MARKERS,
)
from eurostar_query import NEW_BOOKING_SEARCH_QUERY
from profile_builder import FetchProfile, RouteConfig


class EurostarFetchError(RuntimeError):
    pass


def iter_matching_dates(start: date, end: date, weekday: int) -> list[date]:
    current = start + timedelta(days=(weekday - start.weekday()) % 7)
    dates = []
    while current <= end:
        dates.append(current)
        current += timedelta(days=7)
    return dates


def parse_hhmm(value: str | None) -> clock_time | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise EurostarFetchError(f"Unexpected time value from Eurostar: {value!r}") from exc


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
    request = Request(
        GATEWAY_URL,
        data=json.dumps(
            {
                "operationName": "NewBookingSearch",
                "query": NEW_BOOKING_SEARCH_QUERY,
                "variables": eurostar_variables(route, travel_date, currency),
            }
        ).encode("utf-8"),
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
        raise EurostarFetchError(f"HTTP {exc.code}: {body_text[:500]}") from exc
    except URLError as exc:
        raise EurostarFetchError(f"Network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise EurostarFetchError(f"Eurostar returned invalid JSON: {exc}") from exc

    if payload.get("errors"):
        raise EurostarFetchError(json.dumps(payload["errors"], ensure_ascii=False)[:1000])
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
    valid_prices = [
        price
        for price in (as_decimal(product.get("price")) for product in products)
        if price is not None
    ]
    return sum(valid_prices, Decimal("0")) if valid_prices else None


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
    return not (
        isinstance(availability, (int, float)) and availability <= 0
        or isinstance(seats, (int, float)) and seats <= 0
    )


def choose_cheapest_relevant_fare(fares: list[dict[str, Any]], currency: str) -> dict[str, Any] | None:
    candidates = [
        (amount, fare)
        for fare in fares
        if available_fare(fare)
        for amount in [money_amount(fare)]
        if amount is not None
    ]
    if not candidates:
        return None

    standard_choice = min(
        ((amount, fare) for amount, fare in candidates if is_standard_fare(fare)),
        key=lambda item: item[0],
        default=None,
    )
    absolute_choice = min(candidates, key=lambda item: item[0])
    amount, fare = (
        absolute_choice
        if standard_choice is None or absolute_choice[0] < standard_choice[0]
        else standard_choice
    )
    class_of_service = fare.get("classOfService") or {}
    return {
        "amount": float(amount),
        "currency": currency,
        "class_name": class_of_service.get("name"),
        "class_code": class_of_service.get("code"),
    }


def journey_times(journey: dict[str, Any]) -> tuple[clock_time | None, clock_time | None]:
    timing = journey.get("timing") or {}
    return parse_hhmm(timing.get("departureTime")), parse_hhmm(timing.get("arrivalTime"))


def matches_time_window(journey: dict[str, Any], route: RouteConfig) -> bool:
    departure, arrival = journey_times(journey)
    return departure is not None and arrival is not None and departure > route.depart_after and arrival <= route.arrive_before


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
    fare = choose_cheapest_relevant_fare(journey.get("fares") or [], currency)
    if fare is None:
        return None

    timing = journey.get("timing") or {}
    return {
        "date": timing.get("date"),
        "departure_station": route.origin["name"],
        "arrival_station": route.destination["name"],
        "departure_time": timing.get("departureTime"),
        "arrival_time": timing.get("arrivalTime"),
        "price": fare["amount"],
        "currency": fare["currency"],
        "eurostar_class": fare["class_name"] or fare["class_code"],
    }


def extract_trains(payload: dict[str, Any], route: RouteConfig, currency: str) -> list[dict[str, Any]]:
    bound = (((payload.get("data") or {}).get("journeySearch") or {}).get("outbound")) or {}
    trains = [
        summary
        for journey in bound.get("journeys") or []
        if matches_time_window(journey, route) and is_eurostar_journey(journey)
        for summary in [summarize_journey(journey, route, currency)]
        if summary is not None
    ]
    return sorted(trains, key=lambda item: (item.get("date") or "", item.get("departure_time") or ""))


def train_identity(train: dict[str, Any]) -> tuple[Any, ...]:
    return (
        train.get("date"),
        train.get("departure_station"),
        train.get("arrival_station"),
        train.get("departure_time"),
        train.get("arrival_time"),
    )


def train_choice_key(train: dict[str, Any]) -> tuple[Decimal, int]:
    price = as_decimal(train.get("price")) or Decimal("Infinity")
    class_name = str(train.get("eurostar_class") or "").upper()
    non_standard_rank = 0 if any(marker in class_name for marker in STANDARD_CLASS_MARKERS) else 1
    return price, non_standard_rank


def deduplicate_trains(trains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_train: dict[tuple[Any, ...], dict[str, Any]] = {}
    for train in trains:
        identity = train_identity(train)
        current = best_by_train.get(identity)
        if current is None or train_choice_key(train) < train_choice_key(current):
            best_by_train[identity] = train

    return sorted(
        best_by_train.values(),
        key=lambda item: (
            item.get("date") or "",
            item.get("departure_station") or "",
            item.get("departure_time") or "",
        ),
    )


def fetch_prices(
    *,
    profile: FetchProfile,
    start: date | None = None,
    end: date | None = None,
    days_ahead: int = 365,
    currency: str = CURRENCY,
    sleep_seconds: float = 0.25,
    timeout: float = 30.0,
) -> dict[str, Any]:
    start_date = start or date.today()
    end_date = end or start_date + timedelta(days=days_ahead)
    trains: list[dict[str, Any]] = []

    for route in profile.routes:
        for index, travel_date in enumerate(iter_matching_dates(start_date, end_date, route.weekday)):
            if index > 0 and sleep_seconds > 0:
                time.sleep(sleep_seconds)
            payload = search_eurostar(route, travel_date, currency, timeout)
            trains.extend(extract_trains(payload, route, currency))

    return {
        "schedule_name": profile.schedule_name,
        "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trains": deduplicate_trains(trains),
    }
