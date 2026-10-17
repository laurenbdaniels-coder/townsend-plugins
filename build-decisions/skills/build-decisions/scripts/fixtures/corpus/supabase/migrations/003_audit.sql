create table identity_checks (
  id uuid primary key,
  method text not null -- self_attest_dob | provider
);
