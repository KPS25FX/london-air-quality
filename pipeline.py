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

# the choices, found by exploring the API in the notebook; the dates are worked out from DAYS at the bottom
SITES = ["MY1", "GT1"]      # Marylebone Road (kerbside), Station Walk (urban background)
SPECIES = "NO2"
DAYS = 7

Database = duckdb.connect("air.duckdb")

# readings: one row per measurement. The columns come from the readings endpoint (Data/SiteSpecies): each hour in its
#   reply has @MeasurementDateGMT and @Value, and GetReadings adds SiteCode and SpeciesCode from the request.
#   The primary key is what identifies one measurement: which site, which pollutant, which hour. A site measures a
#   pollutant once per hour, so the three together are unique. The value is the measurement itself, so it isn't in
#   the key. Every run re-fetches 7 days, so each hour comes back about 7 times: the key is how the database knows
#   it's the same reading, and updates it instead of adding a second row.
# changes: about the data. One row per stored value that a later run changed, with its old and new value.
#   The API fills in empty hours later and corrects values, so this is the history of what we knew.
# runs: about the pipeline. One row per run: when, the window it asked for, Fetched = hours the API sent back,
#   New = how many of those weren't in readings yet. Example: 2 Nov 11:19 fetched 312, 32 new, and 5 rows in changes.
# IF NOT EXISTS: the first run creates the tables; every later run leaves them, and their data, as they are.
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

# the endpoints we rely on, copied from the API's help page. Each is a template: the names in braces get filled in.
SitesUri: str = "/Information/MonitoringSites/GroupName={GroupName}/Json"
SiteSpeciesUri: str = "/Information/MonitoringSiteSpecies/GroupName={GroupName}/Json"
ReadingsUri: str = "/Data/SiteSpecies/SiteCode={SiteCode}/SpeciesCode={SpeciesCode}/StartDate={StartDate}/EndDate={EndDate}/Json"

# where each endpoint keeps its records: the keys to walk down, one after another. reply["RawAQData"]["Data"] is the
# list of hours. Every endpoint wraps its records differently, so that mess is written down here, in one place.
RecordPaths: dict[str, list[str]] = {
    SitesUri:       ["Sites", "Site"],
    SiteSpeciesUri: ["Sites", "Site"],
    ReadingsUri:    ["RawAQData", "Data"],      # EndDate itself is not included
}


# Get: calls one endpoint.
#
#   Uri      a template, such as ReadingsUri
#   Values   one value for each {Name} in the Uri, as a dictionary:
#              {"SiteCode":    "MY1",
#               "SpeciesCode": "NO2",
#               "StartDate":   "2026-10-27",
#               "EndDate":     "2026-11-03"}
#   returns  the reply:  {"RawAQData": {"Data": [{"@MeasurementDateGMT": "2026-10-27 00:00:00", "@Value": "42.1"}, ...]}}
#
# Called as Get(ReadingsUri, SiteCode="MY1", ...): ** collects the named values into the dictionary, and
# Uri.format(**Values) puts each one into its {Name}. json.load turns the JSON text into dictionaries and lists.
def Get(Uri: str, **Values: str) -> dict:
    return json.load(urllib.request.urlopen("https://api.erg.ic.ac.uk/AirQuality" + Uri.format(**Values)))


# AsList: a list with one item comes back as a single dictionary, so make it a list.
#
#   Value    {...}    or  [{...}, {...}]
#   returns  [{...}]  or  [{...}, {...}]
def AsList(Value: dict | list) -> list:
    return Value if isinstance(Value, list) else [Value]


# Follow: walks down a reply to its records, one key at a time.
#
#   Reply    a reply from Get
#   Path     ["RawAQData", "Data"]
#   returns  Reply["RawAQData"]["Data"]:  [{"@MeasurementDateGMT": "2026-10-27 00:00:00", "@Value": "42.1"}, ...]
#
# Each step replaces Value with what's under the next key, starting from the root. It takes one key per level and
# skips the keys beside it (like @SiteCode next to Data). So it assumes all the records sit under one fixed path:
# if the API moved them, or split them across several keys, this fails with a KeyError or finds the wrong thing.
# That's why the notebook checks RecordPaths against the live API.
def Follow(Reply: dict, Path: list[str]) -> list[dict]:
    Value = Reply
    for Key in Path:
        Value = Value[Key]
    return AsList(Value)


