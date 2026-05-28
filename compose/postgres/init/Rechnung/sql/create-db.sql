CREATE USER sachbearbeiter PASSWORD 'x';
CREATE DATABASE rechnung;
GRANT ALL ON DATABASE rechnung TO sachbearbeiter;
CREATE TABLESPACE rechnungspace OWNER sachbearbeiter LOCATION '/tablespace/rechnung';
