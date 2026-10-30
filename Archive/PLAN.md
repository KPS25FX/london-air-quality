# Plan (restart, 30 Oct 2026)


## Stages

| # | Stage | When | Output (in `DESIGN.md`) |
|---|---|---|---|
| 1 | **Survey** the endpoints for sites, pollutants and readings (the brief's scope) | Fri 30 | **Table A:** endpoint × dimensions. **The question model:** Q = f({r ∈ Readings : filter(r)} grouped by g) |
| 2 | **Collect:** target tables, plus a minimal pipeline (extract, upsert, 7-day re-fetch), scheduled 4× a day | **Sat 31, morning** | **The target tables.** Starts the history clock |
| 3 | **Domain facts** and the claims they imply | Sat 31 | **Table B:** facts (statement, source, kind). **Table C:** derived claims (which facts chain to each) |
| 4 | **Answerability:** can the data answer each claim? | Sat 31 – Sun 1 | **Table D:** criteria (dimensions, coverage, matched comparison, repeats, effect vs noise, period), plus a verdict for each claim |
| 5 | **Correctness:** what "correct" means for the tables | Sun 1 | **Table E:** properties (name, definition, check query). Becomes `CHECKS` in the pipeline, one row = one check |
| 6 | **Use and write-up:** answer the answerable claims, README under the brief's headings, test a fresh clone, submit | Mon 2 | The analysis notebook and README |

**Why stage 2 comes before 3–5:** the history needs days of runs, so a minimal pipeline must be running by Saturday
morning. Stages 3–5 refine the design and add checks. They don't block collection.


## The system diagram (to be filled in as the stages complete)

```
API endpoints (Table A) → pipeline functions → database tables → checks (Table E)
                                                               → questions (Table C, filtered by Table D) → README
```
