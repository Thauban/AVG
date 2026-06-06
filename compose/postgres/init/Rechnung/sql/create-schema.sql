CREATE SCHEMA IF NOT EXISTS rechnung AUTHORIZATION sachbearbeiter;

ALTER ROLE sachbearbeiter SET search_path = 'rechnung';