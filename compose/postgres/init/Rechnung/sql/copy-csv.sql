SET search_path TO rechnung;

COPY rechnung FROM '/init/rechnung/csv/rechnung.csv' WITH (FORMAT csv,DELIMITER ';', HEADER true);