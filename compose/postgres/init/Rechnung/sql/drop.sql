-- =========================
-- Indizex löschen
-- =========================
DROP INDEX IF EXISTS
    rechnung_iban_idx;

-- =========================
-- Tabellen löschen (Reihenfolge wichtig wegen FK)
-- =========================
DROP TABLE IF EXISTS
    rechnungsposition;

DROP TABLE IF EXISTS
    rechnung;

