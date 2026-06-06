SET search_path TO rechnung;

COPY rechnung(invoice_id, customer_name, iban, total_amount, currency, issue_date)
FROM '/init/Rechnung/csv/Rechnung.csv' WITH (FORMAT csv, DELIMITER ';', HEADER true);