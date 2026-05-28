SET default_tablespace = rechnungspace;

-- =========================
-- Mitarbeiter
-- =========================
CREATE TABLE IF NOT EXISTS mitarbeiter (
    id              INTEGER GENERATED ALWAYS AS IDENTITY(START WITH 1000) PRIMARY KEY,
    version         INTEGER NOT NULL DEFAULT 0,
    nachname        TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    "position"        "position" NOT NULL,
    gehalt          NUMERIC(10,2) NOT NULL CHECK (gehalt >= 0),
    eintrittsdatum  DATE NOT NULL CHECK (eintrittsdatum <= current_date),
    homepage        TEXT,
    geschlecht      geschlecht,
    username        TEXT NOT NULL,
    erzeugt         TIMESTAMP NOT NULL,
    aktualisiert    TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS rechnung_iban_idx
    ON rechnung(iban);