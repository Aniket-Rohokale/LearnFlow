-- TrackAI — initial schema
-- All tables have RLS enabled. The FastAPI backend connects as the table owner
-- (Supabase connection string) and bypasses RLS; these policies constrain the
-- browser's anon-key access only.

-- ---------------------------------------------------------------------------
-- users — profile row mirroring auth.users, created by trigger on signup
-- ---------------------------------------------------------------------------
create table public.users (
  id                   uuid primary key references auth.users (id) on delete cascade,
  email                text not null,
  career_goal          text,
  target_hours_per_day numeric(4, 2) check (target_hours_per_day > 0 and target_hours_per_day <= 24),
  created_at           timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- courses — one row per (user, course URL); re-ingesting upserts on this key
-- ---------------------------------------------------------------------------
create table public.courses (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.users (id) on delete cascade,
  platform   text not null,
  title      text not null,
  url        text not null,
  instructor text,
  created_at timestamptz not null default now(),
  unique (user_id, url)
);

create index courses_user_id_idx on public.courses (user_id);

-- ---------------------------------------------------------------------------
-- modules — ordered syllabus items; (course_id, position) is the upsert key
-- ---------------------------------------------------------------------------
create table public.modules (
  id                uuid primary key default gen_random_uuid(),
  course_id         uuid not null references public.courses (id) on delete cascade,
  position          int not null check (position >= 0),
  title             text not null,
  estimated_minutes int check (estimated_minutes > 0),
  completed         boolean not null default false,
  completed_at      timestamptz,
  unique (course_id, position)
);

create index modules_course_id_idx on public.modules (course_id);

-- ---------------------------------------------------------------------------
-- course_progress — exactly one row per course, updated in place on re-sync
-- ---------------------------------------------------------------------------
create table public.course_progress (
  id               uuid primary key default gen_random_uuid(),
  course_id        uuid not null references public.courses (id) on delete cascade,
  percent_complete numeric(5, 2) not null default 0
                   check (percent_complete >= 0 and percent_complete <= 100),
  last_synced_at   timestamptz not null default now(),
  unique (course_id)
);

-- ---------------------------------------------------------------------------
-- activity_logs — study sessions from the extension, manual entry, or dashboard
-- ---------------------------------------------------------------------------
create table public.activity_logs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.users (id) on delete cascade,
  occurred_at     timestamptz not null default now(),
  session_minutes int not null check (session_minutes > 0),
  source          text not null check (source in ('extension', 'manual', 'dashboard'))
);

create index activity_logs_user_time_idx on public.activity_logs (user_id, occurred_at desc);

-- ---------------------------------------------------------------------------
-- ai_recommendations — append-only; dashboard reads latest row per type
-- ---------------------------------------------------------------------------
create table public.ai_recommendations (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references public.users (id) on delete cascade,
  type         text not null check (type in ('syllabus', 'plan', 'burnout', 'roadmap')),
  content_json jsonb not null,
  model        text not null,
  created_at   timestamptz not null default now()
);

create index ai_recommendations_latest_idx
  on public.ai_recommendations (user_id, type, created_at desc);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.users              enable row level security;
alter table public.courses            enable row level security;
alter table public.modules            enable row level security;
alter table public.course_progress    enable row level security;
alter table public.activity_logs      enable row level security;
alter table public.ai_recommendations enable row level security;

-- users: read + update own profile (insert happens via trigger below)
create policy "users_select_own" on public.users
  for select using (auth.uid() = id);
create policy "users_update_own" on public.users
  for update using (auth.uid() = id) with check (auth.uid() = id);

-- courses / modules / activity_logs: full own-row access
create policy "courses_all_own" on public.courses
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy "modules_all_own" on public.modules
  for all
  using (exists (select 1 from public.courses c
                 where c.id = course_id and c.user_id = auth.uid()))
  with check (exists (select 1 from public.courses c
                      where c.id = course_id and c.user_id = auth.uid()));

create policy "activity_logs_all_own" on public.activity_logs
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- course_progress: read-only from the client; only the backend computes it
create policy "course_progress_select_own" on public.course_progress
  for select
  using (exists (select 1 from public.courses c
                 where c.id = course_id and c.user_id = auth.uid()));

-- ai_recommendations: select + insert only — append-only is enforced by the
-- deliberate absence of update/delete policies
create policy "ai_recommendations_select_own" on public.ai_recommendations
  for select using (auth.uid() = user_id);
create policy "ai_recommendations_insert_own" on public.ai_recommendations
  for insert with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Trigger: create public.users profile row on auth signup
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.users (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
