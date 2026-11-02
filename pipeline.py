"""London's air, on repeat: fetch the last 7 days of hourly NO₂ for two London sites into air.duckdb.

Run:  python pipeline.py

Every run adds new hours, updates hours already stored, never duplicates, records every value that changed, and logs
itself. It checks each request before the call (the API must list the site and pollutant as a pair) and each reply
after it (it must hold at least one value), and stops with an error rather than store nothing.
Presentation.ipynb works through how each step was found.
"""
import json, urllib.request
from datetime import date, datetime, timedelta

import duckdb
import pandas

SITES = ["MY1", "GT1"]      # Marylebone Road (kerbside), Station Walk (urban background)
SPECIES = "NO2"
DAYS = 7

Database = duckdb.connect("air.duckdb")
Database.execute("""
CREATE TABLE IF NOT EXISTS readings (
    SiteCode           VARCHAR,
    SpeciesCode        VARCHAR,
    MeasurementDateGMT TIMESTAMP,
    Value              DOUBLE,
    PRIMARY KEY (SiteCode, SpeciesCode, MeasurementDateGMT)
);
CREATE TABLE IF NOT EXISTS changes (
    RunAt              TIMESTAMP,
    SiteCode           VARCHAR,
    SpeciesCode        VARCHAR,
    MeasurementDateGMT TIMESTAMP,
    OldValue           DOUBLE,
    NewValue           DOUBLE
);
CREATE TABLE IF NOT EXISTS runs (
    RunAt              TIMESTAMP,
    StartDate          DATE,
    EndDate            DATE,
    Fetched            INTEGER,
    New                INTEGER
);
""")

# the endpoints we rely on, and where each one keeps its records
SitesUri: str = "/Information/MonitoringSites/GroupName={GroupName}/Json"
SiteSpeciesUri: str = "/Information/MonitoringSiteSpecies/GroupName={GroupName}/Json"
ReadingsUri: str = "/Data/SiteSpecies/SiteCode={SiteCode}/SpeciesCode={SpeciesCode}/StartDate={StartDate}/EndDate={EndDate}/Json"

RecordPaths: dict[str, list[str]] = {
    SitesUri:       ["Sites", "Site"],
    SiteSpeciesUri: ["Sites", "Site"],
    ReadingsUri:    ["RawAQData", "Data"],      # EndDate itself is not included
}


def Get(Uri: str, **Values: str) -> dict:
    return json.load(urllib.request.urlopen("https://api.erg.ic.ac.uk/AirQuality" + Uri.format(**Values)))


# a list with one item comes back as a single dictionary
def AsList(Value: dict | list) -> list:
    return Value if isinstance(Value, list) else [Value]


def Follow(Reply: dict, Path: list[str]) -> list[dict]:
    Value = Reply
    for Key in Path:
        Value = Value[Key]
    return AsList(Value)


# the API puts @ in front of field names and sends a missing value as ""
def Clean(Table: pandas.DataFrame) -> pandas.DataFrame:
    return Table.rename(columns=lambda Name: Name.removeprefix("@")).replace("", None)


def GetValidPairs() -> set[tuple[str, str]]:
    SiteSpeciesSites = Follow(Get(SiteSpeciesUri, GroupName="London"), RecordPaths[SiteSpeciesUri])
    for site in SiteSpeciesSites:
        site["Species"] = AsList(site["Species"])
    SiteSpeciesTable = Clean(pandas.json_normalize(SiteSpeciesSites, record_path="Species", meta=["@SiteCode"]))
    return set(zip(SiteSpeciesTable["SiteCode"], SiteSpeciesTable["SpeciesCode"]))


def GetReadings(**Values: str) -> pandas.DataFrame:
    # before the call: is the pair one the API lists?
    if (Values["SiteCode"], Values["SpeciesCode"]) not in ValidPairs:
        raise ValueError(f"Not a listed pair: {Values['SiteCode']} × {Values['SpeciesCode']}")
    Rows = Follow(Get(ReadingsUri, **Values), RecordPaths[ReadingsUri])
    # after the call: listed doesn't mean it has data
    if not any(row["@Value"] != "" for row in Rows):
        raise ValueError(f"No values: {Values['SiteCode']} × {Values['SpeciesCode']}, {Values['StartDate']} to {Values['EndDate']}")
    return Clean(pandas.json_normalize(Rows)).assign(**Values)


def SaveReadings(Readings: pandas.DataFrame) -> None:
    Database.register("new_readings", Readings)

    # 1. record any hour whose value is different from what we stored
    Database.execute("""
    INSERT INTO changes
    SELECT ?, SiteCode, SpeciesCode, MeasurementDateGMT, r.Value, CAST(n.Value AS DOUBLE)
    FROM new_readings n JOIN readings r USING (SiteCode, SpeciesCode, MeasurementDateGMT)
    WHERE r.Value IS DISTINCT FROM CAST(n.Value AS DOUBLE)
    """, [datetime.now()])

    # 2. add new hours, overwrite existing ones
    Database.execute("""
    INSERT INTO readings
    SELECT SiteCode, SpeciesCode, MeasurementDateGMT, Value
    FROM new_readings
    ON CONFLICT (SiteCode, SpeciesCode, MeasurementDateGMT) DO UPDATE SET Value = excluded.Value
    """)


if __name__ == "__main__":
    SitesTable = Clean(pandas.json_normalize(Follow(Get(SitesUri, GroupName="London"), RecordPaths[SitesUri])))
    Database.execute("CREATE OR REPLACE TABLE sites AS SELECT * FROM SitesTable")   # DuckDB finds the DataFrame by its name
    ValidPairs = GetValidPairs()

    EndDate = date.today() + timedelta(days=1)          # EndDate is excluded, so this includes today
    StartDate = EndDate - timedelta(days=DAYS)
    Readings = pandas.concat([GetReadings(SiteCode=SiteCode, SpeciesCode=SPECIES, StartDate=str(StartDate), EndDate=str(EndDate))
                              for SiteCode in SITES], ignore_index=True)
    Before = Database.execute("SELECT count(*) FROM readings").fetchall()[0][0]
    SaveReadings(Readings)
    After = Database.execute("SELECT count(*) FROM readings").fetchall()[0][0]
    Database.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?)", [datetime.now(), StartDate, EndDate, len(Readings), After - Before])
    print(f"{StartDate} to {EndDate}: fetched {len(Readings)} hours, {After - Before} new.")

    # a site can stop measuring without the site list saying so
    Database.sql("""
    SELECT SiteCode, SpeciesCode, max(MeasurementDateGMT) AS LastMeasured
    FROM readings WHERE Value IS NOT NULL
    GROUP BY SiteCode, SpeciesCode
    """).show()
