"""Extract + Load with dlt: API -> raw tables in air.duckdb (schema "raw"). No cleaning here; that's dbt's job.

Run:  .venv/bin/python load.py
"""

from datetime import date, timedelta

import dlt
from dlt.sources.helpers import requests        # requests with retries built in

API = "https://api.erg.ic.ac.uk/AirQuality"
SITES, SPECIES, DAYS_BACK = ["MY1", "GT1"], "NO2", 7


def AsList(Value):
    """The one quirk dlt can't guess: one item comes back as a dict, several as a list."""
    return [] if Value is None else Value if isinstance(Value, list) else [Value]


# Every column is declared as text, so dlt stores exactly what the API sent ("36.1", "").
# Turning text into numbers and dates is a decision, and it's made in one visible place: dbt staging.
@dlt.resource(write_disposition="replace", columns={"Latitude": {"data_type": "text"},
                                                     "Longitude": {"data_type": "text"},
                                                     "DateClosed": {"data_type": "text"},
                                                     "DateOpened": {"data_type": "text"}})
def sites():
    Data = requests.get(f"{API}/Information/MonitoringSiteSpecies/GroupName=London/Json").json()
    for Site in AsList(Data["Sites"]["Site"]):
        # Drop the "@" ourselves: left in, dlt renames "@SiteCode" to "a_site_code". dlt turns SiteCode into site_code.
        # "Species" is a nested list per site that this project doesn't need.
        yield {Key.lstrip("@"): Value for Key, Value in Site.items() if Key != "Species"}


# merge + primary key = "insert new hours, overwrite hours we already have" (the old Save function).
@dlt.resource(write_disposition="merge", primary_key=("site_code", "species_code", "measured_at"),
              columns={"measured_at": {"data_type": "text"}, "value": {"data_type": "text"}})
def readings(DaysBack=DAYS_BACK):
    End = date.today() + timedelta(days=1)       # the API excludes EndDate, so this includes today
    Start = End - timedelta(days=DaysBack)
    for Site in SITES:
        Data = requests.get(f"{API}/Data/SiteSpecies/SiteCode={Site}/SpeciesCode={SPECIES}"
                            f"/StartDate={Start}/EndDate={End}/Json").json()
        for Hour in AsList(Data["RawAQData"].get("Data")):
            yield {"site_code": Site, "species_code": SPECIES,
                   "measured_at": Hour["@MeasurementDateGMT"], "value": Hour["@Value"]}


if __name__ == "__main__":
    Pipeline = dlt.pipeline(pipeline_name="air", destination=dlt.destinations.duckdb("air.duckdb"),
                            dataset_name="raw")
    print(Pipeline.run([sites(), readings()]))
