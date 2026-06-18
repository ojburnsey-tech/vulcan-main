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

-- ── Status check constraint ─────────────────────────────────────────────────
-- Some live databases gained a stricter "projects_status_check" constraint
-- (e.g. created from the dashboard) that rejects 'draft', which broke project
-- creation with Postgres error 23514. Rebuild it with the full vocabulary the
-- app actually uses, after normalising any rows that would violate it.
alter table public.projects drop constraint if exists projects_status_check;
update public.projects
   set status = 'draft'
 where status is null
    or status not in ('draft', 'processing', 'completed', 'archived');
alter table public.projects alter column status set default 'draft';
alter table public.projects
  add constraint projects_status_check
  check (status in ('draft', 'processing', 'completed', 'archived'));

-- ── Chat messages ───────────────────────────────────────────────────────────
create table if not exists public.chat_messages (
  id         uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  role       text not null check (role in ('user', 'assistant')),
  content    text not null,
  created_at timestamptz not null default now()
);

-- ── Usage events ─────────────────────────────────────────────────────────────
-- raw_response/model/stop_reason are the COST-SAFETY recovery columns: /process
-- writes the (already billed) Claude output here BEFORE parsing/enriching/saving,
-- so a dropped response or killed worker never means a fully wasted Claude call.
create table if not exists public.usage_events (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  project_id    uuid references public.projects(id) on delete set null,
  input_tokens  integer not null default 0,
  output_tokens integer not null default 0,
  raw_response  text,
  model         text,
  stop_reason   text,
  created_at    timestamptz not null default now()
);

-- Bring an existing usage_events table up to date so the recovery persistence in
-- /process works without a manual migration (insert falls back to the minimal
-- row if these are absent, but adding them enables BoQ recovery).
alter table public.usage_events add column if not exists raw_response text;
alter table public.usage_events add column if not exists model        text;
alter table public.usage_events add column if not exists stop_reason  text;

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

-- Bring an existing branding table up to date with every column the app uses.
-- Fixes "Could not find the 'logo' column of 'branding' in the schema cache"
-- when saving from Settings → Branding on a database created before the
-- column existed.
alter table public.branding add column if not exists company_name    text;
alter table public.branding add column if not exists company_address text;
alter table public.branding add column if not exists company_phone   text;
alter table public.branding add column if not exists company_email   text;
alter table public.branding add column if not exists logo            text;
alter table public.branding add column if not exists updated_at      timestamptz not null default now();

