# London's air, on repeat: NO₂ beside a main road

## What I built and who for

**Audience:** people who walk, cycle or wait for buses along central London's main roads, and the people who
advise them.

**Question:** how much worse is the air right beside a busy road than nearby, and at what time of day?

**What I built:**

1. **An exploration of the API** ([Presentation.ipynb](Presentation.ipynb)). It starts from the API's help page and
   finds, by a rule, which endpoint gives the values another endpoint needs, until it reaches the hourly readings.
   Along the way it names the API's quirks and handles each one in one place.
2. **A pipeline** ([pipeline.py](pipeline.py)) that fetches the last 7 days of hourly NO₂ for two sites into DuckDB.
   Every run adds new hours, updates hours already stored, never duplicates, records any value that changed, and logs
   itself. It uses the notebook's rules and checks, and stops with an error rather than store a request that silently
   returned nothing.
3. **A comparison of the two sites** (end of [Presentation.ipynb](Presentation.ipynb)):
   - **Marylebone Road (MY1):** kerbside
   - **Station Walk (GT1):** urban background

   Both site types come from the API's site list, joined to the readings in SQL.

**Headline (17 Oct – 2 Nov 2026):** beside Marylebone Road, NO₂ averaged **3.6×** the background level, over the 320
hours when both sites had a reading. The gap is largest in the evening rush hour, at **17:00 GMT** (60.4 against
16.5 µg/m³), with a second peak in the morning rush hour.

![Mean NO₂ by hour of day](no2_by_hour.png)

## The data

