-- No hour is stored twice for the same site and pollutant.
select site_code, species_code, measured_at, count(*) as copies
from {{ ref('readings') }}
group by all
having count(*) > 1
