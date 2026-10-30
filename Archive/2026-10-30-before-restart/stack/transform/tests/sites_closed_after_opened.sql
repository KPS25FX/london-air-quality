-- A site can't close before it opened.
select * from {{ ref('sites') }}
where date_closed < date_opened
