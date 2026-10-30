"""Collect hourly NO2 for a busy road and a nearby background site into DuckDB.

Run:  python pipeline.py
Each run fetches the last DAYS_BACK days and upserts them, so new hours are added,
late or corrected hours are updated, and nothing is ever duplicated.
"""

import json
import urllib.request
from datetime import date, datetime, timedelta

import duckdb
import pandas

# ---- Settings: the choices, made once in the notebook's menus ---------------------------------

API_BASE = "https://api.erg.ic.ac.uk/AirQuality"
DATABASE = "air.duckdb"
GROUP = "London"
SITES = ["MY1", "GT1"]          # Marylebone Road (kerbside), Station Walk (urban background)
SPECIES = "NO2"
DAYS_BACK = 7                   # re-fetch a week each run, so late readings get picked up


# ---- Extract: API -> raw tables (everything still text) ---------------------------------------

def CallApi(Path):
    with urllib.request.urlopen(API_BASE + Path, timeout=60) as Response:
        return json.loads(Response.read())


def AsList(Value):
    """The API returns one item as a dict and several as a list. Always give back a list."""
    return Value if isinstance(Value, list) else [Value]


def GetSites(Group):
    Data = CallApi(f"/Information/MonitoringSiteSpecies/GroupName={Group}/Json")
    Rows = []
    for Site in AsList(Data["Sites"]["Site"]):
        Rows.append({"SiteCode": Site["@SiteCode"],
                     "SiteName": Site["@SiteName"],
                     "SiteType": Site["@SiteType"],
                     "Latitude": Site["@Latitude"],
                     "Longitude": Site["@Longitude"],
                     "DateClosed": Site["@DateClosed"]})
    return pandas.DataFrame(Rows)


def GetReadings(Site, Species, Start, End):
    Data = CallApi(f"/Data/SiteSpecies/SiteCode={Site}/SpeciesCode={Species}"
                   f"/StartDate={Start}/EndDate={End}/Json")
    Rows = []
    for Hour in AsList(Data["RawAQData"].get("Data", [])):        # one entry per hour
        Rows.append({"SiteCode": Site,
                     "SpeciesCode": Species,
                     "MeasuredAt": Hour["@MeasurementDateGMT"],
                     "Value": Hour["@Value"]})
    return pandas.DataFrame(Rows)


# ---- Shape: text -> proper types ("" means missing) --------------------------------------------

def ShapeSites(Sites):
    Sites = Sites.copy()
    Sites["Latitude"] = pandas.to_numeric(Sites["Latitude"])
    Sites["Longitude"] = pandas.to_numeric(Sites["Longitude"])
    Sites["DateClosed"] = pandas.to_datetime(Sites["DateClosed"].replace("", None))     # missing = still open
    return Sites


def ShapeReadings(Readings):
    Readings = Readings.copy()
    Readings["MeasuredAt"] = pandas.to_datetime(Readings["MeasuredAt"])
    Readings["Value"] = pandas.to_numeric(Readings["Value"].replace("", None))         # missing = not arrived yet
    return Readings


# ---- Load: upsert into DuckDB and log the run -------------------------------------------------

TABLES = """
CREATE TABLE IF NOT EXISTS sites (
    site_code   VARCHAR PRIMARY KEY,
    site_name   VARCHAR NOT NULL,
    site_type   VARCHAR,
    latitude    DOUBLE,
    longitude   DOUBLE,
    date_closed TIMESTAMP                -- NULL = still open
);
CREATE TABLE IF NOT EXISTS readings (
    site_code    VARCHAR   NOT NULL,
    species_code VARCHAR   NOT NULL,
    measured_at  TIMESTAMP NOT NULL,     -- start of the hour, GMT
    value        DOUBLE,                 -- µg/m³ (assumed: the API does not say); NULL = no reading yet
    PRIMARY KEY (site_code, species_code, measured_at)
);
CREATE TABLE IF NOT EXISTS runs (
    run_at      TIMESTAMP NOT NULL,
    days_back   INTEGER   NOT NULL,
    new_rows    INTEGER   NOT NULL,      -- hours we had never stored before
    total_rows  INTEGER   NOT NULL
);
"""


def Save(Database, Sites, Readings, DaysBack):
    # The DataFrames are given names unlike any table, because DuckDB ignores case (Sites would mean sites).
    NewSites, NewReadings = Sites, Readings
    Database.execute(TABLES)
    Database.execute("BEGIN")                                    # all or nothing
    Before = Database.execute("SELECT count(*) FROM readings").fetchone()[0]
    Database.execute("INSERT OR REPLACE INTO sites SELECT * FROM NewSites")
    Database.execute("""
        INSERT INTO readings SELECT * FROM NewReadings
        ON CONFLICT (site_code, species_code, measured_at) DO UPDATE SET value = excluded.value
    """)
    After = Database.execute("SELECT count(*) FROM readings").fetchone()[0]
    Database.execute("INSERT INTO runs VALUES (?, ?, ?, ?)", [datetime.now(), DaysBack, After - Before, After])
    Database.execute("COMMIT")
    return After - Before


# ---- The pipeline: extract -> shape -> load ---------------------------------------------------

def Main(DaysBack=DAYS_BACK):
    End = date.today() + timedelta(days=1)                       # the API excludes EndDate, so this includes today
    Start = End - timedelta(days=DaysBack)
    Sites = ShapeSites(GetSites(GROUP))
    Readings = ShapeReadings(pandas.concat([GetReadings(Site, SPECIES, Start, End) for Site in SITES],
                                           ignore_index=True))
    with duckdb.connect(DATABASE) as Database:
        NewRows = Save(Database, Sites, Readings, DaysBack)
    print(f"Fetched {Start} to {End} (exclusive): {len(Readings)} hours, {NewRows} of them new.")
    return NewRows


if __name__ == "__main__":
    Main()
