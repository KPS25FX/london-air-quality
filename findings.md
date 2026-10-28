# Findings

What we have learned about the API, and how sure we are of each point.
A finding is a **fact** (seen in the data), an **inference** (reasoned, not yet checked) or a **judgment** (opinion).

## The endpoint list

- Source: https://api.erg.ic.ac.uk/AirQuality/help, a page the server generates from its own code (WCF).
  There is no OpenAPI or WSDL spec (both return 404).
- The page has one table: `Uri`, `Method`, `Description`. 70 rows. **Fact.**
- 36 rows end in `/Json`. The other 34 are 30 XML twins of JSON endpoints, 2 CSV exports and 2 PDFs
  (`/Information/Documentation/pdf`, `/Information/Terms/pdf`). **Fact.**
- 6 JSON endpoints have no XML twin (`Annualiser/...`, `DiffusionTube`, `Data/Traffic`, two `Data/SiteSpecies...`). **Fact.**
- **Assumption:** the JSON endpoints cover all the data; the dropped rows are duplicates or documents.
  The documentation PDF is still worth reading.

## Level 0 (no parameters)

Callable with nothing known:

```
/Hourly/Map/Json                     list of hourly maps + metadata (not readings)
/Information/AirPollutionGuide/Json
/Information/Groups/Json             "for use with other calls"
/Information/IndexHealthAdvice/Json
/Information/Objective/Json
/Information/Species/Json            6 species: CO, NO2, O3, PM10, PM2.5, SO2
```

## Information/Groups

- Shape: `["Groups"]["Group"]` → list of dicts with `@GroupName`, `@Description`, `@WebsiteURL`. **Fact.**
  The double wrapper and `@` prefixes come from an XML → JSON conversion. **Inference.**
- Produces `@GroupName`, which is the `{GroupName}` parameter of 8 endpoints. **Fact** (name match);
  a working call will confirm it.
- Groups overlap: `All` ⊇ `London` ⊇ `camden`, and single boroughs are groups too.
  Groups are lenses on the same local authorities, not a hierarchy, so never total across groups. **Inference.**
- For a London angle, `London` ("All currently active boroughs of London") is the group to use. **Judgment.**
- What a group contains is answered by `/Information/MonitoringLocalAuthority/GroupName={GroupName}/Json`.

### Data quality

| Finding | Certainty | How to settle it |
|---|---|---|
| `almbridget` is labelled "Elmbridge", `runnymeade` is labelled "Runnymede" | Fact | — |
| Use the ID as given, not the corrected spelling | Inference | Call `MonitoringLocalAuthority` with both spellings |
| `singlela` ("sub domain test"), `CambridgeCity`, `Cambridgeshire` ("Demo group for tender") are suspect | Judgment | Call them: do they return any sites? |
| Missing values are empty strings (`"@WebsiteURL": ""`) | Fact | Parse `""` to `None` at the boundary |

## Level 0 responses (checked 2026-10-28)

| Endpoint | Status | Fields that match a parameter name |
|---|---|---|
| `Information/Groups` | OK | `@GroupName` |
| `Information/Species` | OK | `@SpeciesCode`, `@SpeciesName` |
| `Hourly/Map` | OK | `@SpeciesCode`, `@SpeciesName` (also `@StartDate`, `@EndDate`) |
| `Information/AirPollutionGuide` | OK | none (guide articles) |
| `Information/IndexHealthAdvice` | **HTTP 400**, HTML "Request Error" page | — |
| `Information/Objective` | **HTTP 400**, HTML "Request Error" page | — |

- Two documented endpoints are broken. **Fact.** `fetch` must treat a non-JSON / error response as a failure, not data.
- The error pages start with a UTF-8 BOM, which is why parsing them as JSON fails with a BOM error rather than a clear "not JSON". **Fact.**
- `SiteCode` and `LocalAuthorityId` come from no Level 0 endpoint; they need a `GroupName` first (Level 1). **Inference**, to confirm by calling.
