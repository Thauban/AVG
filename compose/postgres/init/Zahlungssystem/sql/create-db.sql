CREATE USER zs_mitarbeiter PASSWORD 'x';
CREATE DATABASE zahlungssystem;
GRANT ALL ON DATABASE zahlungssystem TO zs_mitarbeiter;
CREATE TABLESPACE zahlungssystemspace OWNER zs_mitarbeiter LOCATION '/tablespace/zahlungssystem';
