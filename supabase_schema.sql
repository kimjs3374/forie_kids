create table if not exists public.settings (
  id integer primary key,
  notice_text text not null default '현재 공지사항이 없습니다.',
  policy_json jsonb null,
  updated_at timestamptz default now()
);

create table if not exists public.month_passwords (
  target_month varchar(7) primary key,
  access_password varchar(4) not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.used_passwords (
  password varchar(4) primary key,
  created_at timestamptz not null default now()
);

create table if not exists public.reservation_months (
  id bigint generated always as identity primary key,
  target_month varchar(7) unique not null,
  title varchar(100),
  open_at timestamptz not null,
  close_at timestamptz not null,
  status varchar(20) not null default 'DRAFT',
  max_reservations_per_household integer default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.reservation_slots (
  id bigint generated always as identity primary key,
  month_id bigint not null references public.reservation_months(id) on delete cascade,
  play_date date not null,
  start_time time not null,
  end_time time not null,
  capacity integer not null,
  status varchar(20) not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.reservations (
  id bigint generated always as identity primary key,
  month_id bigint not null references public.reservation_months(id) on delete cascade,
  slot_id bigint not null references public.reservation_slots(id) on delete cascade,
  name varchar(50) not null,
  apt_unit varchar(50) not null,
  phone varchar(20) not null,
  children_count integer not null,
  consent_agreed boolean not null default false,
  consent_agreed_at timestamptz null,
  status varchar(20) not null default 'RESERVED',
  payment_confirmed_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.deposit_requests (
  id bigint generated always as identity primary key,
  legacy_thread_id text unique null,
  request_key text not null unique,
  name varchar(50) not null,
  phone varchar(20) not null,
  apt_dong varchar(10) not null,
  apt_ho varchar(10) not null,
  consent_agreed boolean not null default false,
  consent_agreed_at timestamptz null,
  status varchar(20) not null default 'PENDING',
  latest_message_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.deposit_request_messages (
  id bigint generated always as identity primary key,
  request_id bigint not null references public.deposit_requests(id) on delete cascade,
  legacy_message_id text unique null,
  author_type varchar(20) not null,
  content text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.ticker_messages (
  id bigint generated always as identity primary key,
  content text not null,
  display_seconds integer not null default 3,
  sort_order integer not null default 0,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bank_settings (
  id bigint generated always as identity primary key,
  bank_code varchar(20) not null,
  account_holder_name varchar(100) null,
  payment_amount integer not null default 5000,
  account_number_encrypted text not null,
  account_password_encrypted text not null,
  resident_number_encrypted text not null,
  is_active boolean not null default false,
  account_registered_at timestamptz null,
  last_synced_at timestamptz null,
  sync_cursor_at timestamptz null,
  last_error_message text null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bank_transactions (
  id bigint generated always as identity primary key,
  bank_setting_id bigint null references public.bank_settings(id) on delete set null,
  bank_code varchar(20) null,
  transaction_uid varchar(128) not null unique,
  deposit_name varchar(100) null,
  amount integer not null default 0,
  transaction_date timestamptz null,
  description varchar(100) null,
  display_name varchar(100) null,
  counterparty varchar(100) null,
  balance bigint null,
  transaction_type varchar(20) not null default 'deposit',
  status varchar(20) not null default 'PENDING',
  matched_reservation_id bigint null references public.reservations(id) on delete set null,
  matched_at timestamptz null,
  is_billboard_approved boolean not null default false,
  billboard_posted_at timestamptz null,
  raw_json jsonb null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bank_sync_runs (
  id bigint generated always as identity primary key,
  bank_setting_id bigint null references public.bank_settings(id) on delete set null,
  started_at timestamptz not null default now(),
  finished_at timestamptz null,
  status varchar(20) not null default 'RUNNING',
  requested_from date null,
  requested_to date null,
  fetched_count integer not null default 0,
  inserted_count integer not null default 0,
  matched_count integer not null default 0,
  unmatched_count integer not null default 0,
  error_message text null
);

create table if not exists public.bank_match_logs (
  id bigint generated always as identity primary key,
  transaction_id bigint not null references public.bank_transactions(id) on delete cascade,
  reservation_id bigint null references public.reservations(id) on delete set null,
  match_type varchar(20) not null,
  result varchar(20) not null,
  reason text null,
  created_by_admin_id bigint null,
  created_at timestamptz not null default now()
);

create index if not exists idx_bank_transactions_status_date on public.bank_transactions(status, transaction_date desc);
create index if not exists idx_bank_transactions_reservation on public.bank_transactions(matched_reservation_id);
create index if not exists idx_bank_sync_runs_started_at on public.bank_sync_runs(started_at desc);
create index if not exists idx_reservations_slot_status on public.reservations(slot_id, status);
create index if not exists idx_reservations_month_status on public.reservations(month_id, status);

do $$
begin
  if not exists (
    select 1
    from pg_indexes
    where schemaname = 'public'
      and indexname = 'uq_reservations_active_month_apt_unit'
  ) then
    if exists (
      select 1
      from public.reservations
      where status <> 'CANCELLED'
      group by month_id, apt_unit
      having count(*) > 1
    ) then
      raise notice 'uq_reservations_active_month_apt_unit skipped because duplicate active reservations already exist.';
    else
      execute 'create unique index uq_reservations_active_month_apt_unit on public.reservations(month_id, apt_unit) where status <> ''CANCELLED''';
    end if;
  end if;
end $$;

do $$
begin
  if not exists (
    select 1
    from pg_indexes
    where schemaname = 'public'
      and indexname = 'uq_reservations_active_month_phone'
  ) then
    if exists (
      select 1
      from public.reservations
      where status <> 'CANCELLED'
      group by month_id, phone
      having count(*) > 1
    ) then
      raise notice 'uq_reservations_active_month_phone skipped because duplicate active phone reservations already exist.';
    else
      execute 'create unique index uq_reservations_active_month_phone on public.reservations(month_id, phone) where status <> ''CANCELLED''';
    end if;
  end if;
end $$;

do $$
begin
  if not exists (
    select 1
    from pg_indexes
    where schemaname = 'public'
      and indexname = 'uq_bank_sync_runs_running'
  ) then
    if exists (
      select 1
      from public.bank_sync_runs
      where status = 'RUNNING'
      group by bank_setting_id
      having count(*) > 1
    ) then
      raise notice 'uq_bank_sync_runs_running skipped because multiple RUNNING sync rows already exist.';
    else
      execute 'create unique index uq_bank_sync_runs_running on public.bank_sync_runs(bank_setting_id) where status = ''RUNNING''';
    end if;
  end if;
end $$;

alter table public.bank_settings
  add column if not exists payment_amount integer not null default 5000;

alter table public.reservations
  add column if not exists payment_confirmed_at timestamptz null;

alter table public.reservations
  add column if not exists consent_agreed_at timestamptz null;

alter table public.reservation_months
  add column if not exists payment_amount integer not null default 0;

alter table public.reservations
  add column if not exists expected_amount integer not null default 0;

create or replace function public.create_reservation_atomic(
  p_month_id bigint,
  p_name varchar,
  p_apt_unit varchar,
  p_phone varchar,
  p_children_count integer,
  p_expected_amount integer,
  p_consent_agreed boolean,
  p_consent_agreed_at timestamptz default null
)
returns table (
  reservation_id bigint,
  slot_id bigint,
  reservation_status varchar
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_month public.reservation_months%rowtype;
  v_slot public.reservation_slots%rowtype;
  v_reserved_count integer;
  v_inserted public.reservations%rowtype;
begin
  select *
  into v_month
  from public.reservation_months
  where id = p_month_id;

  if not found then
    raise exception using message = '현재 신청 가능한 월이 아닙니다.';
  end if;

  if now() < v_month.open_at or now() > v_month.close_at then
    raise exception using message = '현재 신청 접수 기간이 아닙니다.';
  end if;

  select *
  into v_slot
  from public.reservation_slots
  where month_id = p_month_id
    and status = 'ACTIVE'
  order by play_date asc, start_time asc, id asc
  limit 1
  for update;

  if not found then
    raise exception using message = '신청 가능한 슬롯이 없습니다. 관리자에게 문의해주세요.';
  end if;

  select count(*)
  into v_reserved_count
  from public.reservations
  where slot_id = v_slot.id
    and status <> 'CANCELLED';

  if v_reserved_count >= coalesce(v_slot.capacity, 0) then
    raise exception using message = '해당 월 신청 정원이 모두 마감되었습니다. 더 이상 신청할 수 없습니다.';
  end if;

  if exists (
    select 1
    from public.reservations
    where month_id = p_month_id
      and status <> 'CANCELLED'
      and (apt_unit = p_apt_unit or phone = p_phone)
  ) then
    raise exception using message = '해당 월 이용 신청은 세대당 1회만 가능합니다. 입금 확인 후 해당 월 자유롭게 이용할 수 있습니다.';
  end if;

  begin
    insert into public.reservations (
      month_id,
      slot_id,
      name,
      apt_unit,
      phone,
      children_count,
      expected_amount,
      consent_agreed,
      consent_agreed_at,
      status
    )
    values (
      p_month_id,
      v_slot.id,
      p_name,
      p_apt_unit,
      p_phone,
      p_children_count,
      coalesce(p_expected_amount, 0),
      coalesce(p_consent_agreed, false),
      p_consent_agreed_at,
      'PENDING_PAYMENT'
    )
    returning * into v_inserted;
  exception
    when unique_violation then
      raise exception using message = '해당 월 이용 신청은 세대당 1회만 가능합니다. 입금 확인 후 해당 월 자유롭게 이용할 수 있습니다.';
  end;

  return query
  select v_inserted.id, v_slot.id, v_inserted.status;
end;
$$;

update public.reservation_months
set payment_amount = 0
where payment_amount is null;

update public.reservations r
set expected_amount = coalesce(m.payment_amount, 0)
from public.reservation_months m
where r.month_id = m.id
  and coalesce(r.expected_amount, 0) = 0;

update public.reservations
set consent_agreed_at = created_at
where consent_agreed = true
  and consent_agreed_at is null;

alter table public.deposit_requests
  add column if not exists consent_agreed boolean;

alter table public.deposit_requests
  alter column consent_agreed set default false;

update public.deposit_requests
set consent_agreed = true
where consent_agreed is null;

alter table public.deposit_requests
  alter column consent_agreed set not null;

alter table public.deposit_requests
  add column if not exists consent_agreed_at timestamptz null;

update public.deposit_requests
set consent_agreed_at = created_at
where consent_agreed_at is null;

insert into public.month_passwords (target_month, access_password)
select entry.key, entry.value
from public.settings s
cross join lateral jsonb_each_text(coalesce(s.policy_json->'month_passwords', '{}'::jsonb)) as entry(key, value)
on conflict (target_month) do update
set access_password = excluded.access_password,
    updated_at = now();

insert into public.used_passwords (password)
select distinct value
from (
  select jsonb_array_elements_text(coalesce(s.policy_json->'used_month_passwords', '[]'::jsonb)) as value
  from public.settings s
  union all
  select entry.value as value
  from public.settings s
  cross join lateral jsonb_each_text(coalesce(s.policy_json->'month_passwords', '{}'::jsonb)) as entry(key, value)
) passwords
where coalesce(value, '') <> ''
on conflict (password) do nothing;

update public.reservations r
set payment_confirmed_at = source.confirmed_at
from (
  select (entry.key)::bigint as reservation_id, (entry.value)::timestamptz as confirmed_at
  from public.settings s
  cross join lateral jsonb_each_text(coalesce(s.policy_json->'reservation_payment_confirmed_at', '{}'::jsonb)) as entry(key, value)
) source
where r.id = source.reservation_id
  and (r.payment_confirmed_at is distinct from source.confirmed_at);

insert into public.deposit_requests (
  legacy_thread_id,
  request_key,
  name,
  phone,
  apt_dong,
  apt_ho,
  consent_agreed,
  consent_agreed_at,
  status,
  latest_message_at,
  created_at,
  updated_at
)
select
  thread->>'id' as legacy_thread_id,
  coalesce(thread->>'request_key', concat_ws('|', thread->>'name', thread->>'phone', thread->>'apt_dong', thread->>'apt_ho')) as request_key,
  coalesce(thread->>'name', '') as name,
  coalesce(thread->>'phone', '') as phone,
  coalesce(thread->>'apt_dong', '') as apt_dong,
  coalesce(thread->>'apt_ho', '') as apt_ho,
  true as consent_agreed,
  coalesce((thread->>'created_at')::timestamptz, now()) as consent_agreed_at,
  coalesce(thread->>'status', 'PENDING') as status,
  coalesce((thread->>'latest_message_at')::timestamptz, now()) as latest_message_at,
  coalesce((thread->>'created_at')::timestamptz, now()) as created_at,
  coalesce((thread->>'latest_message_at')::timestamptz, now()) as updated_at
from public.settings s
cross join lateral jsonb_array_elements(coalesce(s.policy_json->'payment_requests', '[]'::jsonb)) as thread
on conflict (request_key) do update
set status = excluded.status,
    latest_message_at = excluded.latest_message_at,
    updated_at = excluded.updated_at;

insert into public.deposit_request_messages (
  request_id,
  legacy_message_id,
  author_type,
  content,
  created_at
)
select
  dr.id,
  message->>'id' as legacy_message_id,
  coalesce(message->>'author_type', 'USER') as author_type,
  coalesce(message->>'content', '') as content,
  coalesce((message->>'created_at')::timestamptz, dr.created_at) as created_at
from public.settings s
cross join lateral jsonb_array_elements(coalesce(s.policy_json->'payment_requests', '[]'::jsonb)) as thread
join public.deposit_requests dr
  on dr.request_key = coalesce(thread->>'request_key', concat_ws('|', thread->>'name', thread->>'phone', thread->>'apt_dong', thread->>'apt_ho'))
cross join lateral jsonb_array_elements(coalesce(thread->'messages', '[]'::jsonb)) as message
where coalesce(message->>'content', '') <> ''
on conflict (legacy_message_id) do nothing;

update public.deposit_requests dr
set latest_message_at = latest.latest_message_at,
    updated_at = greatest(dr.updated_at, latest.latest_message_at)
from (
  select request_id, max(created_at) as latest_message_at
  from public.deposit_request_messages
  group by request_id
) latest
where dr.id = latest.request_id
  and (dr.latest_message_at is distinct from latest.latest_message_at);

insert into public.settings (id, notice_text)
values (1, '현재 공지사항이 없습니다.')
on conflict (id) do nothing;