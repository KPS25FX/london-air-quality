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
