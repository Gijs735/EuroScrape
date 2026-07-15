#!/usr/bin/env python3
"""Azure Function entrypoint and local CLI passthrough for Eurostar price refreshes."""

from __future__ import annotations

import json
import logging

from cli import main
from profile_builder import PROFILES, FetchProfile
from storage import refresh_prices

try:
    import azure.functions as func
except ModuleNotFoundError:
    func = None


app = func.FunctionApp() if func is not None else None


if app is not None:
    def refresh_profile_timer(profile: FetchProfile, timer: func.TimerRequest) -> None:
        if timer.past_due:
            logging.warning("Eurostar price refresh timer for %s is past due.", profile.key)
        result = refresh_prices(profile)
        logging.info(
            "Eurostar price refresh for %s completed: %s journeys written to %s/%s.",
            profile.key,
            result["journeys_fetched"],
            result["container"],
            result["blob_name"],
        )

    def refresh_profile_http(profile: FetchProfile) -> func.HttpResponse:
        try:
            result = refresh_prices(profile)
        except Exception as exc:
            logging.exception("Eurostar price refresh for %s failed.", profile.key)
            return func.HttpResponse(
                json.dumps(
                    {"ok": False, "profile": profile.key, "error": f"{type(exc).__name__}: {exc}"},
                    ensure_ascii=False,
                ),
                status_code=500,
                mimetype="application/json",
            )

        return func.HttpResponse(
            json.dumps({"ok": True, **result}, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
        )

    @app.timer_trigger(
        schedule=PROFILES["gijs"].timer_schedule,
        arg_name="timer",
        run_on_startup=False,
        use_monitor=True,
    )
    def refresh_gijs_eurostar_prices_timer(timer: func.TimerRequest) -> None:
        refresh_profile_timer(PROFILES["gijs"], timer)

    @app.timer_trigger(
        schedule=PROFILES["wenjie"].timer_schedule,
        arg_name="timer",
        run_on_startup=False,
        use_monitor=True,
    )
    def refresh_wenjie_eurostar_prices_timer(timer: func.TimerRequest) -> None:
        refresh_profile_timer(PROFILES["wenjie"], timer)

    @app.route(
        route="refresh-eurostar-prices",
        auth_level=func.AuthLevel.FUNCTION,
        methods=["GET", "POST"],
    )
    def refresh_gijs_eurostar_prices_http(req: func.HttpRequest) -> func.HttpResponse:
        return refresh_profile_http(PROFILES["gijs"])

    @app.route(
        route="refresh-wenjie-eurostar-prices",
        auth_level=func.AuthLevel.FUNCTION,
        methods=["GET", "POST"],
    )
    def refresh_wenjie_eurostar_prices_http(req: func.HttpRequest) -> func.HttpResponse:
        return refresh_profile_http(PROFILES["wenjie"])


if __name__ == "__main__":
    raise SystemExit(main())
