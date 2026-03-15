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
  from public.reservation_months rm
  where rm.id = p_month_id;

  if not found then
    raise exception using message = '현재 신청 가능한 월이 아닙니다.';
  end if;

  if now() < v_month.open_at or now() > v_month.close_at then
    raise exception using message = '현재 신청 접수 기간이 아닙니다.';
  end if;

  select *
  into v_slot
  from public.reservation_slots rs
  where rs.month_id = p_month_id
    and rs.status = 'ACTIVE'
  order by rs.play_date asc, rs.start_time asc, rs.id asc
  limit 1
  for update;

  if not found then
    raise exception using message = '신청 가능한 슬롯이 없습니다. 관리자에게 문의해주세요.';
  end if;

  select count(*)
  into v_reserved_count
  from public.reservations r
  where r.slot_id = v_slot.id
    and r.status <> 'CANCELLED';

  if v_reserved_count >= coalesce(v_slot.capacity, 0) then
    raise exception using message = '해당 월 신청 정원이 모두 마감되었습니다. 더 이상 신청할 수 없습니다.';
  end if;

  if exists (
    select 1
    from public.reservations r
    where r.month_id = p_month_id
      and r.status <> 'CANCELLED'
      and (r.apt_unit = p_apt_unit or r.phone = p_phone)
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
  select v_inserted.id as reservation_id, v_slot.id as slot_id, v_inserted.status as reservation_status;
end;
$$;