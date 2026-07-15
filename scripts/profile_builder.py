from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as clock_time

from config import PROFILE_DEFINITIONS, ROUTE_BRUSSELS_TO_PARIS, ROUTE_PARIS_TO_BRUSSELS

BRUSSELS = {"name": "Brussels-South", "uic": "8814001"}
PARIS = {"name": "Paris-Nord", "uic": "8727100"}

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

ROUTE_DIRECTIONS = {
    ROUTE_BRUSSELS_TO_PARIS: (BRUSSELS, PARIS),
    ROUTE_PARIS_TO_BRUSSELS: (PARIS, BRUSSELS),
}


@dataclass(frozen=True)
class RouteConfig:
    key: str
    origin: dict[str, str]
    destination: dict[str, str]
    weekday: int
    depart_after: clock_time
    arrive_before: clock_time


@dataclass(frozen=True)
class FetchProfile:
    key: str
    schedule_name: str
    blob_name: str
    timer_schedule: str
    routes: tuple[RouteConfig, ...]


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


def route_key(origin: dict[str, str], destination: dict[str, str]) -> str:
    origin_key = origin["name"].lower().replace("-", "_")
    destination_key = destination["name"].lower().replace("-", "_")
    return f"{origin_key}_to_{destination_key}"


def route_from_definition(settings: dict[str, str], prefix: str) -> RouteConfig:
    route_name = settings[f"{prefix}_route"]
    try:
        origin, destination = ROUTE_DIRECTIONS[route_name]
    except KeyError as exc:
        valid_routes = ", ".join(ROUTE_DIRECTIONS)
        raise ValueError(f"Unknown route {route_name!r}; expected one of: {valid_routes}") from exc

    return RouteConfig(
        key=route_key(origin, destination),
        origin=origin,
        destination=destination,
        weekday=configured_weekday(settings[f"{prefix}_weekday"]),
        depart_after=configured_time(settings[f"{prefix}_depart_after"]),
        arrive_before=configured_time(settings[f"{prefix}_arrive_by"]),
    )


def profile_from_definition(key: str, settings: dict[str, str]) -> FetchProfile:
    return FetchProfile(
        key=key,
        schedule_name=settings["schedule_name"],
        blob_name=settings["blob_name"],
        timer_schedule=settings["timer_schedule"],
        routes=(
            route_from_definition(settings, "outbound"),
            route_from_definition(settings, "return"),
        ),
    )


PROFILES = {
    key: profile_from_definition(key, settings)
    for key, settings in PROFILE_DEFINITIONS.items()
}
