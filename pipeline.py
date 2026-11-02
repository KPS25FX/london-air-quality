"""Fetch the last 7 days of hourly NO2 for two London sites and save them to air.duckdb.

Run:  python pipeline.py
Every run adds new hours, updates hours already stored, never duplicates, and records any value that changed.
It also refreshes the London site list (sites) and logs itself (runs).
It stops with an error if a site isn't an open London site, or if a reply has no values at all.
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
    "@MeasurementDateGMT" TIMESTAMP,
    "@Value"              DOUBLE,
    SiteCode              VARCHAR,
    SpeciesCode           VARCHAR,
    StartDate             DATE,
    EndDate               DATE,
    PRIMARY KEY (SiteCode, SpeciesCode, "@MeasurementDateGMT")
);
CREATE TABLE IF NOT EXISTS changes (
    RunAt                 TIMESTAMP,
    SiteCode              VARCHAR,
    SpeciesCode           VARCHAR,
    "@MeasurementDateGMT" TIMESTAMP,
    OldValue              DOUBLE,
    NewValue              DOUBLE
);
CREATE TABLE IF NOT EXISTS runs (
    RunAt                 TIMESTAMP,
    StartDate             DATE,
    EndDate               DATE,
    Fetched               INTEGER,
    New                   INTEGER
);
""")


# Parameters: {"SiteCode": "MY1", "SpeciesCode": "NO2", "StartDate": "YYYY-MM-DD", "EndDate": "YYYY-MM-DD"}
# EndDate itself is not included in the results.
def GetReadings(Parameters):
    Template = "/Data/SiteSpecies/SiteCode={SiteCode}/SpeciesCode={SpeciesCode}/StartDate={StartDate}/EndDate={EndDate}/Json"
    Url = "https://api.erg.ic.ac.uk/AirQuality" + Template.format(**Parameters)
    Data = json.load(urllib.request.urlopen(Url))

    # a site that doesn't exist, or a species it doesn't measure, still answers 200 with every value empty
    if not any(Row["@Value"] != "" for Row in Data["RawAQData"]["Data"]):
        raise ValueError(f"No values in {Url}")
    return pandas.json_normalize(Data["RawAQData"]["Data"]).assign(**Parameters)


def SaveReadings(Readings):
    Database.register("new_readings", Readings)

    # 1. record any hour whose value is different from what we stored
    Database.execute("""
    INSERT INTO changes
    SELECT ?, SiteCode, SpeciesCode, "@MeasurementDateGMT", r."@Value", CAST(NULLIF(n."@Value", '') AS DOUBLE)
    FROM new_readings n JOIN readings r USING (SiteCode, SpeciesCode, "@MeasurementDateGMT")
    WHERE r."@Value" IS DISTINCT FROM CAST(NULLIF(n."@Value", '') AS DOUBLE)
    """, [datetime.now()])

    # 2. add new hours, overwrite existing ones
    Database.execute("""
    INSERT INTO readings
    SELECT "@MeasurementDateGMT", NULLIF("@Value", ''), SiteCode, SpeciesCode, StartDate, EndDate
    FROM new_readings
    ON CONFLICT (SiteCode, SpeciesCode, "@MeasurementDateGMT") DO UPDATE
    SET "@Value" = excluded."@Value", StartDate = excluded.StartDate, EndDate = excluded.EndDate
    """)


if __name__ == "__main__":
    Sites = pandas.json_normalize(json.load(urllib.request.urlopen(
        "https://api.erg.ic.ac.uk/AirQuality/Information/MonitoringSites/GroupName=London/Json"))["Sites"]["Site"])
    Database.execute("CREATE OR REPLACE TABLE sites AS SELECT * FROM Sites")   # DuckDB finds the DataFrame by its name

    NotOpen = set(SITES) - set(Sites[Sites["@DateClosed"] == ""]["@SiteCode"])   # "" means still open
    if NotOpen:
        raise ValueError(f"Not open London sites: {NotOpen}")

    EndDate = date.today() + timedelta(days=1)          # EndDate is excluded, so this includes today
    StartDate = EndDate - timedelta(days=DAYS)
    Readings = pandas.concat([GetReadings({"SiteCode": SiteCode, "SpeciesCode": SPECIES, "StartDate": StartDate, "EndDate": EndDate})
                              for SiteCode in SITES], ignore_index=True)
    Before = Database.execute("SELECT count(*) FROM readings").fetchall()[0][0]
    SaveReadings(Readings)
    After = Database.execute("SELECT count(*) FROM readings").fetchall()[0][0]
    Database.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?)", [datetime.now(), StartDate, EndDate, len(Readings), After - Before])
    print(f"{StartDate} to {EndDate}: fetched {len(Readings)} hours, {After - Before} new.")

    # a site can stop measuring without the site list saying so
    Database.sql("""
    SELECT SiteCode, SpeciesCode, max("@MeasurementDateGMT") AS LastMeasured
    FROM readings WHERE "@Value" IS NOT NULL
    GROUP BY SiteCode, SpeciesCode
    """).show()
