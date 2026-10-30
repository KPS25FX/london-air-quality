-- raw.readings -> clean.readings. Every decision about the API's mess lives here:
--   CAST:   text -> timestamp / number. CAST (not TRY_CAST) fails loudly on text it can't read, so nothing becomes NULL silently.
--   NULLIF: "" is the API's way of saying "no valid reading" -> NULL.
select
    site_code,
    species_code,
    cast(measured_at as timestamp)    as measured_at,   -- start of the hour, GMT
    cast(nullif(value, '') as double) as value          -- µg/m³ (assumed: the API does not say); NULL = no valid reading (yet)
from {{ source('raw', 'readings') }}
