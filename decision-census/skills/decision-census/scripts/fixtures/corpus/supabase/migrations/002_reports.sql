create view my_reports as
select * from reports where owner_id = current_setting('app.user_id')::uuid;
