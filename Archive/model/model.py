"""The London Air API, written as definitions. Read top to bottom like a proof:

    1. Rules        how the API's mess is turned into something regular (each written once)
    2. Definitions  what each endpoint returns: its structure, types and meaning
    3. Endpoints    a URL in, a definition out
    4. Chain        how one endpoint feeds the next:

        Sites endpoint ──► list[Site] ──► chosen site codes ──┐
                                                              ├──► Readings endpoint ──► list[Readings]
        chosen species and dates ─────────────────────────────┘

Run (from the project root):  .venv/bin/python model/model.py
"""

import json
import urllib.request
from datetime import date, datetime, timedelta
from typing import Annotated

import pandas
from pydantic import AfterValidator, AliasPath, BaseModel, BeforeValidator, Field


# ---- 1. Rules: each quirk of the API, named once and attached to any field it affects -----------

# One item comes back as a dict, several as a list, none as nothing -> always a list.
AlwaysList = BeforeValidator(lambda v: [] if v is None else v if isinstance(v, list) else [v])

# The API sends "" for "no value" -> None.
BlankIsNone = BeforeValidator(lambda v: None if v == "" else v)

# One site split over several entries, each holding some of its species (HS1, HS5) -> one site, species combined.
# The site's other details must agree across the entries; if they don't, that's an error rather than picking one.
def MergeSplitSites(Sites):
    Merged = {}
    for Site in Sites:
        First = Merged.setdefault(Site.code, Site)
        if First is not Site:
            if First.model_dump(exclude={"species"}) != Site.model_dump(exclude={"species"}):
                raise ValueError(f"entries for {Site.code} disagree")
            First.species += Site.species
    return list(Merged.values())

OneEntryPerSite = AfterValidator(MergeSplitSites)


# ---- 2. Definitions: what each endpoint returns ---------------------------------------------------
# Each line reads: field name, its type (after the rules are applied), and where it comes from in the JSON.

class Species(BaseModel):                       # a pollutant measured at a site
    code:     str                                       = Field(alias="@SpeciesCode")
    name:     str                                       = Field(alias="@SpeciesDescription")
    started:  datetime                                  = Field(alias="@DateMeasurementStarted")
    finished: Annotated[datetime | None, BlankIsNone]   = Field(alias="@DateMeasurementFinished")  # None = still measured

class Site(BaseModel):                          # a monitoring site
    code:      str                                      = Field(alias="@SiteCode")
    name:      str                                      = Field(alias="@SiteName")
    type:      str                                      = Field(alias="@SiteType")                 # Kerbside, Roadside, ...
    latitude:  float                                    = Field(alias="@Latitude")
    longitude: float                                    = Field(alias="@Longitude")
    opened:    datetime                                 = Field(alias="@DateOpened")
    closed:    Annotated[datetime | None, BlankIsNone]  = Field(alias="@DateClosed")               # None = still open
    species:   Annotated[list[Species], AlwaysList]     = Field(alias="Species", default=[])

class SiteList(BaseModel):                      # the whole sites response: {"Sites": {"Site": [...]}}
    sites: Annotated[list[Site], AlwaysList, OneEntryPerSite] = Field(validation_alias=AliasPath("Sites", "Site"))

class Hour(BaseModel):                          # one hourly measurement
    time:  datetime                                     = Field(alias="@MeasurementDateGMT")       # start of the hour, GMT
    value: Annotated[float | None, BlankIsNone]         = Field(alias="@Value")                    # None = no valid reading (yet)

class Readings(BaseModel):                      # the whole readings response: {"RawAQData": {..., "Data": [...]}}
    site:    str                                        = Field(validation_alias=AliasPath("RawAQData", "@SiteCode"))
    species: str                                        = Field(validation_alias=AliasPath("RawAQData", "@SpeciesCode"))
    hours:   Annotated[list[Hour], AlwaysList]          = Field(validation_alias=AliasPath("RawAQData", "Data"), default=[])


# ---- 3. Endpoints: a URL in, a definition out ------------------------------------------------------

API = "https://api.erg.ic.ac.uk/AirQuality"

def Fetch(Path):
    with urllib.request.urlopen(API + Path, timeout=60) as Response:
        return json.loads(Response.read())

def GetSites(Group) -> list[Site]:
    return SiteList.model_validate(Fetch(f"/Information/MonitoringSiteSpecies/GroupName={Group}/Json")).sites

def GetReadings(SiteCode, SpeciesCode, Start, End) -> Readings:
    return Readings.model_validate(Fetch(f"/Data/SiteSpecies/SiteCode={SiteCode}/SpeciesCode={SpeciesCode}"
                                         f"/StartDate={Start}/EndDate={End}/Json"))


# ---- 4. Chain: sites -> chosen codes -> readings ---------------------------------------------------

GROUP, SITES, SPECIES, DAYS_BACK = "London", ["MY1", "GT1"], "NO2", 7

def Chain(Group=GROUP, 
          SiteCodes=SITES, 
          SpeciesCode=SPECIES, 
          DaysBack=DAYS_BACK):

    
    End = date.today() + timedelta(days=1)                       # the API excludes EndDate, so this includes today
    Start = End - timedelta(days=DaysBack)
    Sites = {Site.code: Site for Site in GetSites(Group)}


    
    for Code in SiteCodes:                                       # the link between the endpoints: checked, not assumed
        assert Code in Sites, f"{Code} is not a {Group} site"
        assert SpeciesCode in [S.code for S in Sites[Code].species], f"{Code} does not measure {SpeciesCode}"
    return list(Sites.values()), [GetReadings(Code, SpeciesCode, Start, End) for Code in SiteCodes]


def Table(Items):
    """Any list of definitions -> a pandas table: one row per item, one column per field."""
    return pandas.DataFrame([Item.model_dump() for Item in Items])


if __name__ == "__main__":
    Sites, AllReadings = Chain()
    print(f"{len(Sites)} sites\n", Table(Sites).drop(columns="species").head(3), "\n")
    for R in AllReadings:
        print(f"{R.site} {R.species}: {len(R.hours)} hours\n", Table(R.hours).head(3), "\n")
