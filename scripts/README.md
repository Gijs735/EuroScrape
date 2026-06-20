# Eurostar Azure Function

Python 3.13 Azure Functions app that refreshes `eurostar_prices.json` and uploads it to Blob Storage.

`function_app.py` is also the local CLI script, so the Eurostar fetch logic lives in one place.

## Functions

- `refresh_eurostar_prices_timer`: timer trigger, default schedule `0 45 9 * * *`.
- `refresh_eurostar_prices_http`: manual trigger at `/api/refresh-eurostar-prices?code=<function-key>`.

The HTTP trigger returns JSON:

```json
{
  "ok": true,
  "journeys_fetched": 584,
  "last_updated": "2026-06-20T13:37:16.426030Z",
  "container": "$web",
  "blob_name": "eurostar_prices.json",
  "bytes_written": 163154
}
```

On failure it returns status `500` with:

```json
{
  "ok": false,
  "error": "Error message"
}
```

## Local CLI

Run the same script locally with Python 3.13:

```bash
python3.13 scripts/function_app.py --output eurostar_prices.json
```

For a small test window:

```bash
python3.13 scripts/function_app.py \
  --start-date 2026-07-03 \
  --end-date 2026-07-05 \
  --output /tmp/eurostar-test.json \
  --sleep 0
```

## App Settings

- `AzureWebJobsStorage`: storage account connection string. Used by the function host and, by default, by the uploader.
- `EUROSTAR_STORAGE_CONNECTION_SETTING`: optional name of a different app setting containing the upload storage connection string. Defaults to `AzureWebJobsStorage`.
- `EUROSTAR_STORAGE_CONTAINER`: defaults to `$web`, the static website container.
- `EUROSTAR_STORAGE_BLOB_NAME`: defaults to `eurostar_prices.json`.
- `WEBSITE_TIME_ZONE`: set to `Romance Standard Time` for Brussels time.
- `EUROSTAR_TIMER_SCHEDULE`: defaults to `0 45 9 * * *`.
- `EUROSTAR_DAYS_AHEAD`: defaults to `365`.
- `EUROSTAR_FETCH_SLEEP_SECONDS`: defaults to `0.25`.
- `EUROSTAR_FETCH_TIMEOUT_SECONDS`: defaults to `30`.

Azure timer schedules use NCRONTAB format: `second minute hour day month day-of-week`. The default is 9:45 in the Function App's configured timezone. If no timezone is configured, Azure runs timers in UTC, so set `WEBSITE_TIME_ZONE=Romance Standard Time` to keep this at 9:45 Brussels time across daylight saving changes.
