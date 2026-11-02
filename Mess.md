# Mess: what the API does that we didn't expect

Checked against the live API on 1 Nov 2026, unless a line says otherwise. Each finding says what happens and what it
means for our code.

The findings fall into four classes, worst first:

| Class | Example | How we deal with it |
|---|---|---|
| Silent: the request looks valid, the API says 200, the data is empty or wrong | a site code that doesn't exist | take inputs from the API's own tables, and check every reply |
| Loud: the API returns an error | 400 from a documented endpoint | let it fail and log it; a 400 isn't always "broken" |
| Mess: names, shapes and types that are odd but stable | `@SiteCode` vs `SiteCode` | a named rule, applied once at the boundary |
| Over time: things only seen by watching | late values, sites that stop | re-fetch 7 days, keep `changes` and `runs` |

## Silent

| Request | What comes back |
|---|---|
| `Data/SiteSpecies` for a site that doesn't exist (ZZZ × NO2) | 200, one row per hour, every `@Value` is `""` |
| `Data/SiteSpecies` for a pair the site doesn't measure (GT1 × CO) | 200, 168 rows, every `@Value` is `""` |
| `Data/SiteSpecies` for a pair listed as measured, with no end date (MY1 × CO) | 200, values for 28% of hours in 2026, 4 of the last 168, none since 30 Oct 08:00 |
| `MonitoringSites` for a group that doesn't exist (`GroupName=Nonsense`) | 200, `{"Sites": null}` |
| `Hourly/MonitoringIndex/SiteCode` for a site with no current data (seen 29 Oct, not re-checked) | 200, a bare `null` |

So "nothing" has three shapes: rows of `""`, `null`, or an empty list. None of them is an error.

Valid pairs: `MonitoringSiteSpecies/GroupName=London` lists the species each site measures, with start and end dates.
It has 650 rows but 646 distinct (site, species) pairs, out of 1,548 possible (258 London sites × 6 species). The other
902 are pairs a site doesn't measure, and GT1 × CO shows what those return.

Decision: build requests only from values the API gave us (site codes from `MonitoringSites`, pairs and date ranges
from `MonitoringSiteSpecies`), and check every reply: one with no non-empty value is an error, not data. We need both,
because "listed" doesn't mean "has data" (MY1 × CO).

## Loud

| Request | What comes back |
|---|---|
| `Information/IndexHealthAdvice/Json` and `Information/Objective/Json`, which take no parameters | 400 |
| `Hourly/Map/SpeciesName=Nitrogen Dioxide` | 400. `SpeciesName=NO2` works, so the parameter wants a code despite its name |
| `Data/SiteSpecies` with StartDate after EndDate | 400 |
| `Daily/MonitoringIndex/Latest/SiteCode=BL0`, a site with no current data | 400 |

Error replies are an XHTML page that starts with a UTF-8 byte order mark, not JSON.

Decision: catch `HTTPError` and log its code; let any other exception stop the run. A 400 can mean "broken" or
"nothing for this input", so it's a lead, not a verdict. The help page is a claim, and only a call checks it.

## Names

- The same thing has different names in different places. `SiteCode` is the parameter and `@SiteCode` the field. The
  Annualiser endpoints use `site`, `species` and `year`. The field `@LocalAuthorityCode` fills the parameter
  `LocalAuthorityId` (seen 29 Oct).
- Endpoints connect through reply fields, not URL paths: Groups returns `@GroupName`, which fills `GroupName`. The rule
  "`@X` fills `X`" misses `site`, `species`, `year` and `LocalAuthorityId`.
- Some parameters appear in no reply. Dates and years we choose ourselves. `backA`–`backD`, `mean`, `code`, `montype`,
  `Period`, `Units`, `Step`, `skip` and `limit` come from nowhere in the API (seen 29 Oct); the documentation PDF is
  the only place they might be explained.
- Group IDs have typos and test entries: `almbridget` is Elmbridge and `runnymeade` is Runnymede; `singlela` is "sub
  domain test" and `CambridgeCity` is "Demo group for tender". Use IDs exactly as given.
- The species list has 6 codes (CO, NO2, O3, PM10, PM25, SO2), but `Data/Wide/Site` for MY1 also reports Nitric Oxide
  and Oxides of Nitrogen.

Decision: one name per thing in our tables. `JOIN sites ON SiteCode = "@SiteCode"` is the one place where the API's two
names meet.

## Shape and types