# Clean: the API puts @ in front of field names and sends a missing value as "".
#
#   Table    @MeasurementDateGMT   @Value
#            2026-10-27 00:00:00   ""
#   returns  MeasurementDateGMT    Value
#            2026-10-27 00:00:00   None        (NULL in the database)
#
# Without the @, a field has the same name as the parameter it fills: @SiteCode becomes SiteCode.
def Clean(Table: pandas.DataFrame) -> pandas.DataFrame:
    return Table.rename(columns=lambda Name: Name.removeprefix("@")).replace("", None)


# GetValidPairs: which (site, pollutant) pairs the API says are real.
#
#   returns  {("MY1", "NO2"), ("GT1", "NO2"), ...}    646 pairs
#
# RecordPaths[SiteSpeciesUri] is ["Sites", "Site"], so SiteSpeciesSites is Reply["Sites"]["Site"]: a list of sites.
# Each site's Species field is a list, or one dictionary if the site measures one pollutant, so AsList fixes it.
# json_normalize then makes one row per (site, species): record_path is the list to turn into rows, and meta copies
# @SiteCode onto each row. zip pairs the SiteCode and SpeciesCode columns row by row; set drops repeats.
# A plain loop over Reply["Sites"]["Site"] and each site's Species would give the same set, more simply.
def GetValidPairs() -> set[tuple[str, str]]:
    SiteSpeciesSites = Follow(Get(SiteSpeciesUri, GroupName="London"), RecordPaths[SiteSpeciesUri])
    for site in SiteSpeciesSites:
        site["Species"] = AsList(site["Species"])
    SiteSpeciesTable = Clean(pandas.json_normalize(SiteSpeciesSites, record_path="Species", meta=["@SiteCode"]))
    return set(zip(SiteSpeciesTable["SiteCode"], SiteSpeciesTable["SpeciesCode"]))


# GetReadings: the hourly readings for one site and pollutant. Four steps: check the pair, fetch, check the reply,
# make the table.
#
#   Values   made by Python at each call, from the named values the call passes (see the bottom of the file):
#              GetReadings(SiteCode="MY1", SpeciesCode="NO2", StartDate="2026-10-27", EndDate="2026-11-03")
#              gives Values = {"SiteCode": "MY1", "SpeciesCode": "NO2", "StartDate": "2026-10-27", "EndDate": "2026-11-03"}
#   returns  one row per hour:
#              MeasurementDateGMT   Value  SiteCode  SpeciesCode  StartDate   EndDate
#              2026-10-27 00:00:00  42.1   MY1       NO2          2026-10-27  2026-11-03
#            or an error, if the pair isn't listed or the reply has no values (the API answers 200 either way)
#
# Assumes the caller passes all four values: a missing one fails with a KeyError. Writing them out as parameters,
# def GetReadings(SiteCode, SpeciesCode, StartDate, EndDate), would make that clearer.
# ValidPairs isn't passed in: Python finds it at the top level of the file, where the bottom block sets it before
# calling this. That works, but it's hidden; passing it in would be clearer.
# Values are still text here: the readings table's types make them a TIMESTAMP and a DOUBLE when they're saved.
def GetReadings(**Values: str) -> pandas.DataFrame:
    # 1. before the call: is the pair one the API lists?
    if (Values["SiteCode"],                       # the value under the SiteCode key: a string, like "MY1"
        Values["SpeciesCode"]                     # the value under the SpeciesCode key: a string, like "NO2"
        ) not in ValidPairs:                      # together a pair, ("MY1", "NO2"), which must be one of the 646
        raise ValueError(f"Not a listed pair: {Values['SiteCode']} × {Values['SpeciesCode']}")

    # 2. fetch
    Rows = Follow(Get(ReadingsUri, **Values),     # the reply for this site, pollutant and dates
                  RecordPaths[ReadingsUri])       # ["RawAQData", "Data"], so Rows is the list of hours

    # 3. after the call: listed doesn't mean it has data. In plain words: if no hour has a value, stop.
    if not any(row["@Value"] != ""                # True if this hour has a value ("42.1"), False if it's ""
               for row in Rows):                  # ...for every hour; any(...) is True if at least one is True
        raise ValueError(f"No values: {Values['SiteCode']} × {Values['SpeciesCode']}, {Values['StartDate']} to {Values['EndDate']}")

    # 4. make the table
    return (Clean(pandas.json_normalize(Rows))    # json_normalize: one row per hour, columns @MeasurementDateGMT, @Value
                                                  # Clean: removes the @, turns "" into None
            .assign(**Values))                    # one column per key in Values, the same value on every row:
                                                  # SiteCode, SpeciesCode, StartDate, EndDate


