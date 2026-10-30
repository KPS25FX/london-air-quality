"""Before/after check: does the dlt + dbt stack give the same data as the original pipeline.py?

Runs the original GetSites/GetReadings + Shape functions live, over the same dates the stack loaded,
and asserts the results match the stack's clean tables. Run it straight after load.py + dbt build.

Run (from the project root, with the original venv, which has pandas):
    .venv/bin/python stack/validate.py
"""

import sys
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas

Root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Root))
import pipeline                                                     # noqa: E402  (the original, as the reference)

Stack = duckdb.connect(str(Root / "stack" / "air.duckdb"), read_only=True)


# ---- Sites ----

Before = pipeline.ShapeSites(pipeline.GetSites(pipeline.GROUP))
After = Stack.sql("SELECT * FROM clean.sites").df()

print(f"sites   original: {len(Before)} rows, {Before.SiteCode.nunique()} unique   stack: {len(After)} rows")
assert set(Before.SiteCode) == set(After.site_code), "a site is in one version but not the other"
Before = Before.drop_duplicates().set_index("SiteCode").sort_index()
After = After.set_index("site_code").sort_index()
for Old, New in [("SiteName", "site_name"), ("SiteType", "site_type"), ("Latitude", "latitude"),
                 ("Longitude", "longitude"), ("DateClosed", "date_closed")]:
    Same = (Before[Old] == After[New]) | (Before[Old].isna() & After[New].isna())   # missing == missing counts as same
    assert Same.all(), f"sites.{New} differs for {list(Same[~Same].index)}"


# ---- Readings ----

Start, Last = Stack.execute("SELECT min(measured_at)::DATE, max(measured_at)::DATE FROM clean.readings").fetchall()[0]
End = Last + timedelta(days=1)
Before = pipeline.ShapeReadings(pandas.concat([pipeline.GetReadings(Site, pipeline.SPECIES, Start, End)
                                               for Site in pipeline.SITES], ignore_index=True))
After = Stack.sql("SELECT * FROM clean.readings").df()

print(f"readings original: {len(Before)} rows   stack: {len(After)} rows   ({Start} to {End}, end exclusive)")
Key = ["SiteCode", "MeasuredAt"]
Both = Before.merge(After.rename(columns={"site_code": "SiteCode", "measured_at": "MeasuredAt", "value": "New"}),
                    on=Key, how="outer", indicator=True)
OnlyOld, OnlyNew = Both[Both._merge == "left_only"], Both[Both._merge == "right_only"]
Changed = Both[(Both._merge == "both") & ~((Both.Value == Both.New) | (Both.Value.isna() & Both.New.isna()))]

print(f"         only in original: {len(OnlyOld)}   only in stack: {len(OnlyNew)}   different value: {len(Changed)}")
if len(Changed):
    print(Changed[Key + ["Value", "New"]].to_string(index=False))   # e.g. a reading that arrived between the two fetches
assert len(OnlyOld) == 0 and len(OnlyNew) == 0, "an hour is in one version but not the other"
assert len(Changed) == 0, "a value differs (if it was blank -> number, a reading arrived in between: rerun load.py)"
print("OK: the stack matches the original pipeline.")