- Every reply is wrapped twice, with different keys per endpoint: `["Groups"]["Group"]`,
  `["AirQualitySpecies"]["Species"]`, `["Sites"]["Site"]`, `["RawAQData"]["Data"]`. Decision: pick the path per
  endpoint, then `json_normalize`.
- A list with one item comes back as a single object. In `MonitoringSiteSpecies`, `Species` is a list for 196 sites and
  a dict for 58. Decision: wrap a dict in a list before flattening.
- Every value is a string: numbers, dates, coordinates, even booleans (`"False"`). Decision: we declare the types
  (DuckDB column types, Pydantic).
- Missing is `""`, not null: `@Value`, `@WebsiteURL`, and `@DateClosed`, where `""` means the site is still open.
  Decision: `NULLIF(…, '')` at the boundary.
- `@LatitudeWGS84` and `@LongitudeWGS84` aren't degrees despite the name: they run from 6,677,126 to 6,740,432, which
  looks like Web Mercator metres. `@Latitude` and `@Longitude` are degrees (50.91 to 51.67). Decision: use `@Latitude`
  and `@Longitude`.
- Units differ by species and aren't in the readings reply: `Data/Wide/Site` labels CO in mg/m³ and the others in
  µg/m³. Decision: state the unit per species, citing that endpoint.

## Site lists

- `MonitoringSites/GroupName=London` has 258 sites, 73 of them still open (`@DateClosed` is `""`). Two (ME5 and ME6, the
  Merton e-samplers) have no coordinates.
- `MonitoringSiteSpecies/GroupName=London` has 254 rows but 251 sites: HS5 is listed three times and HS1 twice.
  Decision: key on SiteCode.
- 7 sites are in the first list but not the second: AZ99, BQ1–BQ4, ME5, ME6.
- The lists change from day to day: `MonitoringSiteSpecies` had 254 rows on 28 Oct, 255 on 29 Oct and 254 today.
  Decision: refresh `sites` on every run (pipeline.py does).

## Time

- Timestamps are GMT all year. 25 Oct, when the clocks went back, has 24 hours and no repeated hour. Decision: store
  GMT, and convert only for display.
- EndDate is exclusive: StartDate 30 Oct with EndDate 31 Oct gives the 24 hours of 30 Oct. Decision: EndDate is
  tomorrow, to include today.
- Rows come back up to the current hour, and the newest are `""` at first and filled in later. All 5 rows in `changes`
  so far are NULL → value: late arrivals, not corrections of real values. Decision: re-fetch 7 days and record every
  change.
- Gaps are scattered, not one outage: MY1 NO2 is missing 66 of the 379 hours since 17 Oct, 1 to 9 hours on 15 of the
  16 days. GT1 is missing 4. Decision: compare the sites only on hours where both have a value.
- Sites stop measuring without the lists saying so: BL0 had no NO2 after 3 Oct (found 28 Oct), and MY1 CO has had
  nothing since 30 Oct 08:00 but is still listed with no end date.
- `Hourly/Map` labels are wrong: "23:00 on Friday 31st November 2026" (there is no 31 November, and 31 July 2026 was a
  Friday), next to `@MeasurementDate` 31/07/2026 and `@StartDate` 01/11/2026. Its dates are dd/mm/yyyy, while readings
  are yyyy-mm-dd hh:mm:ss. Decision: don't use `Hourly/Map` timestamps, and parse each endpoint's date format on its own.

## The questions I started with

**How do you know which permutations of site code × pollutant have valid data?** The API lists them itself:
`MonitoringSiteSpecies` gives 646 (site, species) pairs. But a listed pair can still have no data (MY1 × CO), so the
reply has to be checked too. See Silent above.

**If you call site code × pollutant for an invalid pair, you get an empty table.** Confirmed: 200, one row per hour,
every value `""`. The same happens for a site code that doesn't exist.

**What would happen if this was fed to a machine learning pipeline?** It would learn from hours that were never
measured: as gaps if it handles missing values, or as zeros if something fills them in. Nothing would fail, so nobody
would know. That's why the pipeline raises an error on an empty reply instead of storing it.

**How can we make sure we understand the full set of valid combinations of parameters, and the data each one gives?**
In three ways, because they are three kinds of knowing. The valid parameters come from the API's own lists
(`ValidPairs`), before any call. Whether a combination has data is only known by calling it (the reply check). And
whether it still has data is only known by watching over time (`runs`, `changes`, and the last measured hour per site).

**F : valid parameter tuples → tables.** `GetReadings` in the notebook is this F. Its domain is `ValidPairs` (with
dates), checked before the call. It is a partial function: some tuples in its domain still give no table, and the
reply check is what says so.
