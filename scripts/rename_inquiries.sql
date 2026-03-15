begin;

alter table if exists public.deposit_request_messages rename to inquiry_messages;
alter table if exists public.deposit_requests rename to inquiries;

do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'inquiry_messages' and column_name = 'request_id'
  ) then
    alter table public.inquiry_messages rename column request_id to inquiry_id;
  end if;
end $$;

commit;