
-- Init script to create the user sogo and the database sogo for MariaDB / MySQL.

CREATE DATABASE IF NOT EXISTS `sogo`
  DEFAULT CHARACTER SET = utf8mb4
  DEFAULT COLLATE = utf8mb4_general_ci;

CREATE USER IF NOT EXISTS 'sogo'@'%' IDENTIFIED BY 'sogo';
GRANT ALL PRIVILEGES ON `sogo`.* TO 'sogo'@'%';

-- GRANT ALL PRIVILEGES ON *.* TO 'sogo'@'%' WITH GRANT OPTION;
-- FLUSH PRIVILEGES;


-- Create the user source tables

USE `sogo`;

CREATE TABLE IF NOT EXISTS `sogo_users` (
  `uid` TEXT NOT NULL PRIMARY KEY,
  `mail` TEXT NOT NULL,
  `password` TEXT NOT NULL,
  `cn` TEXT NOT NULL,
  `ou` TEXT NOT NULL
);

-- Insert the three users
INSERT INTO `sogo_users` (`uid`, `mail`, `password`, `cn`, `ou`)
VALUES
  ('sogo-db1@example.org', 'sogo-db1@example.org', 'sogo', 'Dude db', 'example.org'),
  ('sogo-db2@example.org', 'sogo-db2@example.org', 'sogo', 'Hewill db', 'example.org'),
  ('sogo-db3@example.org', 'sogo-db3@example.org', 'sogo', 'Ithas db', 'example.org');