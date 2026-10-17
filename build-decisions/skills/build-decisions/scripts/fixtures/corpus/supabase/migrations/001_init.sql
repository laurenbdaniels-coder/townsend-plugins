create table docs (id uuid primary key, owner_id uuid not null, body text);
alter table docs enable row level security;
create policy "owner reads" on docs for select using (auth.uid() = owner_id);

create view invoice_totals as
select id, ROUND(total, 2) as total from invoices;
