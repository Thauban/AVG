# PostgreSQL Datenbank Setup

> Alle Befehle werden vom **Projektroot** (`AVG/`) ausgeführt, außer es steht etwas anderes dabei.

## Voraussetzungen

- Docker installiert
- Passwortdatei `pw.txt` im Ordner `compose/postgres/` (nicht im Git, selbst anlegen)

```
compose/postgres/pw.txt  →  Inhalt: x
```

---

## Schritt 1 – Named Volumes erstellen (einmalig)

> Verzeichnis: `AVG/` (Projektroot)

```bash
docker volume create avg_data
docker volume create avg_tablespace
docker volume create avg_init
```

---

## Schritt 2 – Dateien in Volume kopieren

> Verzeichnis: `AVG/` (Projektroot)

```bash
docker run \
  -v avg_init:/init \
  -v avg_tablespace:/tablespace \
  -v ./compose/postgres/init:/tmp/init:ro \
  --rm -it -u 0 --entrypoint '' \
  dhi.io/postgres:18.3-debian13 /bin/bash
```

In der Container-Bash dann:

```bash
cp -r /tmp/init/* /init
mkdir /tablespace/rechnung
chown -R postgres:postgres /init /tablespace
chmod 400 /init/Rechnung/sql/* /init/tls/*
exit
```

---

## Schritt 3 – Server einmalig ohne TLS starten (für Initialisierung)

> Verzeichnis: `AVG/compose/postgres/`

In `compose.yml` die Zeile `command: ["-c", "ssl=on"]` auskommentieren, dann:

```bash
# Terminal 1
docker compose up db

# Terminal 2 – TLS-Zertifikate kopieren
docker compose exec db bash -c 'cp /init/tls/* /var/lib/postgresql/18/data'
docker compose down
```

Danach `command: ["-c", "ssl=on"]` wieder einkommentieren.

---

## Schritt 4 – Server mit TLS starten und Datenbank anlegen

> Verzeichnis: `AVG/compose/postgres/`

```bash
# Terminal 1
docker compose up

# Terminal 2
docker compose exec db bash
```

In der Container-Bash:

```bash
psql --dbname=postgres --username=postgres --file=/init/Rechnung/sql/create-db.sql
psql --dbname=rechnung --username=sachbearbeiter --file=/init/Rechnung/sql/create-schema.sql
psql --dbname=rechnung --username=sachbearbeiter --file=/init/Rechnung/sql/create.sql
psql --dbname=rechnung --username=postgres --file=/init/Rechnung/sql/copy-csv.sql
exit
```

Danach:

```bash
docker compose down
```

---

## Schritt 5 – Normal starten

> Verzeichnis: `AVG/compose/postgres/`

```bash
docker compose up
```

Die Datenbank ist erreichbar unter `localhost:5432`.

---

## Nützliche psql-Befehle

> Verzeichnis: `AVG/compose/postgres/`

```bash
docker compose exec db bash -c 'psql --dbname=rechnung --username=sachbearbeiter'
```

```sql
-- Alle Rechnungen anzeigen
SELECT * FROM rechnung.rechnung;

-- Verbindung trennen
\q
```