# SaveReadings: records what changed, then inserts or updates.
#
#   Readings  the table from GetReadings, both sites (about 320 rows)
#   returns   nothing; it writes to the database
#
# register lets the SQL use the DataFrame as a table called new_readings.
def SaveReadings(Readings: pandas.DataFrame) -> None:
    Database.register("new_readings", Readings)

    # 1. record any hour whose value is different from what we stored
    #    n is the new rows, r is the stored rows. JOIN ... USING pairs them on the key, so only hours we already have
    #    take part. WHERE keeps the ones whose value differs. IS DISTINCT FROM counts NULL → 42.1 as a difference,
    #    which != doesn't. The ? is filled with datetime.now(), the run's time.
    Database.execute("""
    INSERT INTO changes
    SELECT ?, SiteCode, SpeciesCode, MeasurementDateGMT, r.Value, CAST(n.Value AS DOUBLE)
    FROM new_readings n JOIN readings r USING (SiteCode, SpeciesCode, MeasurementDateGMT)
    WHERE r.Value IS DISTINCT FROM CAST(n.Value AS DOUBLE)
    """, [datetime.now()])

    # 2. add new hours, overwrite existing ones
    #    Every new row is inserted. If its key is already in readings, that's a conflict, and instead of failing it
    #    updates the stored Value. excluded is the row we tried to insert, so excluded.Value is the new value.
    Database.execute("""
    INSERT INTO readings
    SELECT SiteCode, SpeciesCode, MeasurementDateGMT, Value
    FROM new_readings
    ON CONFLICT (SiteCode, SpeciesCode, MeasurementDateGMT) DO UPDATE SET Value = excluded.Value
    """)


if __name__ == "__main__":
    # the London site list (258 rows: SiteCode, SiteName, SiteType, ...), replaced on every run because it changes
    SitesTable = Clean(pandas.json_normalize(Follow(Get(SitesUri, GroupName="London"), RecordPaths[SitesUri])))
    Database.execute("CREATE OR REPLACE TABLE sites AS SELECT * FROM SitesTable")   # DuckDB finds the DataFrame by its name
    ValidPairs = GetValidPairs()

    EndDate = date.today() + timedelta(days=1)          # EndDate is excluded, so this includes today
    StartDate = EndDate - timedelta(days=DAYS)
    # one table per site, stacked into one: about 2 sites × 7 days × 24 hours
    Readings = pandas.concat([GetReadings(SiteCode=SiteCode, SpeciesCode=SPECIES, StartDate=str(StartDate), EndDate=str(EndDate))
                              for SiteCode in SITES], ignore_index=True)
    # New = how many rows readings gained, so it counts hours we didn't have before
    Before = Database.execute("SELECT count(*) FROM readings").fetchall()[0][0]
    SaveReadings(Readings)
    After = Database.execute("SELECT count(*) FROM readings").fetchall()[0][0]
    # one row in runs: [RunAt, StartDate, EndDate, Fetched, New]; each ? is filled from the list, in order
    Database.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?)", [datetime.now(), StartDate, EndDate, len(Readings), After - Before])
    print(f"{StartDate} to {EndDate}: fetched {len(Readings)} hours, {After - Before} new.")

    # a site can stop measuring without the site list saying so
    # the latest hour with a real value, per site and pollutant
    Database.sql("""
    SELECT SiteCode, SpeciesCode, max(MeasurementDateGMT) AS LastMeasured
    FROM readings WHERE Value IS NOT NULL
    GROUP BY SiteCode, SpeciesCode
    """).show()
