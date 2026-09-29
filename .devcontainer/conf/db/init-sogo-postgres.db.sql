
-- Init script to create the user sogo and the database sogo.
-- All the tables are created by sogo itself.

CREATE ROLE sogo WITH
  SUPERUSER
  LOGIN
  PASSWORD 'sogo';

CREATE DATABASE sogo;
GRANT ALL PRIVILEGES ON DATABASE sogo TO sogo;


-- Connect to the database
\c sogo

-- Create the sogo_users table
CREATE TABLE sogo_users (
  uid TEXT NOT NULL PRIMARY KEY,
  mail TEXT NOT NULL,
  password TEXT NOT NULL,
  cn TEXT NOT NULL,
  ou TEXT NOT NULL
);

-- Insert the three users
INSERT INTO sogo_users (uid, mail, password, cn, ou)
VALUES
  ('sogo-db1@example.org', 'sogo-db1@example.org', 'sogo', 'Dude db', 'example.org'),
  ('sogo-db2@example.org', 'sogo-db2@example.org', 'sogo', 'Hewill db', 'example.org'),
  ('sogo-db3@example.org', 'sogo-db3@example.org', 'sogo', 'Ithas db', 'example.org');