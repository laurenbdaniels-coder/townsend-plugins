alter table public.profiles disable row level security;
create policy "open" on public.notes for select using (true);
