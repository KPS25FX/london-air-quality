# Design

## Stage 1: Survey

Source: the API help page (https://api.erg.ic.ac.uk/AirQuality/help), saved on 28 Oct as
`Archive/snapshots/endpoints.csv`. It lists 36 endpoints. The brief scopes exploration to **sites, pollutants and
readings**.

### 1.1 Endpoints in scope (9 of 36)

| Group | Endpoint | Needs | Returns |
|---|---|---|---|
| Sites | `Information/Groups` | nothing | the groups of sites (e.g. London) |
| Sites | `Information/MonitoringSites/GroupName={GroupName}` | GroupName | the sites in a group, each listed once |
| Sites + pollutants | `Information/MonitoringSiteSpecies/GroupName={GroupName}` | GroupName | the sites, with the pollutants each one measures (the only endpoint that links the two) |
| Pollutants | `Information/Species` | nothing | all pollutants (code, name, health effects) |
| Pollutants | `Information/Species/SpeciesCode={SpeciesCode}` | SpeciesCode | one pollutant (same as above, filtered) |
| Readings | `Data/SiteSpecies/SiteCode/SpeciesCode/StartDate/EndDate` | SiteCode, SpeciesCode, dates | one site, one pollutant, hourly values |
| Readings | `Data/SiteSpecies/…/Period={Period}/Units={Units}/Step={Step}` | the above + Period, Units, Step | the same, with a choice of period and **units** |
| Readings | `Data/Site/SiteCode/StartDate/EndDate` | SiteCode, dates | one site, every pollutant, hourly (one row per site × pollutant × hour) |
| Readings | `Data/Wide/Site/SiteCode/StartDate/EndDate` | SiteCode, dates | one site, every pollutant, hourly (one row per hour, one column per pollutant) |

### How the parameters connect

| Parameter | Comes from |
|---|---|
| GroupName | `Information/Groups` |
| SiteCode | `Information/MonitoringSites` (or `MonitoringSiteSpecies`) |
| SpeciesCode | `Information/Species` (or `MonitoringSiteSpecies`) |
| StartDate, EndDate | our choice (calendar dates) |
| Period, Units, Step | not in any response; only in the API's documentation PDF (found in the 29 Oct crawl) |

```
Information/Groups ──GroupName──► Information/MonitoringSites ──SiteCode──┐
                                                                         ├──► Data/SiteSpecies ──► hourly readings
Information/Species ──SpeciesCode────────────────────────────────────────┘
                                                      (+ StartDate, EndDate: our choice)
```

### 1.2 Table A: what each endpoint gives (called 30 Oct; raw replies in `survey/`)

A **dimension** is something the data is *about* (you filter and group by it). A **measure** is a number you do
maths on.

| Endpoint | Records | Dimensions | Attributes of those dimensions | Measures |
|---|---|---|---|---|
| `Information/Groups` | 69 groups | group | description | none |
| `Information/MonitoringSites` | 258 sites, each once | **site** | type (6 kinds, e.g. Kerbside), borough, latitude/longitude, opened, closed (`""` = open), owner | none |
| `Information/MonitoringSiteSpecies` | 255 entries for 251 sites | **site × pollutant** | the site attributes above + when each pollutant's measurement started and finished | none |
| `Information/Species` | 6 pollutants | **pollutant** | name, description, health effect | none |
| `Data/SiteSpecies` | 24 per site, pollutant and day | **site, pollutant, time** (hourly) | | **value** (µg/m³; `""` = no reading) |
| `Data/SiteSpecies/…/Period/Units/Step` | as above, blank hours **left out** | site, pollutant, time (**15min, hourly or daily**) | | **value**, in **ugm3 or ppb** |
| `Data/Site` | 144 = 6 pollutants × 24 hours | site, **pollutant**, time (hourly) | | value |
| `Data/Wide/Site` | 25 hours × 7 pollutant columns | site, time (hourly); pollutant is a *column* | units are in the column names | value per column |

### 1.3 What the survey found

| Finding | How we know | Kind |
|---|---|---|
| **Readings are in µg/m³.** The wide endpoint's column names say "Nitrogen Dioxide (ug/m3)", and `Units=ugm3` returns exactly the default values | 19 of 19 values identical | Fact |
| `Units=ppb` converts: 36.1 µg/m³ → 18.9 ppb, a factor of 1.91 (NO2's standard conversion factor) | compared the two replies | Fact |
| **`Period=daily` gives the API's own daily mean**, and it is the mean of the hours that have a value (59.5 = mean of 19 of 24 hours) | recomputed it | Fact |
| `Period=15min` exists: finer than hourly | 76 rows for one day | Fact |
| Valid values: `Period` = hourly, daily, 15min (not "hour" or "Daily"). `Units` = ugm3, ppb. `Step` made no difference | tried each | Fact |
| **A gap looks different in different endpoints:** the default lists the hour with `""`, while the `Period` version leaves the hour out | 24 rows (5 blank) vs 19 rows | Fact |
| **Pollutant codes don't match between endpoints:** the Species list has PM25, `Data/Site` has FINE, and `Data/Wide` has NO and NOx (in neither list) | compared the three | Fact |
| `Data/Wide` includes the EndDate's midnight (25 rows) and drops the seconds from times ("2026-10-28 00:00"), unlike the others | compared | Fact |
| 2 sites have no coordinates: ME5, ME6 (Merton samplers, closed 2015) | blank `@Latitude` | Fact |
| Sites appear more than once only in `MonitoringSiteSpecies` (HS1, HS5), never in `MonitoringSites` | 255 entries / 251 codes vs 258 / 258 | Fact |

### 1.4 The question model

The readings are a set of tuples:

> **Readings ⊆ Site × Pollutant × Time × Value**

where each site carries its attributes (type, borough, location) and each time can be broken into features (hour of
day, weekday, date). A question is a statistic over a subset, possibly grouped:

> **Q = f( { r ∈ Readings : filter(r) } grouped by g )**

- **filter** picks the subset, using any dimension or attribute: site = MY1, pollutant = NO2, time in October
- **g** splits it into groups: by site, by site type, by hour of day, by weekday
- **f** is the statistic: mean, max, count, share of hours above a threshold, or a ratio between two groups

This is exactly the shape of SQL: `SELECT f(value) FROM readings WHERE filter GROUP BY g`. A question is only
*expressible* if every dimension it uses appears in Table A. "Do tides in Africa affect London's air?" isn't, because
there's no tide dimension.

### Considered and left out (27)

| Endpoints | Why left out |
|---|---|
| `Daily/…` and `Hourly/MonitoringIndex`, `Data/SiteSpeciesIndexDays` | air quality *index levels* (1–10 bands) derived from readings, not readings |
| `Annual/MonitoringObjective`, `Annual/MonitoringReport`, `Annualiser/…` | yearly summaries and calculations derived from readings |
| `Data/DiffusionTube` | a different kind of measurement (monthly passive tubes), and its parameters appear in no response |
| `Data/Traffic/Site` | traffic counts, not pollutants. **Outside the brief's scope, but worth remembering for stage 3** (traffic → NO2) |
| `Hourly/Map/…`, `Information/News`, `AirPollutionGuide`, `IndexHealthAdvice`, `Objective` | maps, news and guidance text. The last two return HTTP 400 |
