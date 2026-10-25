-- Patients and their cards. /* not a comment opener here */
CREATE TABLE patients (
  id serial PRIMARY KEY,
  email text NOT NULL,
  birthday date,
  creditcard text
);

/* creditcard payments are handled elsewhere */
/*
 stores medical notes
*/
CREATE TABLE notes (
  id serial PRIMARY KEY,
  birth_date date
);

INSERT INTO notes (id) VALUES ('creditcard');
