create table public.profiles (
  id uuid primary key,
  email text not null,
  display_name text
);
alter table public.profiles enable row level security;
create table public.messages (
  id bigserial primary key,
  user_id uuid references public.profiles(id),
  body text
);
alter table public.messages enable row level security;
