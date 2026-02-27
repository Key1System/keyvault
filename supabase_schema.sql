-- Run this in your Supabase SQL editor

create table keys (
  id uuid default gen_random_uuid() primary key,
  key text not null unique,
  label text default '',
  enabled boolean default true,
  hwid text,
  active_hwid text,
  expires_at timestamptz,
  last_seen timestamptz,
  created_at timestamptz default now()
);

-- Index for fast key lookups
create index on keys (key);

-- Disable row level security (service key bypasses anyway, but just in case)
alter table keys disable row level security;
