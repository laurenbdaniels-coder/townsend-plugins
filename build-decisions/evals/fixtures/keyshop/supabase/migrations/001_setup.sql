create table notes (id uuid primary key, owner_id uuid not null, body text);
alter table notes enable row level security;
create policy "owners read notes" on notes for select using (owner_id = auth.uid());

create or replace function purge_note_files(note uuid) returns void language plpgsql security definer as $$
declare
  service_role_key text := '__SERVICE_KEY__';
begin
  perform 1;
end $$;
