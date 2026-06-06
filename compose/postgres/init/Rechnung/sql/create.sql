SET default_tablespace = rechnungspace;

-- =========================
-- Sequence
-- =========================
CREATE SEQUENCE IF NOT EXISTS invoice_seq START 101;

-- =========================
-- Rechnung
-- =========================
CREATE TABLE IF NOT EXISTS rechnung (
    invoice_id      TEXT PRIMARY KEY DEFAULT ('INV-' || LPAD(nextval('invoice_seq')::text, 3, '0')),
    version         INTEGER NOT NULL DEFAULT 0,
    customer_name   TEXT NOT NULL,
    IBAN            VARCHAR(34) NOT NULL,
    total_amount    NUMERIC(10, 2) NOT NULL,
    currency        VARCHAR(3) NOT NULL,
    issue_date      DATE NOT NULL,
    erzeugt         TIMESTAMP NOT NULL DEFAULT NOW(),
    aktualisiert    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS rechnung_iban_idx
    ON rechnung(iban);