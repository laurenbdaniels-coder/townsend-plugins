-- birthday reminders are sent by the mail service
/* creditcard payments go through the payment company */
/*
 stores medical notes
*/
create table public.notes (
  id uuid primary key,
  body text,
  passport_no text
);
insert into public.notes (body) values ('creditcard');
