begin;

delete from public.bank_match_logs;
delete from public.bank_sync_runs;
delete from public.bank_transactions;
delete from public.inquiry_messages;
delete from public.inquiries;
delete from public.reservations;
delete from public.reservation_slots;
delete from public.reservation_months;
delete from public.ticker_messages;
delete from public.month_passwords;
delete from public.used_passwords;
delete from public.bank_settings;
delete from public.settings;

commit;