-- ── Classification overrides ────────────────────────────────────────────────
-- Per-user learned mappings: normalised_description → (nrm2_section, rate_key).
-- Applied before keyword rules so user corrections are respected on all future
-- imports. One row per (user_id, source_term) — upserted on each manual change.
create table if not exists public.classification_overrides (
  id           uuid        primary key default gen_random_uuid(),
  user_id      uuid        not null references auth.users(id) on delete cascade,
  source_term  text        not null,
  nrm2_section text,
  rate_key     text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- One override per term per user — enforces clean upsert semantics.
create unique index if not exists classification_overrides_user_term
  on public.classification_overrides (user_id, source_term);

-- Index for the common read pattern (load all overrides for a user).
create index if not exists classification_overrides_user_id
  on public.classification_overrides (user_id);

-- ── Privileges ──────────────────────────────────────────────────────────────
-- Deliberately nothing for `anon`: the anon key is public in the frontend, so
-- granting it table access would expose every user's data. The backend now
-- runs table operations as service_role, or as `authenticated` by forwarding
-- the signed-in user's JWT.
grant usage on schema public to authenticated, service_role;
grant select, insert, update, delete on public.projects      to authenticated, service_role;
grant select, insert, update, delete on public.chat_messages to authenticated, service_role;
grant select, insert on public.usage_events to authenticated, service_role;
grant select, insert, update, delete on public.branding                   to authenticated, service_role;
grant select, insert, update, delete on public.classification_overrides    to authenticated, service_role;

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

alter table public.classification_overrides enable row level security;

drop policy if exists "Users manage own classification overrides" on public.classification_overrides;
create policy "Users manage own classification overrides"
  on public.classification_overrides for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

alter table public.usage_events enable row level security;

drop policy if exists "Users read own usage" on public.usage_events;
create policy "Users read own usage"
  on public.usage_events for select
  using (auth.uid() = user_id);

drop policy if exists "Service role inserts usage" on public.usage_events;
create policy "Service role inserts usage"
  on public.usage_events for insert
  with check (true);
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

-- ── Refresh the PostgREST schema cache ──────────────────────────────────────
-- Supabase's API layer caches the schema; tell it to reload so new columns
-- (e.g. branding.logo) are usable immediately without waiting or restarting.
notify pgrst, 'reload schema';

-- ════════════════════════════════════════════════════════════════════════════
-- QS Review & Sign-off workspace
-- Run this block after the baseline schema above.
-- ════════════════════════════════════════════════════════════════════════════

-- ── New columns on projects ─────────────────────────────────────────────────
-- review_states: jsonb map of item_id → {state, qty?, rate?, reason?}
-- signed_off_*:  immutable after sign-off; cleared on revoke
alter table public.projects add column if not exists review_states        jsonb        not null default '{}'::jsonb;
alter table public.projects add column if not exists signed_off_at        timestamptz;
alter table public.projects add column if not exists signed_off_by        text;
alter table public.projects add column if not exists signoff_title        text;
alter table public.projects add column if not exists signoff_declaration  boolean;
alter table public.projects add column if not exists signoff_hash         text;

-- ── Widen status constraint to include review lifecycle values ───────────────
-- Drop the existing constraint, normalise any stale rows, then recreate with
-- the full vocabulary the app now uses.  This mirrors the pattern used above
-- for the earlier 'draft' fix so it is safe to re-run.
alter table public.projects drop constraint if exists projects_status_check;
update public.projects
   set status = 'draft'
 where status is null
    or status not in ('draft','processing','completed','archived','in_review','signed_off');
alter table public.projects alter column status set default 'draft';
alter table public.projects
  add constraint projects_status_check
  check (status in ('draft','processing','completed','archived','in_review','signed_off'));

-- ── Audit trail ─────────────────────────────────────────────────────────────
-- Append-only log of every review action (line approvals, modifications,
-- rejections, section approvals, sign-offs, revocations).  Mirrors the
-- privilege model of usage_events: only select + insert are granted so no
-- row can ever be updated or deleted by accident.
create table if not exists public.boq_audit_events (
  id          uuid        primary key default gen_random_uuid(),
  project_id  uuid        not null references public.projects(id) on delete cascade,
  user_id     uuid        not null references auth.users(id)      on delete cascade,
  action      text        not null,   -- e.g. 'line_approved', 'signed_off'
  item_id     text,                   -- null for section / project-level actions
  section     text,                   -- NRM2 section trade name
  prev_state  jsonb,                  -- review state before this action
  new_state   jsonb,                  -- review state after this action
  reason      text,                   -- rejection reason, revocation note, etc.
  created_at  timestamptz not null default now()
);

-- Sparse index for the common read path (load trail for one project).
create index if not exists boq_audit_events_project_id
  on public.boq_audit_events (project_id, created_at desc);

grant select, insert on public.boq_audit_events to authenticated, service_role;

alter table public.boq_audit_events enable row level security;

drop policy if exists "Users read own audit events" on public.boq_audit_events;
create policy "Users read own audit events"
  on public.boq_audit_events for select
  using (auth.uid() = user_id);

-- Any authenticated role can insert (service_role bypasses RLS entirely, but
-- authenticated requests from the frontend also work with with check (true)).
drop policy if exists "Service role inserts audit events" on public.boq_audit_events;
create policy "Service role inserts audit events"
  on public.boq_audit_events for insert
  with check (true);

-- Reload schema so new columns and table are visible to the API immediately.
notify pgrst, 'reload schema';

-- ── Editable working copy of the bill ──────────────────────────────────────
-- boq_data remains the untouched AI output (read-only reference for diffing).
-- working_boq is the live, QS-editable bill: every Review workspace edit,
-- added line, added section and soft-delete happens here. Exports render
-- working_boq when present, falling back to boq_data for projects that
-- predate this column (so old projects don't break).
alter table public.projects add column if not exists working_boq jsonb;
