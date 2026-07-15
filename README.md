# EuroScrape

Static dashboard for Eurostar weekend return trips.

## Criteria

- Gijs: Brussels-South -> Paris-Nord on Fridays, Paris-Nord -> Brussels-South on Sundays.
- Wenjie: Paris-Nord -> Brussels-South on Fridays, Brussels-South -> Paris-Nord on Sundays.
- Outbound: depart after 13:00, arrive by 17:45.
- Return: depart after 18:30, arrive by 22:30.
- Fetches the cheapest fare for 1 adult.

## Update data for local use

`python3.13 scripts/function_app.py`

The script asks which profile to fetch. Use `--profile gijs` or `--profile wenjie` to skip the prompt. This writes the profile JSON in the website root.

Edit profiles, routes, times, JSON filenames, and schedules in `scripts/config.py`.

The same script also runs as the Azure Function app. Gijs keeps `/api/refresh-eurostar-prices`; Wenjie uses `/api/refresh-wenjie-eurostar-prices`.
