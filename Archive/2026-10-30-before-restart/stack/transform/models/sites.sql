-- raw.sites -> clean.sites. Same rules: CAST fails loudly, "" -> NULL.
-- DISTINCT: the API splits HS1 and HS5 over several entries, one per group of species. load.py drops Species, so
-- the rows left are identical. If two rows for one site ever differ, DISTINCT keeps both and the unique test on
-- site_code fails, so we'd find out rather than pick one silently.
select distinct
    site_code,
    site_name,
    site_type,
    cast(latitude as double)                       as latitude,
    cast(longitude as double)                      as longitude,
    cast(nullif(date_opened, '') as timestamp)     as date_opened,
    cast(nullif(date_closed, '') as timestamp)     as date_closed     -- NULL = still open
from {{ source('raw', 'sites') }}
