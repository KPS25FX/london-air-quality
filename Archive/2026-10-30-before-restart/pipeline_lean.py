"""Lean version of pipeline.py: land the API's JSON untouched, then clean it with SQL.

    API  ->  raw          (every response, exactly as received; only ever appended to)
         ->  sites,       (views: SQL that turns raw JSON into clean, typed tables,
             readings      recalculated every time you query them)

Run:  python pipeline_lean.py
"""

import urllib.request
from datetime import date, timedelta

import duckdb

API = "https://api.erg.ic.ac.uk/AirQuality"
DATABASE = "air_lean.duckdb"
SITES, SPECIES, DAYS_BACK = ["MY1", "GT1"], "NO2", 7


# ---- 1. Land: the only Python that touches the API --------------------------------------------

RAW = """
CREATE TABLE IF NOT EXISTS raw (
    kind       VARCHAR,     -- 'sites' or 'readings'
    path       VARCHAR,     -- which API call
    fetched_at TIMESTAMP,
    body       JSON         -- the response, untouched
)"""

def Fetch(Path):
    with urllib.request.urlopen(API + Path, timeout=60) as Response:
        return Response.read().decode()


# ---- 2. Clean: all the API's mess is handled here, once ---------------------------------------
#   as_list:  one item comes back as an object, several as an array, none as nothing -> always an array
#   NULLIF:   the API sends "" for "no reading" -> NULL
#   QUALIFY:  each hour may have been fetched many times -> keep the latest fetch

CLEAN = """
CREATE OR REPLACE MACRO as_list(j) AS
    CASE WHEN j IS NULL THEN '[]'::JSON WHEN json_type(j) = 'ARRAY' THEN j ELSE json_array(j) END;

CREATE OR REPLACE VIEW sites AS
SELECT s->>'@SiteCode'                                  AS site_code,
       s->>'@SiteName'                                  AS site_name,
       s->>'@SiteType'                                  AS site_type,
       CAST(s->>'@Latitude'  AS DOUBLE)                 AS latitude,
       CAST(s->>'@Longitude' AS DOUBLE)                 AS longitude,
       CAST(NULLIF(s->>'@DateClosed', '') AS TIMESTAMP) AS date_closed     -- NULL = still open
FROM (SELECT body FROM raw WHERE kind = 'sites' ORDER BY fetched_at DESC LIMIT 1),
     UNNEST(CAST(as_list(body->'$.Sites.Site') AS JSON[])) AS t(s);

CREATE OR REPLACE VIEW readings AS
SELECT body->>'$.RawAQData.@SiteCode'                   AS site_code,
       body->>'$.RawAQData.@SpeciesCode'                AS species_code,
       CAST(h->>'@MeasurementDateGMT' AS TIMESTAMP)     AS measured_at,     -- start of the hour, GMT
       CAST(NULLIF(h->>'@Value', '') AS DOUBLE)         AS value            -- NULL = no valid reading (yet)
FROM raw, UNNEST(CAST(as_list(body->'$.RawAQData.Data') AS JSON[])) AS t(h)
WHERE kind = 'readings'
QUALIFY row_number() OVER (PARTITION BY site_code, species_code, measured_at ORDER BY fetched_at DESC) = 1;
"""


# ---- 3. Run: fetch -> land -> (views are already clean) ---------------------------------------

def Main(DaysBack=DAYS_BACK):
    End = date.today() + timedelta(days=1)                       # the API excludes EndDate, so this includes today
    Start = End - timedelta(days=DaysBack)
    Calls = [("sites", "/Information/MonitoringSiteSpecies/GroupName=London/Json")] + \
            [("readings", f"/Data/SiteSpecies/SiteCode={Site}/SpeciesCode={SPECIES}/StartDate={Start}/EndDate={End}/Json")
             for Site in SITES]
    with duckdb.connect(DATABASE) as Database:
        Database.execute(RAW)
        Database.executemany("INSERT INTO raw VALUES (?, ?, now(), ?)", [(Kind, Path, Fetch(Path)) for Kind, Path in Calls])
        Database.execute(CLEAN)
        Database.sql("SELECT site_code, count(value) AS hours, round(avg(value), 1) AS mean_no2 "
                     "FROM readings GROUP BY site_code").show()


if __name__ == "__main__":
    Main()
