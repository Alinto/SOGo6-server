
-- Init script to create the user sogo and the database sogo.
-- All the tables are created by sogo itself.

CREATE ROLE sogo WITH
  SUPERUSER
  LOGIN
  PASSWORD 'sogo';

CREATE DATABASE sogo;
GRANT ALL PRIVILEGES ON DATABASE sogo TO sogo;

