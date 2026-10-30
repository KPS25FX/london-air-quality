-- Cleaning keeps every raw row, and the only values that become NULL are the ones that were "" in raw.
-- Returns one row describing the problem if either is false.
with counts as (
    select (select count(*) from {{ source('raw', 'readings') }})                       as raw_rows,
           (select count(*) from {{ ref('readings') }})                                 as clean_rows,
           (select count(*) from {{ source('raw', 'readings') }} where value = '')      as raw_blanks,
           (select count(*) from {{ ref('readings') }} where value is null)             as clean_nulls
)
select * from counts
where raw_rows <> clean_rows or raw_blanks <> clean_nulls
