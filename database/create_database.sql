-- Optional: create the database and a dedicated MySQL user by hand
-- (setup.bat creates the database automatically with the login you give it).
-- Run in MySQL Workbench or:  mysql -u root -p < database/create_database.sql

CREATE DATABASE IF NOT EXISTS routerate CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Change the password before using this
CREATE USER IF NOT EXISTS 'routerate'@'localhost' IDENTIFIED BY 'ChangeMe_123!';
GRANT ALL PRIVILEGES ON routerate.* TO 'routerate'@'localhost';
-- Needed only to run the automated tests (Django creates test_routerate):
GRANT ALL PRIVILEGES ON test_routerate.* TO 'routerate'@'localhost';
FLUSH PRIVILEGES;
