ROUTE_BRUSSELS_TO_PARIS = "brussels_to_paris"
ROUTE_PARIS_TO_BRUSSELS = "paris_to_brussels"

# Profile settings. Route values must be ROUTE_BRUSSELS_TO_PARIS or ROUTE_PARIS_TO_BRUSSELS.
# To add another profile, add it below, create a PROFILE constant in function_app.py, and
# then copy one timer block and one HTTP block in function_app.py.
PROFILE_DEFINITIONS = {
    "gijs": {
        "schedule_name": "Gijs's schedule",
        "blob_name": "eurostar_prices_gijs.json",
        "timer_schedule": "0 45 9 * * *",
        "http_route": "refresh-eurostar-prices",
        "outbound_route": ROUTE_BRUSSELS_TO_PARIS,
        "outbound_weekday": "friday",
        "outbound_depart_after": "13:00",
        "outbound_arrive_by": "17:45",
        "return_route": ROUTE_PARIS_TO_BRUSSELS,
        "return_weekday": "sunday",
        "return_depart_after": "18:30",
        "return_arrive_by": "22:30",
    },
    "wenjie": {
        "schedule_name": "Wenjie's schedule",
        "blob_name": "eurostar_prices_wenjie.json",
        "timer_schedule": "0 15 10 * * *",
        "http_route": "refresh-wenjie-eurostar-prices",
        "outbound_route": ROUTE_PARIS_TO_BRUSSELS,
        "outbound_weekday": "friday",
        "outbound_depart_after": "13:00",
        "outbound_arrive_by": "17:45",
        "return_route": ROUTE_BRUSSELS_TO_PARIS,
        "return_weekday": "sunday",
        "return_depart_after": "18:30",
        "return_arrive_by": "22:30",
    },
}

STORAGE_ACCOUNT_NAME = "eurostartrip"
STORAGE_CONTAINER = "$web"

DEFAULT_DAYS_AHEAD = 365
DEFAULT_SLEEP_SECONDS = 0.25
DEFAULT_TIMEOUT_SECONDS = 30.0
