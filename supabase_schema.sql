create table if not exists public.settings (
  id integer primary key,
  notice_text text not null default '현재 공지사항이 없습니다.',
  policy_json jsonb null,
  updated_at timestamptz default now()
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
  status varchar(20) not null default 'RESERVED',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into public.settings (id, notice_text)
values (1, '현재 공지사항이 없습니다.')
on conflict (id) do nothing;