The [London Air Quality Network API](https://api.erg.ic.ac.uk/AirQuality/help), run by the Environmental Research
Group. Readings are hourly, in µg/m³: the API's `Data/Wide/Site` endpoint labels its NO₂ column
"Nitrogen Dioxide (ug/m3)".

A reading the API doesn't have yet comes back as an empty string (`""`). The pipeline stores it as missing (NULL), and
a later run fills it in when the value arrives.

Everything unexpected we found about how the API behaves, and what the code does about each, is in
[Mess.md](Mess.md).

## How it works

Each box is a table and each arrow is the code that makes the next one. The notebook finds the path through the API.
`pipeline.py` repeats the last part of that path on every run.

```mermaid
flowchart TD
    subgraph Explore["Exploration · Presentation.ipynb"]
        Help["API help page<br/>api.erg.ic.ac.uk/AirQuality/help"]
        HelpTable["HelpTable · 70 rows<br/>Uri, Method, Description"]
        Json["JsonEndpoints · 36 Endpoints<br/>ParametersOf: Endpoint → set of parameter names"]
        Groups["GroupsTable · 69 rows<br/>GroupName, Description, …"]
        Species["SpeciesTable · 6 rows<br/>SpeciesCode, SpeciesName, …"]
        Sites["SitesTable · 258 rows<br/>SiteCode, SiteName, SiteType, …"]
        Pairs["SiteSpeciesTable · 650 rows<br/>ValidPairs: the 646 (site, species) pairs the API lists"]
    end

    subgraph Pipeline["Pipeline · pipeline.py"]
        Readings["Readings DataFrame · up to 168 rows per site per week<br/>SiteCode, SpeciesCode, MeasurementDateGMT, Value"]
        DBSites[("sites · DuckDB<br/>the London site list, refreshed every run")]
        DBReadings[("readings · DuckDB<br/>one row per site, species and hour")]
        DBChanges[("changes · DuckDB<br/>RunAt, the hour, OldValue, NewValue")]
        DBRuns[("runs · DuckDB<br/>one row per run")]
    end

    subgraph Use["Comparison · end of Presentation.ipynb"]
        Stats["Kerbside against background<br/>overall, and by hour of day + chart"]
    end

    Help -- "pandas.read_html" --> HelpTable
    HelpTable -- "Endpoint type<br/>keep URIs ending /Json" --> Json
    Json -- "nothing known yet<br/>GetTable · Information/Groups" --> Groups
    Json -- "GetTable · Information/Species" --> Species
    Groups -- "reveals GroupName = London<br/>GetTable · Information/MonitoringSites" --> Sites
    Groups -- "GroupName = London<br/>Information/MonitoringSiteSpecies" --> Pairs
    Sites -- "reveals SiteCode = MY1, GT1" --> Readings
    Species -- "reveals SpeciesCode = NO2<br/>GetReadings · Data/SiteSpecies" --> Readings
    Pairs -- "each pair must be listed" --> Readings
    Sites -- "the same list, each run" --> DBSites
    Readings -- "SaveReadings: insert new hours,<br/>update existing ones" --> DBReadings
    Readings -- "SaveReadings: value differs<br/>from what was stored" --> DBChanges
    Readings -- "hours fetched, hours new" --> DBRuns
    DBReadings -- "SQL, joined to sites" --> Stats
    DBSites --> Stats
```

### Where each step of the brief happens

| Step | Where | How |
|---|---|---|
| **Extract:** how the endpoints connect | [Presentation.ipynb](Presentation.ipynb) | The help page becomes a table of endpoints, and `ParametersOf` reads the parameters each one needs. Discovery then starts knowing nothing: call every endpoint whose parameters are all known (`CallableWith`), and see which parameters each reply gives values for (`Reveals`: a column named like a parameter). Repeat. Two rounds reach the readings: Groups gives GroupName, MonitoringSites gives SiteCode, Species gives SpeciesCode, and those three unlock `Data/SiteSpecies`. |
| **Collect history** | `pipeline.py`: `SaveReadings` | The `readings` table's primary key is site + species + hour, so each hour is stored once. A new hour is inserted. An hour we already have is updated (`ON CONFLICT … DO UPDATE`), which picks up late and corrected values. Before updating, any value that differs is written to `changes` with its old and new value. Each run re-fetches the last 7 days and adds a row to `runs`. |
| **Shape** | `Clean`, and the `readings` and `sites` tables | `Clean` removes the API's `@` from field names, so a field and the parameter it fills have one name, and turns `""` into a real missing value (NULL). The table's column types turn text into a timestamp and a number. The primary key says what one row is: one site, one species, one hour, and its value. `sites` joins to `readings` on `SiteCode`. |
| **Use** | end of [Presentation.ipynb](Presentation.ipynb) | Mean NO₂ at the kerbside and background sites over the hours where both have a value, overall and by hour of day. |

### Guarding against bad data

The API answers 200 with every value empty for a site that doesn't exist, for a pollutant a site doesn't measure, and
for one it has stopped measuring. None of these is an error, so nothing fails unless we check. A request passes
through several boundaries, and each could hold a check. Each line below is one boundary, the braces hold the
options, and ✓ marks what I chose:

```
Parameters     { nothing | format check | site is an open London site | (site, species) ∈ ValidPairs ✓ | dates within Started–Finished }
      ↓
The call       { catch everything | catch HTTPError and log it ✓ exploring | let it raise ✓ | retry }
      ↓
Reply content  { trust it | no values at all → raise ✓ | a threshold on % missing | a Pydantic model of the reply }
      ↓
Storage        { column types ✓ | primary key ✓ | CHECK constraints }
      ↓
Across runs    { upsert and a changes table ✓ | a runs log ✓ | last measured hour per site ✓ }
```

It takes two checks, because each catches what the other can't. Checking the request stops a site or pair the API
doesn't list, before the call. But listed doesn't mean it has data: Marylebone Road stopped measuring PM10 in 2019,
and has had no CO since 30 Oct 2026, though CO is still listed with no end date. Only checking the reply catches
those.

The API's other quirks each live in one named place. A quirk with a pattern becomes a rule: `Records` finds the
records in any reply, `AsList` handles a list of one coming back as a single object, and `Clean` handles `@` names and
`""` values. Where there is no pattern, the knowledge is written down as data: `RecordPaths` states where the records
are for the endpoints the pipeline relies on, and the notebook checks it against the live API. The notebook explores
with the rule; the pipeline follows the stated paths.

### Running it again

Running the pipeline twice in a row adds nothing the second time. Each run is logged in `runs`, and the
first real runs were on 1 and 2 Nov 2026. The week before that was loaded by replaying past dates, in my first
notebook (kept in the git history): it moved the end date forward one day at a time, starting a week back. The first
run added 336 hours (2 sites × 7 days × 24 hours). Each run after that added 48 (1 new day × 24 hours × 2 sites) and
left the rest as they were.

A replay uses today's version of past data, so it can't show a late value arriving. Real runs a few hours apart do:
the most recent hours are often empty at first and filled in later, and those show up in `changes`.

## How to run it

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python pipeline.py                                       # each run: fetch the last 7 days and save
```

Then open [Presentation.ipynb](Presentation.ipynb) and run it from the top: the exploration, the checks, and then the
history and the comparison, read from `air.duckdb`. The notebook only reads the database, and closes it at the end.
DuckDB lets only one program write to `air.duckdb` at a time, so close any open connection before running
`pipeline.py`.

## What I would do next

- **Measure how far back values change.** The pipeline assumes nothing older than 7 days changes. Re-fetching an
  older month and comparing it with what was stored would turn that assumption into a measured number.
- **Define the rules once.** The notebook defines `Get`, `AsList`, `Follow` and `Clean` as it discovers them, and
  `pipeline.py` repeats them. A small module both import would keep them from drifting apart.
- **A schedule (cron) instead of running it by hand,** and a visual, interactive version of the pipeline diagram.
- **More road / background pairs, and other pollutants,** to test whether the pattern holds across London.

## Where AI helped

I used claude code to find libraries that may help shorten the code and bounced ideas off claude in order to find a minimal and clean solution to problems - I also used claude to do a literature review when faced with certain tricky problems , such as finding a way to standardise/formalise certain pieces of mess ( such as alias and naming issues in the api ) - Sometimes I would have a fancy idea about implementing a certain library or piece of maths in the code, and i would use claude to prototype it - however virtually none of those ideas were kept because they were overly verbose and overkill for such a pipeline - Claude also helped me anticipate errors and i discussed with claude ideas such as what happens when a request is perfectly valid but means nothing. I noticed my own exploration code caught the one error we expected and printed "answers" for everything else, so anything that went wrong in a different way would just get painted over. I checked, and the API answers a site paired with a pollutant it doesn't measure with a 200 and a page of empty values, which is the worst kind of failure because nothing breaks. The way I ended up thinking about it is standing outside a forest - some things you can see and check from the outside before you go in, and some you only find by walking through. That became the three kinds of knowing at the end of [Mess.md](Mess.md), and the two checks in the pipeline: one on the request before the call (only pairs the API itself lists), and one on the reply (a reply with no values at all is an error, not data). I also wanted to show that at every point where a check could go there was a range of options, not one obvious answer, which is the diagram under "Guarding against bad data".

It wasn't a straight line. My first idea, on 27 Oct, was to treat the API's help page as the source of truth - read it into a table, pull each endpoint's parameters out of its URL, start from the endpoints that take no parameters because they have to be what feeds everything else, and then keep calling whatever I now had the parameters for. Claude told me that was a dependency graph and warned me that building all of it automatically was a trap. It was right that I'd over-build - over the next two days it turned into a crawler of the whole API with a huge generated map that I really liked but couldn't explain. On the night of 28 Oct I panicked about the deadline and asked Claude to just build the whole pipeline in one message. The next morning I deleted everything I hadn't written myself, because I couldn't stand behind it, and on 30 Oct I archived the lot and started again by hand - help page, table, one call at a time, look at the actual JSON, then the next call. I'd realised my downfall was trying to make things automatic before I'd done them once by hand. The core idea did survive though, just much smaller - the notebook still starts knowing nothing and finds by a rule which endpoint unlocks the next (`Known`, `CallableWith`, `Reveals`). It just only got written down as a rule after I'd seen it work.

The thing I'm proudest of isn't really about NO₂, it's a habit: only act on what you've actually found out. When Claude told me Marylebone Road was a kerbside site, I asked where that came from - if something only comes from Claude, that's a problem - so the site types now come from the API's own site list, joined in SQL. When it told me something about the monitoring sites before my notebook had called that endpoint, I stopped it, because the notebook should only know what it has discovered so far. I was a bit fixated on chronology - using only what it would be reasonable to know at each step to work out the next one - and that's why the notebook reads top to bottom as a discovery. The same thing decided my angle. You need to know what's in the data to ask a good question, and you need a question to know which data to look at, so it's circular - and picking the angle first felt like an uninformed choice I'd then have to force the data to support. So I explored first, and the kerbside against background comparison came out of what the API actually has.

I didn't always agree with Claude either. Early on it argued for re-parsing each endpoint's parameters inside a function, when I'd already parsed them once into a column of the table. I thought that was doing the same work twice, so I took the argument to a separate Claude chat with the full context to find out which of us was wrong, and it sided with me - parse once at the boundary and trust the result. A lot of the smaller decisions came from pushing on things like that rather than just accepting them - keeping the API's own names instead of renaming them, because every rename is another place for things to drift apart; working through why the value can't be part of the primary key (it's the thing that changes, so every correction would become a duplicate row); and putting the mess in one named place (`AsList`, `Clean`, `RecordPaths`) instead of scattering fixes everywhere. I also caught a hole in my own plan for history. I'd decided to show the pipeline over time by replaying past dates, moving the end date forward a day at a time, and then realised a replay uses today's version of the past, so it can never show a late value turning up. That's why there are also real runs from 1 and 2 Nov.

Where Claude did more than advise, I want to be upfront. Early on I typed nearly everything myself and asked for syntax - I'd explain the code back in my own words until I had it right, and that became the comment, which is how I learnt masks, the `.str` accessor, generators, `lambda` and `.apply`, and how `ON CONFLICT` works. It also showed me things I didn't know existed, like `pandas.read_html` turning the help page into a table in one line. A lot of the probing of the live API was Claude, and many of the quirks in Mess.md came out of those calls, though what each one meant for the code was a conversation - and I asked how someone without AI would have found each one, because a finding I can't reproduce isn't one I can defend. In the last two days, under time pressure, Claude wrote more of the code than at the start - the final notebook was rebuilt from my outline, and it implemented the reply checks, `RecordPaths` and the `changes` table to designs we'd agreed. I read through all of it, questioned anything I couldn't explain, and had things renamed until the input and output of every step was visible. It also wrote most of the prose in this README and Mess.md from my notes, which I then edited.

The biggest thing I took from it is that a language model can write the code, but you still have to know what you want, otherwise you're at the mercy of whatever it decides is "best". Doing things by hand is what gives you that - once you know what the tools can do, you can direct the AI instead of just watching it. It doesn't mean doing less work, it means doing the work faster and spending it on decisions instead of memorising syntax. This took longer than it needed to because I kept trying to build the general version before the simple one, but what's here is something I understand, and I can explain every decision in it.

---

Data: London Air Quality Network, Environmental Research Group ([londonair.org.uk](https://www.londonair.org.uk)),
used under the API's terms and conditions.
