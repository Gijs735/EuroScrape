# EuroScrape

Static dashboard for Brussels-South to Paris-Nord weekend return trips.

## Criteria

- Brussels-South -> Paris-Nord: Fridays, depart after 13:00, arrive before 17:45.
- Paris-Nord -> Brussels-South: Sundays, depart after 18:30, arrive before 22:30.
- Fetches the cheapest fare for 1 adult.

## Update data for local use

`python3.13 scripts/function_app.py --output eurostar_prices.json`

This writes `eurostar_prices.json` in the website root.

The same script also runs as the Azure Function app, with timer and manual HTTP triggers for server deployment on Azure.