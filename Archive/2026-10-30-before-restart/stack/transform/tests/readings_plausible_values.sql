-- NO2 can't really be negative, and London hourly values are far below 1000 µg/m³.
-- Warn, don't fail: GT1 reports small negatives (down to about -1.6) on clean nights. That's analyser noise around
-- zero, also present in the original pipeline. Whether to keep, zero or drop them is an analysis decision.
{{ config(severity='warn') }}
select * from {{ ref('readings') }}
where value < 0 or value > 1000
