
-- Init script to create the user sogo and the database sogo for MariaDB / MySQL.

CREATE DATABASE IF NOT EXISTS `sogo`
  DEFAULT CHARACTER SET = utf8mb4
  DEFAULT COLLATE = utf8mb4_general_ci;

CREATE USER IF NOT EXISTS 'sogo'@'%' IDENTIFIED BY 'sogo';
GRANT ALL PRIVILEGES ON `sogo`.* TO 'sogo'@'%';

-- GRANT ALL PRIVILEGES ON *.* TO 'sogo'@'%' WITH GRANT OPTION;
-- FLUSH PRIVILEGES;