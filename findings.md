Information/MonitoringSiteSpecies (GroupName=London, checked 2026-10-28)

- Shape: ["Sites"]["Site"] -> 254 sites. Each site has a nested Species. Fact.
- Species is a list for 196 sites but a single dict for 58 (sites with one species). The XML -> JSON quirk is real.
  Wrap a dict in a list before flattening. Fact.
- @DateClosed is "" for 72 sites: the open ones. "" means "still open", so parse it to None. Fact.
- Every value is a string, including dates and coordinates. Types must be declared by us. Fact.
- @LatitudeWGS84 / @LongitudeWGS84 look like Web Mercator metres (e.g. 6717454.58), not WGS84 degrees,
  despite the name. Use @Latitude / @Longitude. Inference (from the magnitudes).


What I'd do next: keep every version of a reading (append-only)

Now: readings are upserted. A late or ratified value overwrites the old one, so only the latest value is kept.

Next: an append-only readings_history (site_code, species_code, measured_at, value, fetched_at).
- Insert a row only when the hour is new or its value has changed since the last fetch, so re-runs still add nothing.
- Current picture = latest row per (site, species, hour).
- "What did we know on date X?" = latest row per hour with fetched_at <= X.
- Why: nothing is ever lost, and every number in the analysis can be traced to the fetch it came from.


The API map (crawl run 2026-10-29, see Explore-Collect-Analyse.ipynb part A and api_map/)

How it was found: start knowing only the help page and the calendar; call an endpoint only once a value is
known for every parameter; up to 3 sample values per parameter; record every call and where every value came from.

- 36 JSON endpoints, 25 distinct parameter names. The crawl needs 3 levels: Level 0 (6 endpoints, no parameters),
  Level 1 (11, needs GroupName or SpeciesCode), Level 2 (14, needs SiteCode, LocalAuthorityId or AirQualityIndex). Fact.
- Main sources: GroupName <- Information/Groups (69 values). SpeciesCode <- Information/Species (6).
  SiteCode <- Information/MonitoringSites (391 across 3 sample groups). LocalAuthorityId <- the @LocalAuthorityCode
  field of Daily/MonitoringIndex. AirQualityIndex <- Hourly/MonitoringIndex. Fact.
- 5 endpoints can never be reached from what the API itself returns: their parameters (backA-D and mean; code and
  montype; Period, Units and Step; skip and limit) appear in no response. They are only explained, if anywhere,
  in the documentation PDF. Fact.
- Information/IndexHealthAdvice and Information/Objective fail with HTTP 400 even though they take no parameters:
  broken on the API side. Fact.
- The same thing has different names in different places: the field @LocalAuthorityCode fills the parameter
  LocalAuthorityId; the Annualiser endpoints use lowercase site, species, year. Handled with a hand-written alias map. Fact.
- Hourly/Map/SpeciesName={SpeciesName} fails when given a species name ("Nitrogen Dioxide") and works when given
  a species code ("NO2", tested 2026-10-28). The parameter is misnamed. Fact.
- Some endpoints answer a site with no current data in three different ways: HTTP 400 (Daily/MonitoringIndex/Latest/
  SiteCode), a bare null with HTTP 200 (Hourly/MonitoringIndex/SiteCode, 2 of 3 samples), or an empty Data list.
  The same endpoints worked for MY1. So "failed" or "1/3 ok" can mean "no data for that sample", not "broken". Inference.
- A list with one item comes back as a single object, so one field can sit at two paths (Species[].@SpeciesCode
  and Species.@SpeciesCode). The fields table shows both. Fact.
- Every value in every response is a string, including numbers and dates. Fact.

The data we collect (pipeline.py, part B)

- The London sites list had 254 rows on 28 Oct and 255 on 29 Oct, but only 251 distinct site codes: HS1 and HS5
  (Hounslow - Brentford, both closed) are listed three times each. The sites primary key keeps one row each. Fact.
- Bloomsbury (BL0), the first background site chosen, has no NO2 after 3 Oct 2026, so Station Walk (GT1, 99% of
  hours measured) replaced it. Fact (found 28 Oct).
- Readings arrive late and out of order: on 29 Oct, Marylebone Road had values for 10:00 and 11:00 but not yet for
  08:00, 09:00 or 12:00. This is why missing hours are kept as NULL and the last 7 days are re-fetched. Fact.
- Marylebone Road has values for 76% of hours, Station Walk for 99%. Comparisons use only hours where both have one. Fact.

Analysis (part C, 1 Aug - 29 Oct 2026)

- Beside Marylebone Road, NO2 averaged 4.1x the background level (hours where both sites measured).
- The road adds the most at 16:00 GMT: about +52 µg/m³ on average.
- Days above the WHO daily guideline (25 µg/m³): 68 of 70 at Marylebone Road, 7 of 89 at Station Walk
  (days with at least 18 hours measured).


How these findings were found, and how to find more

You cannot search for a finding you cannot name. But you can run the same cheap checks on everything, and
compare what you expected with what you got. The surprises then name themselves. Almost none of the findings
above came from cleverness; each came from one of these checks:

- HS1 / HS5 listed three times     <- count vs distinct count: len(Sites) vs Sites["SiteCode"].nunique().
                                      (Noticed because 254 sites went into the database and 251 came out.)
- BL0 stopped on 3 October         <- latest timestamp per site: max(measured_at) grouped by site.
                                      One site was weeks behind the other.
- Readings arrive late, out of order <- count missing values, and look at the newest rows (.tail()):
                                      values sat between blanks.
- List-or-object quirk             <- count the types of one field: Counter(type(x) for x in ...).
                                      Two types for one field always has a story.
- "WGS84" coordinates are not degrees <- is the size plausible? A latitude of 6,717,454 is impossible.
                                      .describe() (min / max) on every numeric column catches this.
- Misnamed SpeciesName parameter   <- treat a failure as a lead, not noise: read the error, try the obvious alternative.
- Three ways of saying "no data", broken endpoints <- log every call's result, not just the successes,
                                      then look at the odd ones.

The general method: profile everything, assert your assumptions, log every call.

1. Profile every table, every column, the same five ways:
       Table.dtypes          is each column the type I think it is?
       Table.isna().sum()    how much is missing?
       Table.nunique()       how many distinct values? Compare with len(Table): is the key really unique?
       Table.describe()      min / max / mean: is anything impossible?
       Table.sample(5)       look at real rows, not only the first five
2. Write every assumption as an assert, so it fails loudly instead of hiding:
       "site codes are unique", "every site has a reading in the last day", "latitude is between 51 and 52".
   Most findings are an assertion failing.
3. Log every external call and its result (ok / error / empty), and read the log.
4. When something is odd, form one guess and test it with one call (e.g. "maybe it wants the code, not the name").

The mindset: "What would have to be true for my code to be right? Check each of those things."
You do not need to know what you are looking for; you need to check what you are assuming.
This is also how to approach a client's data: profile it, write down their assumptions as checks, run them.
