create table profiles (id uuid primary key references auth.users, email text, role text default 'member');
create table projects (id uuid primary key default gen_random_uuid(), name text, owner_id uuid references auth.users);
create table project_members (project_id uuid references projects, user_id uuid references auth.users);
create table tasks (id uuid primary key default gen_random_uuid(), project_id uuid references projects, title text, created_by uuid);

alter table profiles enable row level security;
alter table projects enable row level security;
alter table project_members enable row level security;
alter table tasks enable row level security;

create policy "own profile" on profiles for select using (auth.uid() = id);
create policy "own projects" on projects for all using (auth.uid() = owner_id);
create policy "member rows" on project_members for select using (auth.uid() = user_id);
create policy "member tasks" on tasks for all using (
  exists (select 1 from project_members m where m.project_id = tasks.project_id and m.user_id = auth.uid())
);
