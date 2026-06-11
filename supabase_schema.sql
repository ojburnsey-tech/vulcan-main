-- ════════════════════════════════════════════════════════════════════════════
-- Vulcan Quanta — database schema, privileges and row-level security
-- Run this in Supabase Dashboard → SQL Editor → New query. Safe to re-run.
--
-- Fixes Postgres error 42501 "permission denied for table projects":
-- the API roles (authenticated / service_role) need explicit GRANTs, and the
-- tables need RLS policies so each user can only touch their own rows.
-- ════════════════════════════════════════════════════════════════════════════

create extension if not exists pgcrypto;

-- ── Projects ────────────────────────────────────────────────────────────────
create table if not exists public.projects (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users(id) on delete cascade,
  name             text,
  description      text,
  client_name      text,
  contract_type    text,
  location_factor  text,
  notes_for_ai     text,
  auto_delete_days integer,
  page_count       integer,
  estimated_value  numeric,
  boq_data         jsonb,
  status           text default 'draft',
  created_at       timestamptz not null default now()
);

-- Bring an existing table up to date with every column the app uses.
alter table public.projects add column if not exists description      text;
alter table public.projects add column if not exists client_name      text;
alter table public.projects add column if not exists contract_type    text;
alter table public.projects add column if not exists location_factor  text;
alter table public.projects add column if not exists notes_for_ai     text;
alter table public.projects add column if not exists auto_delete_days integer;
alter table public.projects add column if not exists page_count       integer;
alter table public.projects add column if not exists estimated_value  numeric;
alter table public.projects add column if not exists boq_data         jsonb;
alter table public.projects add column if not exists status           text default 'draft';
alter table public.projects add column if not exists created_at       timestamptz not null default now();

-- ── Chat messages ───────────────────────────────────────────────────────────
create table if not exists public.chat_messages (
  id         uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  role       text not null check (role in ('user', 'assistant')),
  content    text not null,
  created_at timestamptz not null default now()
);

-- ── Branding ────────────────────────────────────────────────────────────────
-- One row per user: company identity shown on exported BoQs, managed from the
-- Settings → Branding tab. The logo is stored as a data URL (max 2 MB file).
create table if not exists public.branding (
  user_id         uuid primary key references auth.users(id) on delete cascade,
  company_name    text,
  company_address text,
  company_phone   text,
  company_email   text,
  logo            text,
  updated_at      timestamptz not null default now()
);

-- ── Privileges ──────────────────────────────────────────────────────────────
-- Deliberately nothing for `anon`: the anon key is public in the frontend, so
-- granting it table access would expose every user's data. The backend now
-- runs table operations as service_role, or as `authenticated` by forwarding
-- the signed-in user's JWT.
grant usage on schema public to authenticated, service_role;
grant select, insert, update, delete on public.projects      to authenticated, service_role;
grant select, insert, update, delete on public.chat_messages to authenticated, service_role;
grant select, insert, update, delete on public.branding      to authenticated, service_role;

-- profiles is created by SUPABASE_SETUP.md §3 — grant only if it exists so this
-- script never aborts halfway.
do $$
begin
  if to_regclass('public.profiles') is not null then
    grant select, insert, update, delete on public.profiles to authenticated, service_role;
  end if;
end $$;

-- ── Row-level security ──────────────────────────────────────────────────────
alter table public.projects      enable row level security;
alter table public.chat_messages enable row level security;
alter table public.branding      enable row level security;

drop policy if exists "Users manage own projects" on public.projects;
create policy "Users manage own projects"
  on public.projects for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users manage own chat messages" on public.chat_messages;
create policy "Users manage own chat messages"
  on public.chat_messages for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users manage own branding" on public.branding;
create policy "Users manage own branding"
  on public.branding for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ── Auto-delete expired projects ────────────────────────────────────────────
-- Called by the backend before every project list (GDPR auto-delete option).
create or replace function public.delete_expired_projects(uid uuid)
returns void
language sql
security definer
set search_path = public
as $$
  delete from public.projects
  where user_id = uid
    and auto_delete_days is not null
    and created_at < now() - make_interval(days => auto_delete_days);
$$;

grant execute on function public.delete_expired_projects(uuid) to authenticated, service_role;
