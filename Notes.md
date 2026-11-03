# Notes

## Angle and audience
- Hook: the Silvertown Tunnel opened in April 2025, and the main air quality verdict ("NO₂ down 17%") came from TfL, who built it. The data to check it is public.
- Question: how much worse is NO₂ right beside a main road than at a background site, and when?
- For: people who walk, cycle or wait for buses on central London's main roads.
- Answer: Marylebone Road averaged 3.6× the background (47.6 against 13.3 µg/m³), worst at 17:00, and the gap is a third bigger on weekdays.
- Picked after exploring, because the API's site list labels each site Kerbside or Background.

## Extract
- Help page → table of endpoints → call the ones that need nothing (Groups, Species) → GroupName, SpeciesCode → MonitoringSites gives SiteCode → Data/SiteSpecies gives hourly readings.

## Collect history
- Each run fetches the last 7 days, so runs overlap.
- The primary key (site, species, hour) means each hour is stored once: a new hour is inserted, a known hour is updated.
- A value that changes goes into `changes` first. Every run is logged in `runs`.
- Run twice: the second run says "0 new".

## Shape
- One table, `readings`: one row per site, species and hour. Types are TIMESTAMP and DOUBLE.
- `Clean` removes the @ from names and turns "" into NULL. Gaps stay NULL. Units are µg/m³, times are GMT.

## Use
- SQL joins `readings` to `sites` on SiteCode, and averages by site type and hour of day, which gives the chart.

## Extend
- The Silvertown check: tunnel-approach sites against background sites, before and after April 2025.
- More site pairs and pollutants, a schedule, Pydantic models, and one shared module for the rules.

## Problems I anticipated
- A bad request returns 200 with empty values, so I check the pair is listed and the reply has values.
- Values arrive late or change, so the pipeline updates in place and records the old value in `changes`.
- Re-runs could duplicate, so the primary key and ON CONFLICT stop that.
- Values older than 7 days could still change. That's a stated assumption, and the first next step.

## API mess (detail in Mess.md)
- Field names start with @, missing is "", everything is text, a one-item list comes back as a dict, each endpoint wraps its records differently, and times are GMT all year.

## Where AI helped
- Tutor and reviewer: it explained syntax, probed the API, and wrote more code near the deadline, plus the README prose. The decisions are mine.
