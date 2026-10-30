-- Hourly data: every timestamp is exactly on the hour.
select * from {{ ref('readings') }}
where measured_at <> date_trunc('hour', measured_at)
